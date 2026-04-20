# 3_final_system_api.py

import sys
import asyncio

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# --- 基础模块 ---
import torch
import uvicorn
import io
import base64
import numpy as np
import json
import argparse
import zipfile
import uuid
import time
import sqlite3
import contextlib
import glob
import threading
from PIL import Image, ImageDraw, ImageFont, ImageOps
from pathlib import Path
from typing import List, Optional
from packaging import version
from tqdm import tqdm
from fastapi import Query
import math

# --- FastAPI 框架 ---
from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Depends, Form, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# --- AI/ML 核心库 ---
import torch.nn.functional as F
from torch.amp import autocast
from sentence_transformers import SentenceTransformer
import faiss
from ultralytics import YOLO
import torchvision.transforms as transforms
from diffusers import StableDiffusionControlNetPipeline, ControlNetModel, UniPCMultistepScheduler
from controlnet_aux import LineartDetector

# --- 本地模块 ---
import config
from models_def import MultiTaskStyleRoomClassifier, StyleClassifier as LocalStyleClassifier

# --- 全局配置与状态 ---
Image.MAX_IMAGE_PIXELS = None
BATCH_TASKS = {}
SYSTEM_STATUS = {"status": "loading", "message": "系统正在启动..."}

# --- 辅助函数 ---
def create_visualized_image(pil_image: Image.Image, analysis_result: dict, confidence_threshold: float = 0.5):
    image_to_draw = pil_image.copy()
    high_confidence_objects = [obj for obj in analysis_result.get("sideline_task_analysis", []) if obj.get('style_confidence', 0) >= confidence_threshold]
    if not high_confidence_objects:
        buffered = io.BytesIO()
        image_to_draw.save(buffered, format="PNG")
        return f"data:image/png;base64,{base64.b64encode(buffered.getvalue()).decode()}"
    
    draw = ImageDraw.Draw(image_to_draw)
    try:
        font = ImageFont.truetype(str(config.FONT_FILE), 24)
    except IOError:
        font = ImageFont.load_default()
        
    for obj in high_confidence_objects:
        box = obj['bounding_box']
        label = f"{obj['furniture_type']}: {obj['predicted_style']}"
        draw.rectangle(box, outline="red", width=3)
        text_position = (box[0] + 5, box[1] + 5)
        text_bbox = draw.textbbox(text_position, label, font=font)
        draw.rectangle(text_bbox, fill="red")
        draw.text(text_position, label, fill="white", font=font)
        
    buffered = io.BytesIO()
    image_to_draw.save(buffered, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(buffered.getvalue()).decode()}"

def pil_image_to_bytes(pil_image: Image.Image, format="PNG"):
    buffered = io.BytesIO()
    pil_image.save(buffered, format=format)
    return buffered.getvalue()

def process_zip_file_in_background(task_id: str, zip_bytes: bytes, confidence_threshold: float, inference_sys: 'InferenceSystem'):
    task = BATCH_TASKS[task_id]
    results = []
    supported_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.webp']
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as zf:
            image_filenames = [f for f in zf.namelist() if not f.startswith('__MACOSX/') and any(f.lower().endswith(ext) for ext in supported_extensions)]
            total_images = len(image_filenames)
            task['status'] = 'processing'
            task['progress'] = f"0 / {total_images}"
            for i, filename in enumerate(image_filenames):
                with zf.open(filename) as image_file:
                    pil_image = Image.open(io.BytesIO(image_file.read())).convert("RGB")
                    analysis_result = inference_sys.analyze_image(pil_image)
                    if analysis_result:
                        analysis_result["visualized_image_base64"] = create_visualized_image(pil_image, analysis_result, confidence_threshold)
                        results.append({"filename": filename, "analysis": analysis_result})
                task['progress'] = f"{i + 1} / {total_images}"
        task['status'] = 'complete'
        task['results'] = results
    except Exception as e:
        task['status'] = 'failed'
        task['error'] = str(e)

