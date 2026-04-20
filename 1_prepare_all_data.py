# 1_prepare_all_data.py

import os
import json
import random
import argparse
from tqdm import tqdm
from pathlib import Path
import cv2
from ultralytics import YOLO
import config
from multiprocessing import Pool, cpu_count
import multiprocessing as mp
from multiprocessing import Pool, cpu_count, set_start_method

yolo_model = None

def init_worker(model_path):
    """
    多进程工作单元（Worker）的初始化函数。
    此函数会在每个子进程启动时被调用一次。
    """
    global yolo_model
    yolo_model = YOLO(model_path)

def process_single_image_for_cropping(task_args):
    """
    这是执行具体裁剪任务的函数，被每个子进程调用。
    它处理单张图片，检测、裁剪并保存家具。
    """
    global yolo_model
    ann, base_data_dir, output_set_dir, yolo_mapping, target_furniture, min_size = task_args

    image_path = base_data_dir / ann['image_path']
    if not image_path.exists():
        return 0

    crop_count = 0
    try:
        image = cv2.imread(str(image_path))
        if image is None:
            return 0

        results = yolo_model(image, conf=0.6, verbose=False)
        
        if results:
            for i, res in enumerate(results):
                for box in res.boxes:
                    class_name = res.names[int(box.cls[0])].lower()
                    if class_name in yolo_mapping:
                        f_type = yolo_mapping[class_name]
                        if f_type in target_furniture:
                            x1, y1, x2, y2 = map(int, box.xyxy[0])
                            if (x2 - x1) < min_size or (y2 - y1) < min_size:
                                continue
                            
                            cropped_image = image[y1:y2, x1:x2]
                            
                            save_folder = output_set_dir / f_type / ann['style']
                            save_folder.mkdir(parents=True, exist_ok=True)
                            
                            save_path = save_folder / f"{image_path.stem}_{f_type}_{i}_{int(box.cls[0])}.png"
                            cv2.imwrite(str(save_path), cropped_image)
                            crop_count += 1
    except Exception:
        return 0
    return crop_count

def process_fully_labeled_data(data_dir: Path, val_split: float, output_dir: Path):
    print(f"\n--- 主线任务: 正在处理双标签数据集: {data_dir} ---")
    all_annotations = []
    supported_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.webp', '.JPG', '.JPEG', '.PNG']
    room_type_folders = [d for d in data_dir.iterdir() if d.is_dir()]
    
    for room_type_path in tqdm(room_type_folders, desc="扫描房间类型"):
        style_folders = [d for d in room_type_path.iterdir() if d.is_dir()]
        for style_path in style_folders:
            for image_file in style_path.iterdir():
                if image_file.suffix.lower() in supported_extensions:
                    all_annotations.append({
                        "image_path": str(image_file.relative_to(data_dir)),
                        "style": style_path.name, "room_type": room_type_path.name
                    })
    
    print(f"双标签数据集总计找到 {len(all_annotations)} 张图片。")
    random.shuffle(all_annotations)
    split_idx = int(len(all_annotations) * (1 - val_split))
    train_ann, val_ann = all_annotations[:split_idx], all_annotations[split_idx:]
    print(f"分割后 - 训练集: {len(train_ann)} | 验证集: {len(val_ann)}")
    
    main_task_dir = output_dir / 'main_task'
    main_task_dir.mkdir(parents=True, exist_ok=True)
    with open(main_task_dir / 'train_multitask.json', 'w', encoding='utf-8') as f:
        json.dump(train_ann, f, indent=2, ensure_ascii=False)
    with open(main_task_dir / 'val_multitask.json', 'w', encoding='utf-8') as f:
        json.dump(val_ann, f, indent=2, ensure_ascii=False)
    print(f"主线任务标注文件已保存至: {main_task_dir}")
    
    return train_ann, val_ann

