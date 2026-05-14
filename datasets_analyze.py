# datasets_analyze.py

import os
from pathlib import Path
from collections import defaultdict
import config

def analyze_dataset_composition():
    """
    分析数据集构成，打印每个房间类型下各种风格的图片数量。
    """
    print("--- 正在分析数据集构成 ---")
    
    SUPPORTED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.bmp', '.webp', '.JPG', '.JPEG', '.PNG']
    
    base_dir = config.BASE_DATA_DIR
    if not base_dir.exists():
        print(f"错误：数据集目录 '{base_dir}' 不存在，请检查config.py中的路径。")
        return

    data_composition = defaultdict(lambda: defaultdict(int))
    total_images_found = 0

    # --- 1. 数据收集 ---
    for room_type_path in sorted(base_dir.iterdir()):
        if room_type_path.is_dir():
            room_type = room_type_path.name
            for style_path in sorted(room_type_path.iterdir()):
                if style_path.is_dir():
                    style = style_path.name
                    
                    image_count = len([
                        f for f in style_path.iterdir() 
                        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
                    ])
                    
                    if image_count > 0:
                        data_composition[room_type][style] = image_count
                        total_images_found += image_count

    if not data_composition:
        print("警告：在数据集中没有找到任何符合结构的图片，请检查目录和文件。")
        return

    # --- 2. 按层级打印详细分布 ---
    print(f"\n 数据集构成详细分析 (共计: {total_images_found} 张图片)")
    print("="*50)

    room_totals = {room: sum(styles.values()) for room, styles in data_composition.items()}

    for room_type, styles in sorted(data_composition.items()):
        print(f"\n 房间类型: {room_type} (总计: {room_totals[room_type]} 张)")
        for style, count in sorted(styles.items()):
            print(f"    - {style}: {count} 张")
            
    print("\n" + "="*50)
    print("\n--- 分析完成 ---\n")


if __name__ == "__main__":
    analyze_dataset_composition()