# --- AI核心系统类 ---
class InferenceSystem:
    def __init__(self):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.use_torch_compile = version.parse(torch.__version__) >= version.parse("2.0.0")
        self._load_all_models()
        self._prepare_transforms()
    
    def _load_model_with_compile(self, model, model_path, checkpoint_key=None):
        if checkpoint_key:
            checkpoint = torch.load(model_path, map_location=self.device)
            model.load_state_dict(checkpoint[checkpoint_key])
        else:
            model.load_state_dict(torch.load(model_path, map_location=self.device))
        model.to(self.device).eval()
        if self.use_torch_compile and self.device.type == 'cuda':
            # model = torch.compile(model) 【windows系统 × linux √】
            print()
        return model

    def _load_multitask_model(self):
        model_path = config.MODEL_OUTPUT_DIR / 'multitask_model_best.pth'
        ann_path = config.ANNOTATIONS_OUTPUT_DIR / 'main_task' / 'train_multitask.json'
        if not (model_path.exists() and ann_path.exists()): return None, None
        with open(ann_path, 'r', encoding='utf-8') as f: annotations = json.load(f)
        styles = sorted(list(set(ann['style'] for ann in annotations if ann.get('style'))))
        room_types = sorted(list(set(ann['room_type'] for ann in annotations if ann.get('room_type'))))
        model = MultiTaskStyleRoomClassifier(len(styles), len(room_types), model_name=config.MAIN_TASK_MODEL_NAME)
        model = self._load_model_with_compile(model, model_path)
        labels = {'style_map': {i: n for i, n in enumerate(styles)}, 'room_type_map': {i: n for i, n in enumerate(room_types)}}
        print(f"✓ 主线多任务模型加载成功。")
        return model, labels
    
    def _load_local_models(self):
        local_classifiers, local_labels = {}, {}
        ann_path = config.ANNOTATIONS_OUTPUT_DIR / 'sideline_task' / 'train_local.json'
        if not ann_path.exists(): return {}, {}
        with open(ann_path, 'r', encoding='utf-8') as f: all_ann = json.load(f)
        anns_by_type = {}
        for ann in all_ann:
            f_type = ann.get('furniture_type')
            if f_type: anns_by_type.setdefault(f_type, []).append(ann)
        for f_type in ['bed', 'sofa', 'chair']:
            model_path = config.MODEL_OUTPUT_DIR / f'{f_type}_classifier.pth'
            if model_path.exists() and f_type in anns_by_type:
                styles = sorted(list(set(ann['style'] for ann in anns_by_type[f_type] if ann.get('style'))))
                model = LocalStyleClassifier(len(styles), config.LOCAL_TASK_MODEL_NAME)
                model = self._load_model_with_compile(model, model_path, checkpoint_key='model_state_dict')
                local_classifiers[f_type] = model
                local_labels[f_type] = {'style_map': {i: n for i, n in enumerate(styles)}}
                print(f"✓ 副线局部模型 '{f_type}' 加载成功。")
        return local_classifiers, local_labels

    def _load_all_models(self):
        print("\n--- 正在加载所有打标模型... ---")
        self.multitask_model, self.multitask_labels = self._load_multitask_model()
        self.local_classifiers, self.local_labels = self._load_local_models()
        try:
            self.yolo_model = YOLO(config.PROJECT_ROOT / 'yolov8n.pt')
            self.yolo_mapping = {'bed': 'bed', 'chair': 'chair', 'couch': 'sofa', 'sofa': 'sofa'}
            print("✓ YOLOv8模型加载成功。")
        except Exception as e:
            self.yolo_model = None; print(f"⚠️ YOLO模型加载失败: {e}")
        print("--- 所有打标模型加载完毕 ---")
    
    def _prepare_transforms(self):
        self.transform_global = transforms.Compose([transforms.Resize((384, 384)), transforms.ToTensor(), transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])
        self.transform_local = transforms.Compose([transforms.Resize((224, 224)), transforms.ToTensor(), transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])
    
    def analyze_image(self, image_path_or_pil):
        try:
            if isinstance(image_path_or_pil, (str, Path)):
                image_pil = Image.open(image_path_or_pil).convert("RGB")
                try: image_path_str = str(Path(image_path_or_pil).relative_to(config.BASE_DATA_DIR))
                except ValueError: image_path_str = str(image_path_or_pil)
            else:
                image_pil = image_path_or_pil; image_path_str = "uploaded_image"
        except Exception: return None
        result = {"image_path": image_path_str, "main_task_analysis": {}, "sideline_task_analysis": []}
        with torch.no_grad(), autocast(device_type=self.device.type, enabled=self.device.type == 'cuda'):
            if self.multitask_model:
                input_tensor = self.transform_global(image_pil).unsqueeze(0).to(self.device)
                style_logits, room_logits = self.multitask_model(input_tensor)
                style_probs, room_probs = F.softmax(style_logits, 1).cpu().squeeze(), F.softmax(room_logits, 1).cpu().squeeze()
                style_idx, room_idx = style_probs.argmax().item(), room_probs.argmax().item()
                result["main_task_analysis"] = {"predicted_style": self.multitask_labels['style_map'][style_idx], "style_confidence": float(style_probs[style_idx]),"predicted_room_type": self.multitask_labels['room_type_map'][room_idx], "room_type_confidence": float(room_probs[room_idx])}
            if self.yolo_model and self.local_classifiers:
                yolo_results = self.yolo_model(image_pil, conf=0.4, verbose=False)
                for res in yolo_results:
                    for box in res.boxes:
                        cls_name = res.names[int(box.cls[0])].lower()
                        if cls_name in self.yolo_mapping:
                            f_type = self.yolo_mapping[cls_name]
                            if f_type in self.local_classifiers:
                                x1, y1, x2, y2 = map(int, box.xyxy[0])
                                cropped_pil = image_pil.crop((x1, y1, x2, y2))
                                in_tensor = self.transform_local(cropped_pil).unsqueeze(0).to(self.device)
                                logits = self.local_classifiers[f_type](in_tensor)
                                probs = F.softmax(logits, 1).cpu().squeeze()
                                pred_idx = probs.argmax().item()
                                result["sideline_task_analysis"].append({"furniture_type": f_type, "bounding_box": [x1, y1, x2, y2],"predicted_style": self.local_labels[f_type]['style_map'][pred_idx],"style_confidence": float(probs[pred_idx])})
        return result

