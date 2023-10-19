#!/usr/bin/env bash

set -euo pipefail

TEXT_ENCODER=xlm-roberta-base  # xlm-roberta-base or microsoft/mdeberta-v3-base
IMAGE_BACKBENE=timm_tf_efficientnet_b3_ns
DEVICES=2
BATCH_SIZE=4

poetry run python -m torch.distributed.run --nproc_per_node="${DEVICES}" main.py \
  --dataset_config configs/mmdialogue.json \
  --ema \
  --text_encoder_type "${TEXT_ENCODER}" \
  --backbone "${IMAGE_BACKBENE}" \
  --lr_backbone 5e-5 \
  --batch_size "${BATCH_SIZE}" \
  --epochs 4 \
  --output_dir ./result/pretrained_b3_roberta_ja_mixed_2e_mmdialogue_4e_b8 \
  --load ./result/pretrained_b3_roberta_ja_mixed_2e/checkpoint_1.pth \
  --num_workers 8
