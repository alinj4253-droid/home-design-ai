# 4_streamlit_ui.py

import streamlit as st
import requests
import base64
import io
import time
import zipfile
import math
from PIL import Image
from streamlit_card import card
from streamlit_pannellum import streamlit_pannellum
from streamlit_autorefresh import st_autorefresh
import config

st.set_page_config(page_title="创居AI - 智能家居设计平台", page_icon="🎨", layout="wide")

st.markdown("""
<style>
    /* 删除Streamlit页脚和汉堡菜单 */
    .st-emotion-cache-1c7gzgp, .st-emotion-cache-h4xjwg, footer { display: none; }
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    html, body, [class*="st-"] { font-size: 16px; }
    h1 { font-size: 2.5em !important; }
    h2 { font-size: 2em !important; }
    h3 { font-size: 1.5em !important; }
    .analysis-summary { background-color: #FFFBEA; border-left: 6px solid #DC143C; padding: 1rem 1.25rem; margin: 1rem 0; border-radius: 8px; font-size: 1.2em; color: #DC143C; font-weight: 500; }
    .analysis-summary b { color: #333; }
    [data-testid="stVerticalBlock"] .card-frame { border-radius: 10px; border: 1px solid #e6e6e6; box-shadow: 0 4px 8px rgba(0,0,0,0.08); transition: transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out; }
    [data-testid="stVerticalBlock"] .card-frame:hover { transform: translateY(-5px); box-shadow: 0 8px 16px rgba(0,0,0,0.12); }
</style>
""", unsafe_allow_html=True)

API_BASE_URL = f"http://127.0.0.1:{config.API_PORT}"

# --- 会话状态初始化 ---
session_keys = {
    'system_status': 'unknown', 'is_initializing': True, 'analysis_results': None,
    'batch_task_id': None, 'generated_floorplan_result': None,
    'gallery_search_results': None, 'gallery_page_num': 1, 'gallery_total_pages': 0,
    'nlp_search_results': None, 'nlp_images_shown': 5,
    'dialog_info': None,
    'gallery_style_last_run': "所有风格",
    'gallery_room_type_last_run': "所有空间",
    'batch_analysis_page': 1,
}
for key, default_value in session_keys.items():
    if key not in st.session_state:
        st.session_state[key] = default_value

# --- 辅助函数 ---
@st.cache_data(ttl=600)
def get_filter_options():
    try:
        response = requests.get(f"{API_BASE_URL}/get-filter-options", timeout=5)
        if response.status_code == 200:
            return (response.json().get("styles", []), response.json().get("room_types", []))
    except requests.exceptions.RequestException:
        pass
    return ([], [])

def display_analysis_result(result_data, confidence_threshold):
    main_analysis = result_data.get("main_task_analysis", {})
    high_conf_objs = [o for o in result_data.get("sideline_task_analysis", []) if o.get('style_confidence', 0) >= confidence_threshold]
    summary_parts = [main_analysis.get("predicted_room_type"), main_analysis.get("predicted_style")]
    if high_conf_objs:
        summary_parts.extend([f"{obj['furniture_type']}-{obj['predicted_style']}" for obj in high_conf_objs])
    summary_text = " | ".join(filter(None, summary_parts))
    st.markdown(f"<div class='analysis-summary'><b>分析摘要</b>: {summary_text}</div>", unsafe_allow_html=True)
    if result_data.get('visualized_image_base64'):
        st.image(result_data['visualized_image_base64'], caption="AI标注的可视化结果", use_container_width=True)
    with st.expander("查看详细JSON数据"):
        st.json(result_data)

@st.dialog("图片详情")
def show_detail_dialog(item_info):
    image_url = f"{API_BASE_URL}/get_image_by_id/{item_info['id']}"
    st.image(image_url, caption="高清大图", use_container_width=True)
    st.markdown(f"#### **风格**: {item_info['style']}")
    st.markdown(f"#### **空间**: {item_info['room_type']}")

def clear_dialog_state_on_tab_change():
    st.session_state.dialog_info = None

st.title("🎨 创居AI - 智能家居设计平台")
status_map = {
    "ready": ("success", "✅ 系统就绪, 所有功能可用。"),
    "initializing": ("info", "⏳ 系统首次启动, 正在后台初始化数据... (页面将自动刷新)"),
}
status_type, status_text = status_map.get(st.session_state.system_status, ("warning", "⚠️ 未知系统状态。"))
st.caption(status_text)
is_ready = st.session_state.system_status == 'ready'

# --- 全局状态管理 ---
if st.session_state.is_initializing:
    st_autorefresh(interval=3000, key="global_status_refresher")