class SemanticSearchSystem:
    def __init__(self, model_name=config.SEMANTIC_MODEL_NAME, index_path=str(config.VECTOR_INDEX_FILE)):
        print("\n--- 正在加载语义搜索系统... ---")
        self.model = SentenceTransformer(model_name)
        self.index = faiss.read_index(index_path)
        with contextlib.closing(sqlite3.connect(config.DB_FILE)) as db:
            db.row_factory = sqlite3.Row
            self.known_room_types = [row['room_type'] for row in db.execute("SELECT DISTINCT room_type FROM images WHERE room_type IS NOT NULL").fetchall()]
            self.known_styles = [row['style'] for row in db.execute("SELECT DISTINCT style FROM images WHERE style IS NOT NULL").fetchall()]
        print("✓ 语义搜索系统加载成功。")
    def search(self, query: str, k: int = 10, db: sqlite3.Connection = None, filter_dict: dict = None):
        query_vector = self.model.encode([query], normalize_embeddings=True).astype('float32')
        search_k = min(k * 20, self.index.ntotal)
        if search_k == 0: return []
        distances, ids = self.index.search(query_vector, search_k)
        semantic_results = ids[0].tolist()
        if not filter_dict or not db or not semantic_results: return semantic_results[:k]
        id_placeholders = ','.join('?' for _ in semantic_results)
        sql_query = f"SELECT id FROM images WHERE id IN ({id_placeholders})"
        params = list(semantic_results)
        for key, value in filter_dict.items():
            sql_query += f" AND {key} = ?"; params.append(value)
        cursor = db.cursor(); cursor.execute(sql_query, params)
        filtered_ids = {row[0] for row in cursor.fetchall()}
        return [id for id in semantic_results if id in filtered_ids][:k]

