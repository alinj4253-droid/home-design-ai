# config.py
from pathlib import Path

# --- 基础路径配置 ---
PROJECT_ROOT = Path(__file__).resolve().parent
BASE_DATA_DIR = PROJECT_ROOT / "datasets"
GENERATED_LOCAL_DIR = PROJECT_ROOT / "generated_local_data"
ANNOTATIONS_OUTPUT_DIR = PROJECT_ROOT / "annotations"
MODEL_OUTPUT_DIR = PROJECT_ROOT / "models"
DB_FILE = PROJECT_ROOT / "home_style_library.db"
VECTOR_INDEX_FILE = PROJECT_ROOT / "image_library.faiss"
FONT_FILE = PROJECT_ROOT / "simhei.ttf"

# --- 模型相关配置 ---
# 智能打标
MAIN_TASK_MODEL_NAME = 'vit_base_patch16_384'
LOCAL_TASK_MODEL_NAME = 'vit_base_patch16_224'
# 自然语言搜索
SEMANTIC_MODEL_NAME = 'shibing624/text2vec-base-chinese'
# 户型图AI设计
REALISTIC_VISION_MODEL_PATH = PROJECT_ROOT / 'realistic-vision-v51'
CONTROLNET_LINEART_MODEL_PATH = PROJECT_ROOT / "controlnet-lineart"
# 全景图LoRA路径
PANORAMA_LORA_PATH = PROJECT_ROOT / "loras" / "HDR360.safetensors"

# --- 训练超参数 ---
EPOCHS = 30
BATCH_SIZE = 16
HEAD_LR = 1e-4
MAIN_LR = 2e-5
PATIENCE = 7
VAL_SPLIT = 0.2

# --- API服务配置 ---
API_HOST = "0.0.0.0"
API_PORT = 8000