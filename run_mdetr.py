import argparse
import math
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import torch
import torchvision.transforms as tt
from PIL import Image, ImageFile
from rhoknp import Document, Jumanpp
from transformers import BatchEncoding, CharSpan

from util.util import CamelCaseDataClassJsonMixin, Rectangle

from hubconf import _make_detr  # noqa: E402

torch.set_grad_enabled(False)


@dataclass(frozen=True, eq=True)
class BoundingBox(CamelCaseDataClassJsonMixin):
    rect: Rectangle
    class_name: str
    confidence: float
    word_probs: List[float]

    def __hash__(self):
        return hash((self.rect, self.class_name, self.confidence, tuple(self.word_probs)))


@dataclass(frozen=True)
class MDETRPrediction(CamelCaseDataClassJsonMixin):
    bounding_boxes: List[BoundingBox]
    words: List[str]


# for output bounding box post-processing
def box_cxcywh_to_xyxy(
    x: torch.Tensor,  # (N, 4)
) -> torch.Tensor:
    x_c, y_c, w, h = x.unbind(1)
    b = [(x_c - 0.5 * w), (y_c - 0.5 * h), (x_c + 0.5 * w), (y_c + 0.5 * h)]
    return torch.stack(b, dim=1)


def rescale_bboxes(
    out_bbox: torch.Tensor,  # (N, 4)
    size: Tuple[int, int],
) -> torch.Tensor:  # (N, 4)
    img_w, img_h = size
    b = box_cxcywh_to_xyxy(out_bbox)
    b = b * torch.tensor([img_w, img_h, img_w, img_h], dtype=torch.float32)
    return b


# colors for visualization
COLORS = [
    [0.000, 0.447, 0.741],
    [0.850, 0.325, 0.098],
    [0.929, 0.694, 0.125],
    [0.494, 0.184, 0.556],
    [0.466, 0.674, 0.188],
    [0.301, 0.745, 0.933],
]


def apply_mask(image, mask, color, alpha=0.5):
    """Apply the given mask to the image."""
    for c in range(3):
        image[:, :, c] = np.where(mask == 1, image[:, :, c] * (1 - alpha) + alpha * color[c] * 255, image[:, :, c])
    return image


def plot_results(image: ImageFile, prediction: MDETRPrediction) -> None:
    plt.figure(figsize=(16, 10))
    np_image = np.array(image)
    ax = plt.gca()
    colors = COLORS * 100

    for bounding_box in prediction.bounding_boxes:
        rect = bounding_box.rect
        score = bounding_box.confidence
        label = ",".join(word for word, prob in zip(prediction.words, bounding_box.word_probs) if prob >= 0.1)
        color = colors.pop()
        ax.add_patch(plt.Rectangle((rect.x1, rect.y1), rect.w, rect.h, fill=False, color=color, linewidth=3))
        ax.text(
            rect.x1,
            rect.y1,
            f'{label}: {score:0.2f}',
            fontsize=15,
            bbox=dict(facecolor=color, alpha=0.8),
            fontname='Hiragino Maru Gothic Pro',
        )

    plt.imshow(np_image)
    plt.axis('off')
    plt.savefig('output.png')
    plt.show()