class FloorplanGenerationSystem:
    def __init__(self):
        print("\n--- 正在加载【户型图AI设计】引擎... ---")
        device, torch_dtype = "cuda", torch.float16
        base_model_path, controlnet_path = str(config.REALISTIC_VISION_MODEL_PATH), str(config.CONTROLNET_LINEART_MODEL_PATH)
        print(f" > 加载ControlNet(Lineart): {controlnet_path}")
        controlnet = ControlNetModel.from_pretrained(controlnet_path, torch_dtype=torch_dtype, local_files_only=True)
        print(" > 加载LineartDetector预处理器...")
        self.preprocessor = LineartDetector.from_pretrained("lllyasviel/Annotators")
        print(f" > 加载基础渲染模型: {base_model_path}")
        self.pipe = StableDiffusionControlNetPipeline.from_pretrained(base_model_path, controlnet=controlnet, torch_dtype=torch_dtype, local_files_only=True, safety_checker=None).to(device)
        print(" > 加载并融合Panorama LoRA...")
        self.pipe.load_lora_weights(config.PANORAMA_LORA_PATH)
        self.pipe.scheduler = UniPCMultistepScheduler.from_config(self.pipe.scheduler.config)
        print("✓ 户型图AI设计引擎准备就绪。")

    def generate(self, floorplan_image: Image.Image, prompt: str, negative_prompt: str,
                 guidance_scale: float, num_steps: int, seed: int, is_panorama: bool = False):
        
        print(f" > 正在执行生成任务... (模式: {'3D全景' if is_panorama else '标准图片'})")
        
        control_image = self.preprocessor(floorplan_image, detect_resolution=512, image_resolution=512)
        generator = torch.Generator(device="cuda").manual_seed(seed) if seed != -1 else None

        if is_panorama:
            final_prompt = f"3d, panorama, equirectangular, virtual reality, 360 view, {prompt}"
            width, height = 1024, 512
            lora_scale = 0.8
        else:
            final_prompt = prompt
            lora_scale = 0.0
            orig_width, orig_height = floorplan_image.size
            aspect_ratio = orig_width / orig_height
            target_pixels = 512 * 768
            new_height = int((target_pixels / aspect_ratio) ** 0.5)
            new_width = int(new_height * aspect_ratio)
            width = int(new_width / 8) * 8
            height = int(new_height / 8) * 8
            print(f"   > 原始尺寸: {orig_width}x{orig_height}, 智能适配生成尺寸: {width}x{height}")

        output_image = self.pipe(
            final_prompt,
            negative_prompt=negative_prompt,
            image=control_image,
            num_inference_steps=num_steps,
            generator=generator,
            guidance_scale=guidance_scale,
            width=width,
            height=height,
            cross_attention_kwargs={"scale": lora_scale}
        ).images[0]
        
        print(" ✓ 效果图生成完成。")
        return output_image


# --- 数据库与后台初始化任务 ---
def create_database_table(db: sqlite3.Connection):
    db.execute('CREATE TABLE IF NOT EXISTS images (id INTEGER PRIMARY KEY, image_path TEXT UNIQUE, style TEXT, room_type TEXT, detected_objects TEXT)'); db.commit()
    print("✓ 数据库及表结构准备就绪。")

def run_indexing_task(inference_sys: InferenceSystem):
    print("\n[后台任务] 👉 数据入库任务已启动...")
    supported_formats = ['.jpg', '.jpeg', '.png', '.bmp', '.webp']
    image_paths = [p for p in glob.glob(str(config.BASE_DATA_DIR / '**' / '*.*'), recursive=True) if Path(p).suffix.lower() in supported_formats]
    with contextlib.closing(sqlite3.connect(config.DB_FILE, check_same_thread=False)) as db:
        for img_path in tqdm(image_paths, desc="[后台任务] 数据入库进度"):
            data = inference_sys.analyze_image(img_path)
            if data:
                main = data.get("main_task_analysis", {})
                objects = json.dumps(data.get("sideline_task_analysis", []), ensure_ascii=False)
                db.execute('INSERT OR REPLACE INTO images (image_path, style, room_type, detected_objects) VALUES (?, ?, ?, ?)', (data["image_path"], main.get("predicted_style"), main.get("predicted_room_type"), objects))
        db.commit()
    print(" [后台任务] 数据入库完成！")

def create_vector_index_func():
    print("\n[后台任务] 开始构建向量索引...")
    if not config.DB_FILE.exists(): print(" 错误：数据库文件未找到。"); return False
    try:
        model = SentenceTransformer(config.SEMANTIC_MODEL_NAME)
        with contextlib.closing(sqlite3.connect(config.DB_FILE, check_same_thread=False)) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute("SELECT id, style, room_type, detected_objects FROM images").fetchall()
        if not rows: print(" 警告: 数据库为空，跳过向量索引创建。"); return True
        descriptions, db_ids = [], []
        for row in tqdm(rows, desc="[后台任务] 生成文本描述"):
            desc_parts = []
            if row['room_type']: desc_parts.append(row['room_type'])
            if row['style']: desc_parts.append(row['style'] + "风格")
            try:
                if row['detected_objects'] and row['detected_objects'].strip():
                    objects = json.loads(row['detected_objects'])
                    if objects:
                        furniture_types = sorted(list(set(obj['furniture_type'] for obj in objects)))
                        if furniture_types: desc_parts.append("其中包含" + "、".join(furniture_types))
            except (json.JSONDecodeError, TypeError): pass
            descriptions.append("，".join(desc_parts)); db_ids.append(row['id'])
        vectors = model.encode(descriptions, show_progress_bar=True, normalize_embeddings=True)
        index = faiss.IndexIDMap(faiss.IndexFlatL2(vectors.shape[1]))
        index.add_with_ids(vectors.astype('float32'), np.array(db_ids).astype('int64'))
        faiss.write_index(index, str(config.VECTOR_INDEX_FILE))
        print(f"✓ 向量索引已保存。共索引 {index.ntotal} 条记录。")
        return True
    except Exception as e:
        print(f" [后台任务] 向量索引构建失败: {e}"); import traceback; traceback.print_exc(); return False

