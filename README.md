# ChuangJu AI · 创居 — Multimodal Home-Design Platform

A multimodal AI platform that closes the loop **understanding → retrieval → generation** for home design: upload a room photo and get structured tags, find reference cases by tag combos or one natural-language sentence, and turn a 2D floor-plan sketch + text description into a photorealistic rendering.

English | [简体中文](README.zh-CN.md)

[![Python](https://img.shields.io/badge/Python-3.9-3776AB.svg)](https://www.python.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.1.2+cu118-EE4C2C.svg)](https://pytorch.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

<p align="center">
  <img src="docs/images/architecture.png" alt="ChuangJu AI architecture" width="820">
</p>

## Four modules

| Module | What it does | Core tech |
|---|---|---|
| ① **Auto-Tagging** | From one room photo: room type, overall style, and per-furniture local styles | Multi-task classification (self-trained `.pth`) + YOLOv8n detection |
| ② **Tag Library Search** | Filter a labeled case library by room-type × style combos | Curated labeled image base |
| ③ **Natural-Language Search** | "A cozy cream-style bedroom" → matching cases | text2vec-base-chinese embeddings + vector similarity |
| ④ **Floor-Plan AI Design** | 2D floor-plan sketch + text → photorealistic rendering matching the structure | ControlNet-Lineart + Stable Diffusion (Realistic Vision V5.1) + optional LoRA |

Serving: backend API (`3_final_system_api.py`) + Streamlit UI (`4_streamlit_ui.py`, port 8501) + a Java Web showcase module (`ChuangJu-JavaWeb/`).

## Quick Start

```bash
# 1. environment (Python 3.9)
conda create --name AI python=3.9 -y && conda activate AI
pip install -r requirements.txt
# PyTorch 2.1.2 + cu118 wheels (see README.zh-CN.md for the exact pip lines)

# 2. data + training (only if you want to retrain the classifiers)
python 1_prepare_all_data.py                       # expects datasets/<room>/<style>/*.jpg
python 2_train_all_models.py                       # all models
python 2_train_all_models.py --module main         # room type + overall style only
python 2_train_all_models.py --module sideline --furniture_type sofa

# 3. launch
python 3_final_system_api.py        # terminal 1 — backend API
streamlit run 4_streamlit_ui.py     # terminal 2 — UI at http://localhost:8501
```

HuggingFace slow? Set the mirror first: `$env:HF_ENDPOINT="https://hf-mirror.com"` (Windows) or `export HF_ENDPOINT=https://hf-mirror.com`.

### Model weights (manual download, not in repo)

| Model | Source | Destination |
|---|---|---|
| Stable Diffusion renderer | [SG161222/Realistic_Vision_V5.1_noVAE](https://huggingface.co/SG161222/Realistic_Vision_V5.1_noVAE) (diffusers format) | `realistic-vision-v51/` |
| ControlNet | [lllyasviel/control_v11p_sd15_lineart](https://huggingface.co/lllyasviel/control_v11p_sd15_lineart) | `controlnet-lineart/` |
| Text embedding | [shibing624/text2vec-base-chinese](https://huggingface.co/shibing624/text2vec-base-chinese) | `models/text2vec-base-chinese/` |
| Object detection | YOLOv8n | auto-downloads on first run |
| Panorama LoRA (optional) | HDR360 LoRA | `loras/HDR360.safetensors` |
| Trained classifiers | produced by step 2 | `models/*.pth` |

## Dataset layout

```
datasets/
├── <room type 1>/
│   ├── <style 1>/image_01.jpg ...
│   └── <style 2>/...
└── <room type 2>/...
```

## Project structure

```
1_prepare_all_data.py     dataset preparation / annotation files
2_train_all_models.py     classifier training (main / sideline / per-furniture)
3_final_system_api.py     backend API serving all four modules
4_streamlit_ui.py         Streamlit frontend
models_def.py, config.py  model & config definitions
ChuangJu-JavaWeb/         Java web showcase module
docs/images/              architecture diagram
```

## Notes

- Demo videos and screenshots are not bundled: the full system requires several GB of model weights and a CUDA GPU; see the model table above for setup.
- Trained only on self-collected / licensed data; classifier quality depends on your dataset size and balance.

## License

MIT — see [LICENSE](LICENSE). Third-party models keep their own licenses (see links above).

中文文档见 [README.zh-CN.md](README.zh-CN.md)。