def predict_mdetr(
    checkpoint_path: Path, images: list, caption: Document, batch_size: int = 32
) -> List[MDETRPrediction]:
    if len(images) == 0:
        return []
    model = _make_detr(backbone_name='timm_tf_efficientnet_b3_ns', text_encoder='xlm-roberta-base')
    checkpoint = torch.load(str(checkpoint_path), map_location='cpu')
    model.load_state_dict(checkpoint['model'])
    if torch.cuda.is_available():
        model = model.cuda()
    model.eval()

    assert caption.need_jumanpp is False

    # standard PyTorch mean-std input image normalization
    transform = tt.Compose([tt.Resize(800), tt.ToTensor(), tt.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])

    predictions: list[MDETRPrediction] = []
    image_size = images[0].size
    assert all(im.size == image_size for im in images)
    # mean-std normalize the input image
    image_tensors = [transform(im) for im in images]
    for batch_idx in range(math.ceil(len(images) / batch_size)):
        img = torch.stack(image_tensors[batch_idx * batch_size : (batch_idx + 1) * batch_size], dim=0)  # (b, ch, H, W)
        if torch.cuda.is_available():
            img = img.cuda()

        # propagate through the model
        memory_cache = model(img, [caption.text] * img.size(0), encode_and_save=True)
        # dict keys: 'pred_logits', 'pred_boxes', 'proj_queries', 'proj_tokens', 'tokenized'
        # pred_logits: (b, cand, seq)
        # pred_boxes: (b, cand, 4)
        # proj_queries: (b, cand, 64)
        # proj_tokens: (b, 28, 64)
        # tokenized: BatchEncoding
        outputs: dict = model(img, [caption.text] * img.size(0), encode_and_save=False, memory_cache=memory_cache)
        pred_logits: torch.Tensor = outputs['pred_logits'].cpu()  # (b, cand, seq)
        pred_boxes: torch.Tensor = outputs['pred_boxes'].cpu()  # (b, cand, 4)
        tokenized: BatchEncoding = memory_cache['tokenized']

        for pred_logit, pred_box in zip(pred_logits, pred_boxes):  # (cand, seq), (cand, 4)
            # keep only predictions with 0.0+ confidence
            # -1: no text
            probs: torch.Tensor = 1 - pred_logit.softmax(dim=-1)[:, -1]  # (cand)
            keep: torch.Tensor = probs >= 0.0  # (cand)

            # convert boxes from [0; 1] to image scales
            bboxes_scaled = rescale_bboxes(pred_boxes[0, keep], image_size)  # (kept, 4)

            bounding_boxes = []
            for prob, bbox, token_probs in zip(
                probs[keep].tolist(), bboxes_scaled.tolist(), pred_logits[0, keep].softmax(dim=-1)
            ):
                char_probs: list[float] = [0] * len(caption.text)
                for pos, token_prob in enumerate(token_probs.tolist()):
                    try:
                        span: CharSpan = tokenized.token_to_chars(0, pos)
                    except TypeError:
                        continue
                    char_probs[span.start : span.end] = [token_prob] * (span.end - span.start)
                word_probs: list[float] = []
                char_span = CharSpan(0, 0)
                for morpheme in caption.morphemes:
                    char_span = CharSpan(char_span.end, char_span.end + len(morpheme.text))
                    word_probs.append(np.max(char_probs[char_span.start : char_span.end]).item())

                bounding_boxes.append(
                    BoundingBox(
                        rect=Rectangle.from_xyxy(*bbox),
                        class_name="",
                        confidence=prob,
                        word_probs=word_probs,
                    )
                )
            predictions.append(MDETRPrediction(bounding_boxes, [m.text for m in caption.morphemes]))
    return predictions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', '-m', type=str, help='Path to trained model.')
    # parser.add_argument('--image-dir', '--img', type=str, help='Path to the directory containing images.')
    parser.add_argument('--image-files', '--img', type=str, nargs='*', help='Path to images files.')
    parser.add_argument(
        '--text', type=str, default='5 people each holding an umbrella', help='split text to perform grounding.'
    )
    parser.add_argument('--caption-file', type=str, help='Path to Juman++ file for caption.')
    parser.add_argument('--batch-size', '--bs', type=int, default=32, help='Batch size.')
    parser.add_argument('--export-dir', type=str, help='Path to directory to export results.')
    args = parser.parse_args()

    # url = "http://images.cocodataset.org/val2017/000000281759.jpg"
    # web_image = requests.get(url, stream=True).raw
    # image = Image.open(web_image)

    images = [Image.open(image_file) for image_file in args.image_files]
    if args.caption_file is not None:
        caption = Document.from_jumanpp(Path(args.caption_file).read_text())
    else:
        caption = Jumanpp().apply_to_document(args.text)

    predictions = predict_mdetr(args.model, images, caption, args.batch_size)
    # plot_results(image, predictions[0])

    export_dir = Path(args.export_dir)
    export_dir.mkdir(exist_ok=True)
    for image_file, prediction in zip(args.image_files, predictions):
        export_dir.joinpath(f'{Path(image_file).stem}.json').write_text(prediction.to_json())


if __name__ == '__main__':
    main()