try:
    status_res = requests.get(f"{API_BASE_URL}/system-status", timeout=2)
    if status_res.status_code == 200:
        status_code = status_res.json().get('status', 'unknown')
        if st.session_state.system_status != status_code:
            st.session_state.system_status = status_code
        st.session_state.is_initializing = status_code not in ['ready', 'failed', 'api_down']
    else:
        st.session_state.system_status = 'api_down'
        st.session_state.is_initializing = False
except requests.exceptions.RequestException:
    if st.session_state.system_status != 'api_down':
        st.session_state.system_status = 'api_down'
    st.session_state.is_initializing = False


tab_options = ["**🔍 智能打标**", f"**{'🖼️' if is_ready else '⏳'} 图库检索**",
               f"**{'💬' if is_ready else '⏳'} 自然语言搜索**", "**✨ 户型图AI设计**"]

active_tab = st.radio("选择功能", tab_options, index=0, horizontal=True)

if active_tab != st.session_state.get("last_tab", None):
    clear_dialog_state_on_tab_change()
    st.session_state.last_tab = active_tab

if active_tab == "**🔍 智能打标**":
    with st.container():
        st.header("智能分析与批量打标")
        st.info("您可以上传单张图片、多张图片或ZIP压缩包，系统将智能地进行处理。")

        def clear_analysis_state():
            st.session_state.analysis_results = None
            st.session_state.batch_task_id = None

    confidence_threshold = st.slider("设置局部风格的置信度阈值：", 0.1, 1.0, 0.5, 0.05, key="tag_slider")
    uploaded_files = st.file_uploader(
        "拖拽文件到此处", 
        type=['png', 'jpg', 'jpeg', 'zip'], 
        accept_multiple_files=True, 
        key="tag_uploader",
        on_change=clear_analysis_state
    )

    if st.button("开始分析", use_container_width=True, type="primary", key="tag_button"):
        clear_analysis_state()
        if not uploaded_files:
            st.warning("请先上传文件。")
        else:
            image_files = [f for f in uploaded_files if not f.name.lower().endswith('.zip')]
            zip_files = [f for f in uploaded_files if f.name.lower().endswith('.zip')]

            if len(image_files) == 1 and not zip_files:
                with st.spinner("正在分析单张图片..."):
                    files = {'file': (image_files[0].name, image_files[0].getvalue(), image_files[0].type)}
                    try:
                        response = requests.post(
                            f"{API_BASE_URL}/analyze-image", 
                            files=files, 
                            data={'confidence_threshold': confidence_threshold}, 
                            timeout=120
                        )
                        if response.status_code == 200:
                            st.success("🎉 分析完成！")
                            st.session_state.analysis_results = {"type": "single", "data": response.json()}
                        else:
                            st.error(f"分析失败: {response.text}")
                    except requests.exceptions.RequestException as e:
                        st.error(f"请求后端服务时发生错误: {e}")
            else:
                with st.spinner("正在准备并提交批量分析任务..."):
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, 'w') as zf:
                        for file in image_files:
                            zf.writestr(file.name, file.getvalue())
                        for zip_file in zip_files:
                            with zipfile.ZipFile(zip_file, 'r') as user_zip:
                                for item_name in user_zip.namelist():
                                    if item_name.lower().endswith(('.png', '.jpg', '.jpeg')) and not item_name.startswith('__MACOSX/'):
                                        zf.writestr(item_name, user_zip.read(item_name))
                    zip_buffer.seek(0)
                    files = {'file': ('batch_upload.zip', zip_buffer, 'application/zip')}
                    try:
                        submit_response = requests.post(
                            f"{API_BASE_URL}/analyze-batch", 
                            files=files, 
                            data={'confidence_threshold': confidence_threshold}, 
                            timeout=30
                        )
                        if submit_response.status_code == 200:
                            st.session_state.batch_task_id = submit_response.json().get('task_id')
                            st.success("🎉 批量分析任务已成功提交！")
                        else:
                            st.error(f"任务提交失败: {submit_response.json().get('detail', submit_response.text)}")
                    except requests.exceptions.RequestException as e:
                        st.error(f"请求后端服务时发生错误: {e}")

    if st.session_state.batch_task_id:
        st_autorefresh(interval=2000, key="batch_status_checker")
        try:
            status_response = requests.get(f"{API_BASE_URL}/batch-status/{st.session_state.batch_task_id}", timeout=10)
            if status_response.status_code == 200:
                res_data = status_response.json()
                status = res_data.get('status')
                if status == 'complete':
                    st.success("批量分析完成！正在准备显示结果...")
                    st.session_state.analysis_results = {"type": "batch", "task_id": st.session_state.batch_task_id}
                    st.session_state.batch_task_id = None
                    st.balloons()
                elif status in ['pending', 'processing']:
                    progress_str = res_data.get('progress', '0/1')
                    try:
                        current, total = map(int, progress_str.split('/'))
                        progress_val = current / total if total > 0 else 0
                    except (ValueError, ZeroDivisionError):
                        progress_val = 0
                    st.progress(progress_val, text=f"处理中: {progress_str}")
                elif status == 'failed':
                    st.error(f"任务处理失败: {res_data.get('error', '未知错误')}")
                    st.session_state.batch_task_id = None
                else:
                    st.error("无法获取任务状态。")
                    st.session_state.batch_task_id = None
        except requests.exceptions.RequestException:
            st.error("轮询任务状态时网络错误。")
            st.session_state.batch_task_id = None
    
    if st.session_state.analysis_results:
        st.divider()
        st.subheader("分析结果")
        results_info = st.session_state.analysis_results

        if results_info["type"] == "single":
            display_analysis_result(results_info["data"], confidence_threshold)

        elif results_info["type"] == "batch":
          task_id = results_info.get("task_id")
          if task_id:
              with st.spinner("正在获取全部分析结果..."):
                  try:
                      all_results = []
                      total_pages = 1
                      current_page = 1
                      
                      first_page_response = requests.get(f"{API_BASE_URL}/batch-results/{task_id}", params={'page': 1, 'size': 5}, timeout=60)
                      
                      if first_page_response.status_code == 200:
                          data = first_page_response.json()
                          all_results.extend(data.get('results', []))
                          total_pages = data.get('total_pages', 1)
                          
                          if total_pages > 1:
                              for page_num in range(2, total_pages + 1):
                                  st.spinner(f"正在获取第 {page_num}/{total_pages} 页结果...")
                                  next_page_response = requests.get(f"{API_BASE_URL}/batch-results/{task_id}", params={'page': page_num, 'size': 5}, timeout=60)
                                  if next_page_response.status_code == 200:
                                      all_results.extend(next_page_response.json().get('results', []))
                                  else:
                                      st.warning(f"获取第 {page_num} 页结果失败。")
                                      break 
                          
                          st.subheader(f"批量分析完成！共处理 {len(all_results)} 张图片。")
                          
                          for result_item in all_results:
                              with st.expander(f"**文件名: {result_item.get('filename')}**"):
                                  analysis_data = result_item.get('analysis', {})
                                  if analysis_data:
                                      display_analysis_result(analysis_data, confidence_threshold)
                                  else:
                                      st.warning("未能获取到此文件的有效分析数据。")
                      else:
                          st.error(f"获取分析结果失败: {first_page_response.text}")

                  except requests.exceptions.RequestException as e:
                      st.error(f"请求后端服务时发生错误: {e}")

