#!/usr/bin/env bash

set -euo pipefail

TEXT_ENCODER=microsoft/mdeberta-v3-base  # xlm-roberta-base or microsoft/mdeberta-v3-base
IMAGE_BACKBENE=timm_tf_efficientnet_b3_ns

# export CUDA_VISIBLE_DEVICES=1,3
# saffron では --bach_size 2
# saffron4 では --bach_size 8 で 70GB 前後消費．2枚使用で eta 18h ほど．
poetry run python -m torch.distributed.run --nproc_per_node=2 main.py \
  --dataset_config configs/pretrain_ja.json \
  --ema \
  --text_encoder_type "${TEXT_ENCODER}" \
  --backbone "${IMAGE_BACKBENE}" \
  --lr_backbone 5e-5 \
  --freeze_text_encoder \
  --batch_size 8 \
  --epochs 2 \
  --output_dir ./result/pretrained_b3_mdeberta_ja_mixed_2e \
  --load ./data/official_ckpt/pretrained_EB3_checkpoint.pth \
  --num_workers 8

# settings on moss110
# poetry run python -m torch.distributed.launch --nproc_per_node=4 --use_env main.py \
# poetry run python main.py \
poetry run python -m torch.distributed.launch --nproc_per_node=4 --use_env main.py \
  --dataset_config configs/pretrain_ja_flickr.json \
  --ema \
  --text_encoder_type "${TEXT_ENCODER}" \
  --backbone "${IMAGE_BACKBENE}" \
  --lr_backbone 5e-5 \
  --freeze_text_encoder \
  --batch_size 2 \
  --epochs 2 \
  --output_dir ./result/pretrained_b3_mdeberta_ja_mixed_2e_flickr_2e \
  --load ./result/pretrained_b3_mdeberta_ja_mixed_2e/checkpoint.pth \
  --num_workers 8
