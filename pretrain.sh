#!/usr/bin/env bash

set -euo pipefail

TEXT_ENCODER=xlm-roberta-base  # xlm-roberta-base or microsoft/mdeberta-v3-base
IMAGE_BACKBENE=timm_tf_efficientnet_b3_ns
DEVICES=3
BATCH_SIZE=4

# export CUDA_VISIBLE_DEVICES=1,3
# saffron では --bach_size 2
# saffron4 では --bach_size 8 で 70GB 前後消費．2枚使用で eta 18h ほど．
poetry run python -m torch.distributed.run --nproc_per_node="${DEVICES}" main.py \
  --dataset_config configs/pretrain_ja.json \
  --ema \
  --text_encoder_type "${TEXT_ENCODER}" \
  --backbone "${IMAGE_BACKBENE}" \
  --lr_backbone 5e-5 \
  --freeze_text_encoder \
  --skip_loading_text_encoder \
  --batch_size "${BATCH_SIZE}" \
  --epochs 2 \
  --output_dir ./result/pretrained_b3_roberta_ja_mixed_2e \
  --load ./data/official_ckpt/pretrained_EB3_checkpoint.pth \
  --num_workers 8
