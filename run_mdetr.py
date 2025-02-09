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
    image_id: str
    rect: Rectangle
    class_name: str
    confidence: float
    word_probs: List[float]

    def __hash__(self):
        return hash((self.rect, self.class_name, self.confidence, tuple(self.word_probs)))


@dataclass(frozen=True)
class MDETRPrediction(CamelCaseDataClassJsonMixin):
    doc_id: str
    image_id: str
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


def plot_results(
    image: ImageFile, image_id: str, prediction: MDETRPrediction, export_dir: Path, confidence_threshold: float = 0.8
) -> None:
    plt.figure(figsize=(16, 10))
    np_image = np.array(image)
    ax = plt.gca()
    colors = COLORS * 100

    for bounding_box in prediction.bounding_boxes:
        rect = bounding_box.rect
        score = bounding_box.confidence
        if score < confidence_threshold:
            continue
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
    plt.savefig(export_dir / f'{image_id}.png')
    plt.show()


def predict_mdetr(
    checkpoint_path: Path, images: list, image_ids: List[str], caption: Document, backbone_name: str, text_encoder: str, batch_size: int = 32
) -> List[MDETRPrediction]:
    if len(images) == 0:
        return []
    model = _make_detr(backbone_name=backbone_name, text_encoder=text_encoder)
    device = torch.device('cuda:0') if torch.cuda.is_available() else torch.device('cpu')
    checkpoint = torch.load(str(checkpoint_path), map_location=device)
    model.load_state_dict(checkpoint['model'])
    model = model.to(device)
    model.eval()

    assert caption.is_jumanpp_required() is False

    # standard PyTorch mean-std input image normalization
    transform = tt.Compose([tt.Resize(800), tt.ToTensor(), tt.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])

    predictions: List[MDETRPrediction] = []
    image_size = images[0].size
    assert all(im.size == image_size for im in images)
    # mean-std normalize the input image
    image_tensors: List[torch.Tensor] = [transform(im) for im in images]  # [(ch, H, W)]
    for batch_idx in range(math.ceil(len(images) / batch_size)):
        img = torch.stack(image_tensors[batch_idx * batch_size : (batch_idx + 1) * batch_size], dim=0)  # (b, ch, H, W)
        img = img.to(device)
        img_ids = image_ids[batch_idx * batch_size : (batch_idx + 1) * batch_size]

        # propagate through the model
        memory_cache = model(img, [caption.text] * img.size(0), encode_and_save=True)
        # dict keys: 'pred_logits', 'pred_boxes', 'proj_queries', 'proj_tokens', 'tokenized'
        # pred_logits: (b, cand, seq)
        # pred_boxes: (b, cand, 4)
        # proj_queries: (b, cand, 64)
        # proj_tokens: (b, 28, 64)
        # tokenized: BatchEncoding
        with torch.no_grad():
            outputs: dict = model(img, [caption.text] * img.size(0), encode_and_save=False, memory_cache=memory_cache)
        pred_logits: torch.Tensor = outputs['pred_logits'].cpu()  # (b, cand, seq)
        pred_boxes: torch.Tensor = outputs['pred_boxes'].cpu()  # (b, cand, 4)
        tokenized: BatchEncoding = memory_cache['tokenized']

        assert len(pred_logits) == len(pred_boxes) == len(img_ids)
        for pred_logit, pred_box, image_id in zip(pred_logits, pred_boxes, img_ids):  # (cand, seq), (cand, 4)
            # NULL ターゲットを指す確率を反転させたものが confidence
            probs: torch.Tensor = 1 - pred_logit.softmax(dim=-1)[:, -1]  # (cand)
            # keep only predictions with 0.0+ confidence
            keep: torch.Tensor = probs.ge(0.0)  # (cand)

            # convert boxes from [0; 1] to image scales
            bboxes_scaled = rescale_bboxes(pred_box[keep], image_size)  # (kept, 4)

            bounding_boxes = []
            for prob, bbox, token_probs in zip(
                probs[keep].tolist(), bboxes_scaled.tolist(), pred_logit[keep].softmax(dim=-1)
            ):
                char_probs: List[float] = [0] * len(caption.text)
                for pos, token_prob in enumerate(token_probs.tolist()):
                    try:
                        span: CharSpan = tokenized.token_to_chars(0, pos)
                    except TypeError:
                        continue
                    char_probs[span.start : span.end] = [token_prob] * (span.end - span.start)
                word_probs: List[float] = []  # 単語を構成するサブワードが持つ確率の最大値
                char_span = CharSpan(0, 0)
                for morpheme in caption.morphemes:
                    char_span = CharSpan(char_span.end, char_span.end + len(morpheme.text))
                    word_probs.append(np.max(char_probs[char_span.start : char_span.end]).item())

                bounding_boxes.append(
                    BoundingBox(
                        image_id=image_id,
                        rect=Rectangle.from_xyxy(*bbox),
                        class_name="",
                        confidence=prob,
                        word_probs=word_probs,
                    )
                )
            predictions.append(
                MDETRPrediction(
                    doc_id=caption.doc_id,
                    image_id=image_id,
                    bounding_boxes=bounding_boxes,
                    words=[m.text for m in caption.morphemes],
                )
            )
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
    parser.add_argument(
        '--backbone-name', type=str, default='timm_tf_efficientnet_b3_ns', help='backbone image encoder name'
    )
    parser.add_argument('--text-encoder', type=str, default='xlm-roberta-base', help='text encoder name')
    parser.add_argument('--batch-size', '--bs', type=int, default=32, help='Batch size.')
    parser.add_argument('--export-dir', type=str, help='Path to directory to export results.')
    parser.add_argument('--plot', action='store_true', help='Plot results.')
    args = parser.parse_args()

    export_dir = Path(args.export_dir)
    export_dir.mkdir(exist_ok=True)

    # url = "http://images.cocodataset.org/val2017/000000281759.jpg"
    # web_image = requests.get(url, stream=True).raw
    # image = Image.open(web_image)

    image_files = [Path(image_file) for image_file in args.image_files]
    images: list = [Image.open(image_file) for image_file in image_files]
    image_ids = [image_file.stem for image_file in image_files]
    assert len(image_ids) == len(set(image_ids)), f'Image ids must be unique: {image_ids}'

    if args.caption_file is not None:
        caption = Document.from_jumanpp(Path(args.caption_file).read_text())
    else:
        caption = Jumanpp().apply_to_document(args.text)

    predictions = predict_mdetr(
        args.model, images, image_ids, caption, args.backbone_name, args.text_encoder, args.batch_size
    )
    if args.plot:
        for prediction in predictions:
            plot_results(images[image_ids.index(prediction.image_id)], prediction.image_id, prediction, export_dir)

    for prediction in predictions:
        export_dir.joinpath(f'{prediction.image_id}.json').write_text(prediction.to_json(indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