elif active_tab.startswith("**🖼️") or active_tab.startswith("**⏳"):
    with st.container():
            st.header("图库检索")
    if not is_ready:
        st.info("⏳ 系统正在初始化数据, 请稍后使用本功能...")
    else:
        styles, room_types = get_filter_options()
        st.subheader("筛选与浏览")

        filter_col1, filter_col2 = st.columns(2)
        selected_room_type = filter_col1.selectbox("空间类型:", ["所有空间"] + room_types, key="sel_room_tab2")
        selected_style = filter_col2.selectbox("设计风格:", ["所有风格"] + styles, key="sel_style_tab2")

        if (st.session_state.gallery_style_last_run != selected_style or
            st.session_state.gallery_room_type_last_run != selected_room_type):
            clear_dialog_state_on_tab_change()
            st.session_state.gallery_page_num = 1
            st.session_state.gallery_search_results = None
            st.session_state.gallery_style_last_run = selected_style
            st.session_state.gallery_room_type_last_run = selected_room_type

        current_params = {
            k: v for k, v in {
                "style": selected_style if selected_style != "所有风格" else None,
                "room_type": selected_room_type if selected_room_type != "所有空间" else None
            }.items() if v is not None
        }

        if st.session_state.gallery_search_results is None:
            with st.spinner("正在检索图库..."):
                params = {"page": st.session_state.gallery_page_num, "size": 9, **current_params}
                try:
                    response = requests.get(f"{API_BASE_URL}/search", params=params, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        st.session_state.gallery_search_results = data
                        st.session_state.gallery_total_pages = math.ceil(data.get('total_results', 0) / 9)
                    else:
                        st.session_state.gallery_search_results = {}
                except requests.exceptions.RequestException:
                    st.session_state.gallery_search_results = {}

        if st.session_state.gallery_search_results:
            total_results = st.session_state.gallery_search_results.get('total_results', 0)
            if total_results > 0:
                if st.session_state.gallery_page_num == 1:
                    st.success(f"共找到 {total_results} 张匹配的图片。")
                
                image_items = st.session_state.gallery_search_results.get('results', [])
                for i in range(0, len(image_items), 3):
                    cols = st.columns(3)
                    for j in range(3):
                        if i + j < len(image_items):
                            with cols[j]:
                                item = image_items[i+j]
                                image_url = f"{API_BASE_URL}/get_image_by_id/{item['id']}"
                                
                                if card(
                                    title=f"{item['style']}", text=f"空间: {item['room_type']}",
                                    image=image_url, styles={"card": {"width": "100%", "height": "300px"}},
                                    key=f"gallery_{item['image_path']}"
                                ):
                                    st.session_state.dialog_info = item
            else:
                st.warning("在图库中没有找到匹配的图片。")

            if st.session_state.gallery_total_pages > 1:
                st.divider()
                def go_prev_page(): st.session_state.gallery_page_num -= 1; st.session_state.gallery_search_results = None
                def go_next_page(): st.session_state.gallery_page_num += 1; st.session_state.gallery_search_results = None
                p_cols = st.columns([2, 8, 2])
                p_cols[0].button("⬅️ 上一页", key="g_prev", on_click=go_prev_page, disabled=(st.session_state.gallery_page_num <= 1))
                p_cols[2].button("下一页 ➡️", key="g_next", on_click=go_next_page, disabled=(st.session_state.gallery_page_num >= st.session_state.gallery_total_pages))
                p_cols[1].markdown(f"<div style='text-align: center; padding-top: 0.5em;'>第 {st.session_state.gallery_page_num} / {st.session_state.gallery_total_pages} 页</div>", unsafe_allow_html=True)

elif active_tab.startswith("**💬") or active_tab.startswith("**⏳"):
    with st.container():
            st.header("自然语言搜索")
    if not is_ready:
        st.info("⏳系统正在初始化数据, 请稍后使用本功能...")
    else:
        st.subheader("输入您的想法")
        query_text = st.text_input("例如:", placeholder="一个舒适温馨的奶油风卧室...", key="text_search_input")

        if st.button("开始智能搜索", use_container_width=True, type="primary", key="nlp_button"):
            clear_dialog_state_on_tab_change()
            st.session_state.nlp_search_results = None
            if query_text:
                with st.spinner("正在理解您的想法并检索图库..."):
                    try:
                        params_nlp = {"query": query_text, "size": 10}
                        response = requests.get(f"{API_BASE_URL}/search-text", params=params_nlp, timeout=20)
                        if response.status_code == 200:
                            data = response.json()
                            if data and isinstance(data, dict):
                                st.session_state.nlp_search_results = data.get('results', [])
                        else:
                             st.session_state.nlp_search_results = []
                    except requests.exceptions.RequestException:
                        st.session_state.nlp_search_results = []
            else:
                st.warning("请输入您的需求描述。")
        
        if st.session_state.nlp_search_results is not None:
            st.divider()
            results = st.session_state.nlp_search_results
            if not results:
                st.warning("抱歉，没有在图库中找到与您描述相关的图片。")
            else:
                st.success(f"为您找到了 {len(results)} 张最相关的图片！")
                images_to_display = results[:st.session_state.nlp_images_shown]
                for i in range(0, len(images_to_display), 3):
                    cols = st.columns(3)
                    for j in range(3):
                        if i + j < len(images_to_display):
                            with cols[j]:
                                item = images_to_display[i+j]
                                image_url = f"{API_BASE_URL}/get_image_by_id/{item['id']}"
                                
                                if card(
                                    title=f"{item['style']}", text=f"空间: {item['room_type']}",
                                    image=image_url, styles={"card": {"width": "100%", "height": "300px"}},
                                    key=f"nlp_{item['image_path']}"
                                ):
                                    st.session_state.dialog_info = item
                
                if len(results) > 5 and st.session_state.nlp_images_shown < 10:
                    st.divider()
                    _, btn_col, _ = st.columns([1, 1, 1])
                    def load_more(): st.session_state.nlp_images_shown = 10

                    btn_col.button("加载更多结果", use_container_width=True, on_click=load_more)


elif active_tab == "**✨ 户型图AI设计**":
    with st.container():
        st.header("✨ 户型图AI设计")
    st.markdown("上传一张**简单的户型图或线条草图**，用文字描述您的梦想设计，AI即可为您生成照片级效果图！")
    st.subheader("1. 上传与设定")
    floorplan_file = st.file_uploader("上传您的户型图 🏠", type=['png', 'jpg', 'jpeg'], key="floorplan_uploader")
    if floorplan_file:
        st.session_state.uploaded_floorplan = floorplan_file
    gen_mode = st.radio("选择生成模式", ["标准效果图", "3D全景图 ✨"], horizontal=True, captions=["生成一张高质量的静态图片", "生成可720°交互查看的沉浸式全景图"])
    is_panorama_mode = (gen_mode == "3D全景图 ✨")
    st.subheader("2. 描绘您的创意 ✍️")
    prompt_example = "一张现代简约风格的客厅效果图，拥有巨大的落地窗和充足的自然光，白色的墙壁，浅灰色布艺沙发，搭配原木色电视柜和茶几，地板为浅色木地板，点缀有绿植，整体氛围明亮、舒适、温馨，电影级光照，照片级真实感，8k画质。"
    prompt = st.text_area("详细描述", value=prompt_example, height=150, key="floorplan_prompt")
    with st.expander("⚙️ 高级参数调整"):
        negative_prompt = st.text_area("反向提示词", value="低质量, 效果差, 模糊, 卡通, 动漫, 绘画, 水印, 文字", key="floorplan_neg_prompt")
        c1, c2, c3 = st.columns(3)
        guidance_scale = c1.slider("文字引导强度", 1.0, 15.0, 7.5, 0.5)
        num_steps = c2.slider("生成步数", 10, 50, 25, 1)
        seed = c3.number_input("随机种子", value=-1, help="-1代表每次生成都随机")
    st.divider()
    if st.button("🚀 生成您的专属效果图", use_container_width=True, type="primary", key="floorplan_button"):
        if st.session_state.get('uploaded_floorplan') and prompt:
            with st.spinner(f"AI正在全力创作中... (模式: {gen_mode}, 预计需要1-3分钟)"):
                fp_file = st.session_state.uploaded_floorplan
                files = {'file': (fp_file.name, fp_file.getvalue(), fp_file.type)}
                payload = {"prompt": prompt, "negative_prompt": negative_prompt, "guidance_scale": guidance_scale, "num_steps": num_steps, "seed": seed, "is_panorama": is_panorama_mode}
                try:
                    response = requests.post(f"{API_BASE_URL}/generate-from-floorplan", files=files, data=payload, timeout=300)
                    if response.status_code == 200:
                        st.session_state.generated_floorplan_result = response.json().get('generated_image_base64')
                    else:
                        st.error(f"生成失败: {response.text}")
                except requests.RequestException as e:
                    st.error(f"请求后端服务时发生错误: {e}")
        else:
            st.warning("请确保已上传户型图并填写了设计描述。")
    st.subheader("🖼️ 生成结果")
    if st.session_state.generated_floorplan_result:
        res_col1, res_col2 = st.columns([1, 3])
        with res_col1:
            if st.session_state.uploaded_floorplan:
                st.markdown("**原始户型图**")
                st.image(st.session_state.uploaded_floorplan, use_container_width=True)
        with res_col2:
            img_data_b64 = st.session_state.generated_floorplan_result
            if is_panorama_mode:
                st.info("🖱️ 请用鼠标在下方图片上拖动，体验720°沉浸式全景。")
                pannellum_config = {"type": "equirectangular", "panorama": img_data_b64, "autoLoad": True, "showZoomCtrl": False, "mouseZoom": False}
                with st.container(height=520, border=False):
                    streamlit_pannellum(config=pannellum_config)
            else:
                img_data_bytes = base64.b64decode(img_data_b64.split(',')[1])
                st.image(Image.open(io.BytesIO(img_data_bytes)), caption="AI生成的最终效果图", use_container_width=True)
            download_bytes = base64.b64decode(img_data_b64.split(',')[1])
            st.download_button(label="📥 下载高清原图", data=download_bytes, file_name=f"ai_designed_{'panorama' if is_panorama_mode else 'room'}.png", mime="image/png", use_container_width=True)
    else:
        st.markdown("""<div style="height: 500px; border: 2px dashed #ccc; border-radius: 10px; display: flex; justify-content: center; align-items: center; background-color: #fafafa;"><p style="color: #888;">您的AI设计效果图将在这里展示</p></div>""", unsafe_allow_html=True)

if st.session_state.get('dialog_info'):
    show_detail_dialog(st.session_state.dialog_info)