def run_full_setup_in_background(app: FastAPI):
    global SYSTEM_STATUS
    try:
        SYSTEM_STATUS = {"status": "indexing_database", "message": "正在执行首次数据入库，请稍候..."}
        run_indexing_task(app.state.inference_system)
        SYSTEM_STATUS = {"status": "indexing_vector", "message": "数据入库完成，正在构建向量索引..."}
        if not create_vector_index_func():
            SYSTEM_STATUS = {"status": "failed", "message": "向量索引构建失败。"}; return
        SYSTEM_STATUS = {"status": "reloading_search", "message": "索引完成，正在重载语义搜索模块..."}
        app.state.semantic_search_system = SemanticSearchSystem()
        SYSTEM_STATUS = {"status": "ready", "message": "系统就绪，所有功能可用。"}
        print("\n [后台任务] 所有初始化任务完成，系统已就绪！")
    except Exception as e:
        SYSTEM_STATUS = {"status": "failed", "message": f"后台初始化任务发生未知错误: {e}"}; import traceback; traceback.print_exc()

# --- FastAPI 应用与生命周期 ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    global SYSTEM_STATUS
    print("INFO:     Application starting up...")
    app.state.inference_system = None; app.state.semantic_search_system = None; app.state.floorplan_generation_system = None
    try:
       with contextlib.closing(sqlite3.connect(config.DB_FILE, check_same_thread=False)) as db: create_database_table(db)
    except Exception as e:
        SYSTEM_STATUS = {"status": "failed", "message": f"数据库初始化失败: {e}"}; yield; return
    if config.MODEL_OUTPUT_DIR.exists(): app.state.inference_system = InferenceSystem()
    db_populated = False
    if config.DB_FILE.exists():
        with contextlib.closing(sqlite3.connect(config.DB_FILE, check_same_thread=False)) as db:
            if db.execute("SELECT COUNT(*) FROM images").fetchone()[0] > 0: db_populated = True
    if db_populated and config.VECTOR_INDEX_FILE.exists():
        app.state.semantic_search_system = SemanticSearchSystem()
        SYSTEM_STATUS = {"status": "ready", "message": "系统就绪，所有功能可用。"}; print(" 系统文件完整，直接启动。")
    else:
        print(" 检测到首次运行或数据不完整，将在后台自动执行初始化任务。")
        SYSTEM_STATUS = {"status": "initializing", "message": "首次运行，后台正在初始化..."}
        thread = threading.Thread(target=run_full_setup_in_background, args=(app,), daemon=True); thread.start()
    print("INFO:     Application startup complete.")
    yield
    print("INFO:     Application shutdown.")

