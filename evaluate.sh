#!/usr/bin/env bash

set -euo pipefail

exp_name=pretrained_ja_flickr_mixed_1e_flickr_1e

python -m torch.distributed.launch --nproc_per_node=4 --use_env main.py \
  --dataset_config configs/pretrain_ja.json \
  --ema \
  --text_encoder_type xlm-roberta-base \
  --backbone timm_tf_efficientnet_b3_ns \
  --lr_backbone 5e-5 \
  --freeze_text_encoder \
  --batch_size 1 \
  --output_dir "result/${exp_name}" \
  --load "result/${exp_name}/checkpoint.pth" \
  --eval
