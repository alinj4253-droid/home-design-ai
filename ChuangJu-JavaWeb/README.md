# 创居AI - 智能家居设计平台

欢迎来到创居AI项目！这是一个功能强大的智能家居设计与分析平台，利用深度学习和计算机视觉技术，为家居设计提供全方位的AI解决方案。

本项目最初使用 Streamlit 作为前端原型，现已成功重构为基于 **Vue 3** 和 **Spring Boot** 的现代化Web应用，实现了前后端分离的专业级架构。

## ✨ 项目特色

- **四大核心功能模块**:
  - **智能打标**: 自动分析家居图片，识别空间类型、设计风格以及关键家具（床、沙发、椅子）的风格。支持单图、多图及ZIP包批量处理。
  - **图库检索**: 基于风格、空间等标签对海量图库进行快速筛选和可视化浏览。
  - **自然语言搜索**: 通过自然语言描述（如“一个舒适温馨的奶油风卧室”）智能检索相关设计图片。
  - **户型图AI设计**: 上传简单的户型图或线条草图，结合文字描述，利用ControlNet和Stable Diffusion技术生成照片级效果图或360°全景图。
- **现代化技术栈**:
  - **AI后端**: Python, FastAPI, PyTorch, Diffusers, YOLOv8, Sentence Transformers.
  - **Web前端**: Vue 3, Vite, TypeScript, Element Plus, Pinia.
  - **服务网关/托管**: Java, Spring Boot.
- **专业级用户体验**:
  - 采用企业级中后台布局，界面美观，交互流畅。
  - 异步任务处理与实时进度反馈，提升用户等待体验。
  - 响应式设计，适配不同屏幕尺寸。

## 🏛️ 项目架构

本项目采用完全的前后端分离架构：

1.  **AI后端 (`/AI` 目录)**:
    - 运行在 **Python 3.10** 环境。
    - 使用 **FastAPI** 提供所有AI计算和数据查询的 RESTful API。
    - 负责所有模型推理（图像分类、目标检测、文本编码、图像生成）。
    - 数据库使用 **SQLite**，向量索引使用 **Faiss**。

2.  **前端 (`/chuangju-ai-frontend` 目录)**:
    - 运行在 **Node.js 18+** 环境。
    - 使用 **Vue 3** 构建的单页应用（SPA）。
    - 负责所有用户界面的展示和交互。
    - 通过HTTP请求调用AI后端的API。

3.  **Java服务网关 (`/chuangju-ai-portal` 目录)**:
    - 运行在 **Java 17** 环境。
    - 使用 **Spring Boot** 构建。
    - 主要职责是托管Vue前端构建出的静态文件。在生产环境中，它使得整个Web应用可以被打包成一个独立的`.jar`文件，方便一键部署。


## 🚀 环境部署与启动步骤

要成功运行本项目，您需要分别配置 **AI后端** 和 **Web端 (前端 + Java服务)** 的环境。

### 0. 基础环境安装 (系统级依赖)

这些是运行本项目所必需的底层软件。请在开始之前，确保您的系统中已安装并配置好它们。

#### a. Java Development Kit (JDK) & Maven

- **作用**: 用于运行 Spring Boot 服务网关，它负责托管前端应用。
- **要求**: Java 17+, Maven 3.6+
- **在 Ubuntu/Debian 上的安装命令**:
  ```bash
  # 1. 更新包列表
  sudo apt update
  
  # 2. 安装 OpenJDK 17 和 Maven
  sudo apt install -y openjdk-17-jdk maven
  
  # 3. 验证安装
  java -version
  mvn -v
b. Node.js & npm
作用: 用于构建和运行 Vue 前端项目。npm 是 Node.js 的包管理器。
要求: Node.js 18+
在 Ubuntu/Debian 上的推荐安装方式 (使用 nvm):
code
Bash
# 1. 安装 nvm (Node Version Manager)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash

# 2. 使 nvm 生效 (需要重启终端，或运行 source ~/.bashrc)
source ~/.bashrc

# 3. 使用 nvm 安装最新的 LTS (长期支持) 版本的 Node.js
nvm install --lts

# 4. 验证安装 (npm 会随 Node.js 自动安装)
node -v
npm -v
c. Python & Pip
作用: 用于运行 FastAPI AI 后端服务。
要求: Python 3.10+
在 Ubuntu 22.04+ 上的安装:
Ubuntu 22.04 通常自带 Python 3.10。您可以通过 python3 --version 来验证。
d. (可选) NVIDIA CUDA Toolkit
作用: 如果您希望使用“户型图AI设计”功能，必须安装 NVIDIA 显卡驱动和对应版本的 CUDA。
要求: CUDA 11.8+
安装: 请遵循 NVIDIA 官方文档 进行安装。
1. 启动 AI 后端
AI后端是所有功能的核心，必须首先启动。
进入AI后端项目目录:
cd ~/AI/AI
创建虚拟环境并安装Python依赖:
requirements.txt 文件列出了所有需要通过 pip 安装的 Python 库。
# (推荐) 创建并激活Python虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装所有Python依赖包
pip install -r requirements.txt
注意: requirements.txt 中的 torch 库需要您根据 CUDA 版本手动安装。请访问 PyTorch 官网获取正确的安装命令。
下载AI模型:
请确保所有必要的AI模型文件（如YOLOv8, Stable Diffusion, ControlNet, LoRA等）已下载并放置在正确的目录（如 models, loras等）。
启动FastAPI服务:
uvicorn 3_final_system_api:app --host 127.0.0.1 --port 8000
当您看到 Uvicorn running on http://127.0.0.1:8000 时，表示AI后端已成功启动。
2. 启动前端 (开发模式)
前端提供了用户交互界面。
进入前端项目目录:
cd ~/AI/chuangju-ai-frontend
安装Node.js依赖:
package.json 文件列出了所有需要通过 npm 安装的前端库。
# (如果遇到网络问题，请先取消代理)
# unset http_proxy
# unset https_proxy
npm install
启动Vite开发服务器:
npm run dev
当您看到 Local: http://localhost:5173/ 时，表示前端开发服务器已成功启动。
3. 访问应用
打开您的浏览器，访问前端开发服务器提供的地址：http://localhost:5173/
现在，您应该可以看到“创居AI”的界面，并可以开始使用了。
附：依赖包文件说明
本项目涉及三个主要的依赖管理文件，它们列出了所有需要下载的项目级安装包：
AI/requirements.txt:
管理者: pip (Python)
内容: fastapi, torch, diffusers, numpy 等所有 Python 后端库。
安装命令: pip install -r requirements.txt
chuangju-ai-frontend/package.json:
管理者: npm (Node.js)
内容: vue, element-plus, axios, pinia 等所有前端库。
安装命令: npm install
chuangju-ai-portal/pom.xml:
管理者: Maven (Java)
内容: spring-boot-starter-web 等所有 Java 后端库。
安装方式: Maven 会在执行命令（如 mvn spring-boot:run）时自动下载。