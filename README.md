# 创居AI - 智能家居设计辅助平台

## 项目介绍

本项目由四大核心功能模块构成，形成了一个从理解、检索到创造的完整服务闭环：

### 智能打标

作为平台的数据基石，此模块运用多任务学习和目标检测技术，实现了对家居图片的自动化、多维度深度解析。用户上传图片后，系统能精准识别出其房间类型、整体设计风格，并检测出核心家具及其局部风格。

### 标签库检索

基于后台海量的已标注数据，用户可以通过**“空间类型 + 设计风格”**的组合进行精确筛选，快速定位到符合自己偏好的高品质设计案例图库，解决了传统模式下寻找灵感效率低下的问题。

### 自然语言搜索

为了提供更自然、更人性化的交互体验，本模块引入了语义理解能力。用户无需学习复杂的筛选逻辑，只需用一句日常语言（如“我想找找温馨的奶油风卧室”）描述需求，系统即可通过文本向量化和向量相似度搜索技术，精准理解用户意图，并返回最相关的设计图片。

### 户型图AI设计

这是本项目的核心创新功能，实现了从抽象到具象的革命性跨越。用户仅需上传一张简单的二维户型图或线条草图，并配以详细的文字描述，系统即可利用先进的ControlNet技术和高质量的渲染模型，一键生成一张与户型结构完全匹配、符合用户描述的照片级真实感效果图，将用户的创意和想法直观地呈现出来。

## 数据集构成

本项目使用的原始训练数据存放于 `datasets` 文件夹中，需遵循特定的层级结构以便于数据处理脚本（`1_prepare_all_data.py`）正确读取。结构如下：

```
datasets/
├── 房间类型1/  
│   ├── 风格1/  
│   │   ├── image_01.jpg
│   │   └── image_02.png
│   └── 风格2/  
│       └── ...
├── 房间类型2/  
│   ├── 风格1/
│   │   └── ...
│   └── ...
└── ...
```

## 命令行操作指南

请按照以下步骤在命令行中完成项目的环境配置、模型准备与启动。

### 步骤一：环境准备

**创建并激活Python 3.9环境：**

```bash
conda create --name AI python=3.9 -y
conda activate AI
```

### 步骤二：安装项目依赖

1. **安装依赖** :

```bash
pip install -r requirements.txt
```

2. **安装PyTorch**:

```bash
pip install torch-2.1.2+cu118-cp39-cp39-win_amd64.whl --no-dependencies --force-reinstall
pip install torchvision-0.16.2+cu118-cp39-cp39-win_amd64.whl --no-dependencies --force-reinstall
pip install torchaudio-2.1.2+cu118-cp39-cp39-win_amd64.whl --no-dependencies --force-reinstall
```

### 步骤三：数据处理与模型训练

1. **数据预处理** (处理 `datasets` 文件夹中的图片，生成标注文件):

```bash
python 1_prepare_all_data.py
```

2. **模型训练** (训练智能打标所需的分类模型):

```bash
python 2_train_all_models.py

# 只训练全局模型 (房间类型 + 整体风格)
python 2_train_all_models.py --module main

# 只训练所有局部模型 (床、沙发、椅子)
python 2_train_all_models.py --module sideline

# 只训练某个特定的局部模型
# "床" 模型
python 2_train_all_models.py --module sideline --furniture_type bed
# "沙发" 模型
python 2_train_all_models.py --module sideline --furniture_type sofa
# "椅子" 模型
python 2_train_all_models.py --module sideline --furniture_type chair
```

### 步骤四：启动项目

1. **启动后端服务**

```bash
# 在终端窗口 1 中运行
linux系统：export HF_ENDPOINT=https://hf-mirror.com
windows系统：$env:HF_ENDPOINT="https://hf-mirror.com"
python 3_final_system_api.py
```

2. **启动前端界面**:

```bash
# 在终端窗口 2 中运行
streamlit run 4_streamlit_ui.py
```

3. **访问应用**:
      - 打开浏览器，访问终端中提示的地址 `http://localhost:8501`