def generate_local_dataset_parallel(base_data_dir: Path, train_main_ann: list, val_main_ann: list, output_data_dir: Path):
    """
    使用多进程并行生成局部家具数据集。
    此函数处理来自训练集和验证集的图片，并将裁剪图保存到对应的 train/val 子目录中。
    """
    print(f"\n--- 副线任务: 开始生成局部家具数据集 ---")
    target_furniture = ['bed', 'sofa', 'chair']
    yolo_mapping = {'bed': 'bed', 'chair': 'chair', 'couch': 'sofa'}
    min_size = 50
    model_path = 'yolov8n.pt'

    train_output_dir = output_data_dir / 'train'
    val_output_dir = output_data_dir / 'val'
    train_output_dir.mkdir(parents=True, exist_ok=True)
    val_output_dir.mkdir(parents=True, exist_ok=True)

    train_tasks = [(ann, base_data_dir, train_output_dir, yolo_mapping, target_furniture, min_size) for ann in train_main_ann]
    val_tasks = [(ann, base_data_dir, val_output_dir, yolo_mapping, target_furniture, min_size) for ann in val_main_ann]
    all_tasks = train_tasks + val_tasks
    
    num_processes = max(1, cpu_count() - 2)
    print(f"将使用 {num_processes} 个进程进行并行处理...")

    total_crops = 0
    with Pool(processes=num_processes, initializer=init_worker, initargs=(model_path,)) as pool:
        with tqdm(total=len(all_tasks), desc="并行裁剪家具") as pbar:
            for num_cropped in pool.imap_unordered(process_single_image_for_cropping, all_tasks, chunksize=20):
                total_crops += num_cropped
                pbar.update(1)

    print(f"局部家具数据集生成完成！总计生成 {total_crops} 张图片，保存在: {output_data_dir}")

def process_local_data(data_dir: Path, output_dir: Path):
    """
    为生成的局部数据集创建标注
    """
    print(f"\n--- 副线任务: 正在为生成的局部数据集创建标注: {data_dir} ---")
    sideline_task_dir = output_dir / 'sideline_task'
    sideline_task_dir.mkdir(parents=True, exist_ok=True)
    supported_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.webp']

    for split_type in ['train', 'val']:
        print(f"处理 {split_type} 集合...")
        split_annotations = []
        split_dir = data_dir / split_type
        if not split_dir.exists():
            print(f"警告: 未找到 {split_dir} 目录，跳过。")
            continue

        furniture_folders = [d for d in split_dir.iterdir() if d.is_dir()]
        for f_path in tqdm(furniture_folders, desc=f"处理家具类别 ({split_type})"):
            style_folders = [d for d in f_path.iterdir() if d.is_dir()]
            for s_path in style_folders:
                for img_file in s_path.iterdir():
                    if img_file.suffix.lower() in supported_extensions:
                        split_annotations.append({
                            "image_path": str(img_file.relative_to(data_dir)),
                            "style": s_path.name,
                            "furniture_type": f_path.name
                        })
        
        print(f"{split_type.capitalize()} 集总计找到 {len(split_annotations)} 张局部图片。")
        random.shuffle(split_annotations) 

        output_filename = sideline_task_dir / f'{split_type}_local.json'
        with open(output_filename, 'w', encoding='utf-8') as f:
            json.dump(split_annotations, f, indent=2, ensure_ascii=False)
            
    print(f"副线任务标注文件已保存至: {sideline_task_dir}")


def main():
    parser = argparse.ArgumentParser(description="第一步：数据准备")
    parser.add_argument('--data_dir', type=str, default=str(config.BASE_DATA_DIR), help='数据集根目录路径')
    parser.add_argument('--annotations_output_dir', type=str, default=str(config.ANNOTATIONS_OUTPUT_DIR), help='JSON标注文件输出目录')
    parser.add_argument('--generated_local_dir', type=str, default=str(config.GENERATED_LOCAL_DIR), help='裁剪后家具图片输出目录')
    parser.add_argument('--val_split', type=float, default=config.VAL_SPLIT, help='验证集比例')
    args = parser.parse_args()
    
    random.seed(42)
    
    # 1. 处理主线任务数据，并获得严格分割的训练/验证集列表
    train_main_ann, val_main_ann = process_fully_labeled_data(Path(args.data_dir), args.val_split, Path(args.annotations_output_dir))
    
    # 2. 将分割好的列表传入并行处理函数，生成同样分割的局部家具图片
    generate_local_dataset_parallel(Path(args.data_dir), train_main_ann, val_main_ann, Path(args.generated_local_dir))
    
    # 3. 为新生成的、已分割好的局部图片创建标注文件
    process_local_data(Path(args.generated_local_dir), Path(args.annotations_output_dir))

    print("\n 数据准备工作已全部完成！")

if __name__ == '__main__':
    try:
        mp.set_start_method('spawn', force=True)
        print("多进程启动方式已成功设置为 'spawn'，以确保GPU兼容性。")
    except RuntimeError:
        pass
    main()