app = FastAPI(title="创居AI - 智能家居设计平台", version="9.0.0_FINAL", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.mount("/static_images", StaticFiles(directory=config.BASE_DATA_DIR), name="static_images")

def get_db():
    db = sqlite3.connect(config.DB_FILE, check_same_thread=False); db.row_factory = sqlite3.Row
    try: yield db
    finally: db.close()

# --- API 端点 ---
@app.get("/", tags=["系统状态"])
def read_root(): return {"status": "ok", "version": "9.0.0"}

@app.get("/system-status", tags=["系统状态"])
def get_system_status(): return SYSTEM_STATUS

@app.get("/get_image_by_id/{image_id}", tags=["核心功能"])
def get_image_by_id(image_id: int, db: sqlite3.Connection = Depends(get_db)):
    try:
        cursor = db.cursor()
        row = cursor.execute("SELECT image_path FROM images WHERE id = ?", (image_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="数据库中未找到该图片ID")
        
        full_path = config.BASE_DATA_DIR / row['image_path']
        if not full_path.is_file():
            raise HTTPException(status_code=404, detail=f"图片文件在磁盘上未找到: {row['image_path']}")
        
        with open(full_path, "rb") as f:
            image_bytes = f.read()
        
        ext = Path(row['image_path']).suffix.lower()
        media_type = "image/jpeg" if ext in ['.jpg', '.jpeg'] else "image/png"
        
        return Response(content=image_bytes, media_type=media_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取图片时出错: {e}")

@app.post("/analyze-image", tags=["核心功能"], summary="上传图片进行全自动分析打标")
def analyze_uploaded_image(request: Request, file: UploadFile = File(...), confidence_threshold: float = Form(0.5)):
    if not request.app.state.inference_system: raise HTTPException(503, "推理系统尚未初始化。")
    try:
        pil_image = Image.open(file.file).convert("RGB")
        analysis_result = request.app.state.inference_system.analyze_image(pil_image)
        if not analysis_result: raise HTTPException(500, "图片分析失败。")
        analysis_result["visualized_image_base64"] = create_visualized_image(pil_image, analysis_result, confidence_threshold)
        return analysis_result
    except Exception as e: raise HTTPException(500, f"处理图片时发生未知错误: {str(e)}")

@app.get("/search", tags=["核心功能"], summary="按风格、空间等标签筛选图片")
def search_images(style: Optional[str] = None, room_type: Optional[str] = None, page: int = 1, size: int = 20, db: sqlite3.Connection = Depends(get_db)):
    sql_params = []
    query_parts = []
    
    if style:
        query_parts.append("style = ?")
        sql_params.append(style)
    if room_type:
        query_parts.append("room_type = ?")
        sql_params.append(room_type)
        
    base_query = "SELECT id, image_path, style, room_type FROM images"
    if query_parts:
        base_query += " WHERE " + " AND ".join(query_parts)
    
    try:
        cursor = db.cursor()
        count_query_base = base_query.split(" ORDER BY ")[0]
        count_query = f"SELECT COUNT(*) FROM ({count_query_base})"
        total = cursor.execute(count_query, sql_params).fetchone()[0]
        paginated_query = base_query + " ORDER BY id DESC LIMIT ? OFFSET ?"
        full_sql_params = sql_params + [size, (page - 1) * size]
        cursor.execute(paginated_query, full_sql_params)
        rows = cursor.fetchall()
        return {"total_results": total, "page": page, "page_size": size, "results": [dict(row) for row in rows]}
    
    except Exception as e:
        print(f"!!! 数据库查询出错: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"查询数据库时发生严重错误: {e}")

@app.get("/get-filter-options", tags=["核心功能"], summary="获取所有可用的筛选标签")
def get_filter_options(db: sqlite3.Connection = Depends(get_db)):
    try:
        styles = [row['style'] for row in db.execute("SELECT DISTINCT style FROM images WHERE style IS NOT NULL ORDER BY style").fetchall()]
        room_types = [row['room_type'] for row in db.execute("SELECT DISTINCT room_type FROM images WHERE room_type IS NOT NULL ORDER BY room_type").fetchall()]
        return {"styles": styles, "room_types": room_types}
    except Exception as e: raise HTTPException(status_code=500, detail=f"获取筛选选项失败: {e}")

@app.post("/analyze-batch", tags=["批量处理"], summary="提交一个ZIP压缩包进行批量分析")
async def analyze_batch_submit(request: Request, background_tasks: BackgroundTasks, confidence_threshold: float = Form(0.5), file: UploadFile = File(...)):
    if file.content_type not in ["application/zip", "application/x-zip-compressed"]: raise HTTPException(status_code=400, detail=f"文件类型错误，需要ZIP，但收到的是: {file.content_type}")
    if not request.app.state.inference_system: raise HTTPException(503, "推理系统尚未初始化。")
    zip_contents = await file.read()
    task_id = str(uuid.uuid4()); BATCH_TASKS[task_id] = {"status": "pending"}
    background_tasks.add_task(process_zip_file_in_background, task_id, zip_contents, confidence_threshold, request.app.state.inference_system)
    return {"message":"批量分析任务已成功提交。", "task_id": task_id}

@app.get("/batch-status/{task_id}", tags=["批量处理"], summary="查询批量分析任务的状态和进度")
def get_batch_status(task_id: str):
    task = BATCH_TASKS.get(task_id)
    if not task: raise HTTPException(status_code=404, detail="任务ID未找到。")
    return {"task_id": task_id, "status": task.get('status'), "progress": task.get('progress')}

@app.get("/batch-results/{task_id}", tags=["批量处理"], summary="获取批量分析任务的最终结果")
def get_batch_results(task_id: str, page: int = Query(1, ge=1), size: int = Query(5, ge=1)):
    task = BATCH_TASKS.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务ID未找到。")
    if task.get('status') != 'complete':
        raise HTTPException(status_code=400, detail=f"任务尚未完成, 当前状态: {task.get('status')}")
    
    all_results = task.get('results', [])
    total = len(all_results)
    start_index = (page - 1) * size
    end_index = start_index + size
    paginated_results = all_results[start_index:end_index]
    
    return {
        "task_id": task_id, 
        "total_results": total,
        "page": page,
        "page_size": size,
        "total_pages": math.ceil(total / size) if size > 0 else 0,
        "results": paginated_results
    }

@app.get("/search-text", tags=["核心功能"], summary="通过自然语言描述进行智能搜索")
def search_images_by_text(request: Request, query: str, size: int = 10, db: sqlite3.Connection = Depends(get_db)):
    if not request.app.state.semantic_search_system: raise HTTPException(503, "语义搜索功能尚未初始化...")
    try:
        search_system = request.app.state.semantic_search_system
        filter_conditions = {}
        for room_type in search_system.known_room_types:
            if room_type in query: filter_conditions['room_type'] = room_type
        for style in search_system.known_styles:
            if style in query: filter_conditions['style'] = style
        db_ids = search_system.search(query, k=size, db=db, filter_dict=filter_conditions)
        if not db_ids: return {"query": query, "results": []}
        id_placeholders = ','.join('?' for _ in db_ids)
        rows = db.execute(f"SELECT * FROM images WHERE id IN ({id_placeholders})", db_ids).fetchall()
        results_dict = {row['id']: dict(row) for row in rows}
        sorted_results = [results_dict[id] for id in db_ids if id in results_dict]
        return {"query": query, "results": sorted_results}
    except Exception as e: raise HTTPException(500, f"语义搜索失败: {e}")
    
@app.post("/generate-from-floorplan", tags=["核心功能 - AI设计"])
async def generate_from_floorplan_api(request: Request, prompt: str = Form(...), negative_prompt: str = Form(""), guidance_scale: float = Form(7.5),
                                     num_steps: int = Form(25), seed: int = Form(-1), is_panorama: bool = Form(False), file: UploadFile = File(...)):
    if request.app.state.floorplan_generation_system is None:
        try:
            request.app.state.floorplan_generation_system = FloorplanGenerationSystem()
        except Exception as e: import traceback; traceback.print_exc(); raise HTTPException(503, f"户型图AI设计引擎ds加载失败: {e}")
    try:
        floorplan_image = Image.open(io.BytesIO(await file.read())).convert("RGB")
        generated_image = request.app.state.floorplan_generation_system.generate(floorplan_image=floorplan_image, prompt=prompt, negative_prompt=negative_prompt, guidance_scale=guidance_scale, num_steps=num_steps, seed=seed, is_panorama=is_panorama)
        img_str = base64.b64encode(pil_image_to_bytes(generated_image)).decode()
        return {"generated_image_base64": f"data:image/png;base64,{img_str}"}
    except Exception as e: import traceback; traceback.print_exc(); raise HTTPException(500, f"从户型图生成时发生错误: {e}")
    
@app.post("/run-indexing", tags=["数据管理"], summary="手动触发后台数据索引")
def trigger_indexing(request: Request):
    if SYSTEM_STATUS['status'].startswith('indexing') or SYSTEM_STATUS['status'] == 'initializing': raise HTTPException(status_code=409, detail=f"任务已在进行中: {SYSTEM_STATUS['message']}")
    if not request.app.state.inference_system: raise HTTPException(status_code=503, detail="智能分析系统尚未初始化...")
    print("INFO: 手动触发全量初始化任务...")
    thread = threading.Thread(target=run_full_setup_in_background, args=(request.app,), daemon=True); thread.start()
    return {"message": "手动数据索引和向量构建任务已在后台开始。"}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="创居AI - 后端API服务")
    parser.add_argument("--host", default=config.API_HOST)
    parser.add_argument("--port", default=config.API_PORT, type=int)
    args = parser.parse_args()
    uvicorn.run("3_final_system_api:app", host=args.host, port=args.port, reload=False, lifespan="on")