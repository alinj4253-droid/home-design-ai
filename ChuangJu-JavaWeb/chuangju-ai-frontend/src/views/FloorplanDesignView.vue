<!-- 文件: src/views/FloorplanDesignView.vue -->
<template>
  <div class="floorplan-view">
    <el-row :gutter="20" class="main-row">
      <!-- 左侧：设置区域 -->
      <el-col :xs="24" :sm="10" :md="8" class="settings-col">
        <el-card shadow="never" class="settings-card">
          <div class="settings-content">
            <div class="settings-section">
              <h3>1. 上传与设定</h3>
              <el-upload
                action="#"
                :show-file-list="false"
                :auto-upload="false"
                :on-change="handleFileChange"
                class="floorplan-uploader"
              >
                <!-- 预览图 -->
                <img v-if="uploadedImageUrl" :src="uploadedImageUrl" class="floorplan-preview" />
                <el-icon v-else class="uploader-icon"><Plus /></el-icon>
              </el-upload>
              <el-radio-group v-model="form.is_panorama" class="mode-selector">
                <el-radio-button :value="false" label="标准效果图" />
                <el-radio-button :value="true" label="3D全景图 ✨" />
              </el-radio-group>
            </div>

            <div class="settings-section">
              <h3>2. 描绘您的创意 ✍️</h3>
              <el-input
                v-model="form.prompt"
                type="textarea"
                :rows="6"
                placeholder="一张现代简约风格的客厅效果图，拥有巨大的落地窗..."
              />
            </div>

            <el-collapse class="advanced-settings">
              <el-collapse-item title="⚙️ 高级参数调整">
                <el-form label-position="top">
                  <el-form-item label="反向提示词">
                    <el-input v-model="form.negative_prompt" type="textarea" :rows="3" />
                  </el-form-item>
                  <el-form-item label="文字引导强度">
                    <el-slider v-model="form.guidance_scale" :min="1.0" :max="15.0" :step="0.5" show-input />
                  </el-form-item>
                  <el-form-item label="生成步数">
                    <el-slider v-model="form.num_steps" :min="10" :max="50" :step="1" show-input />
                  </el-form-item>
                  <el-form-item label="随机种子 (-1代表随机)">
                    <el-input-number v-model="form.seed" controls-position="right" style="width: 100%;" />
                  </el-form-item>
                </el-form>
              </el-collapse-item>
            </el-collapse>
          </div>
          
          <el-button
            type="primary"
            size="large"
            @click="handleGenerate"
            :loading="loading"
            :disabled="!uploadedFile"
            class="generate-button"
            icon="Promotion"
          >
            🚀 生成您的专属效果图
          </el-button>
        </el-card>
      </el-col>

      <!-- 右侧：结果展示区域 -->
      <el-col :xs="24" :sm="14" :md="16" class="result-col">
        <el-card 
          shadow="never" 
          class="result-card" 
          :body-style="{ padding: '0px', height: '100%', display: 'flex', flexDirection: 'column' }"
        >
          <div v-if="loading" class="loading-overlay">
            <el-progress type="circle" :percentage="75" status="success" :indeterminate="true" :duration="2" />
            <p>AI正在全力创作中... (预计需要3-10分钟)</p>
          </div>
          
          <div v-else-if="!generatedImageB64" class="placeholder">
            <el-icon><Picture /></el-icon>
            <p>您的AI设计效果图将在这里展示</p>
          </div>
          
          <div v-else class="result-display">
            <!-- 3D全景查看器 -->
            <VuePannellum
              v-if="form.is_panorama"
              :src="generatedImageB64"
              :key="generatedImageB64"
              class="pannellum-viewer"
              :auto-load="true"
              :show-zoom-ctrl="false"
            />
            
            <!-- 普通图片查看 -->
            <el-image 
              v-else 
              :src="generatedImageB64" 
              fit="contain" 
              class="result-image"
              :preview-src-list="[generatedImageB64]"
              :initial-index="0"
              :hide-on-click-modal="true"
            />
            
            <!-- 悬浮下载按钮 -->
            <el-button @click="downloadImage" type="success" size="large" class="download-button" icon="Download">
              下载高清原图
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, nextTick } from 'vue';
import { Plus, Picture, Promotion, Download } from '@element-plus/icons-vue';
import type { UploadFile } from 'element-plus';
import { ElMessage } from 'element-plus';
import VuePannellum from 'vue-pannellum';
import 'pannellum/build/pannellum.css';
import { generateFromFloorplan, type FloorplanPayload } from '@/services/apiService';

const loading = ref(false);
const uploadedFile = ref<File | null>(null);
const uploadedImageUrl = ref<string>('');
const generatedImageB64 = ref<string>('');

const form = reactive({
  prompt: '一张现代简约风格的客厅效果图，拥有巨大的落地窗和充足的自然光，白色的墙壁，浅灰色布艺沙发，搭配原木色电视柜和茶几，地板为浅色木地板，点缀有绿植，整体氛围明亮、舒适、温馨，电影级光照，照片级真实感，8k画质。',
  negative_prompt: '低质量, 效果差, 模糊, 卡通, 动漫, 绘画, 水印, 文字',
  guidance_scale: 7.5,
  num_steps: 20,
  seed: -1,
  is_panorama: false,
});

const handleFileChange = (uploadFile: UploadFile) => {
  if (uploadFile.raw) {
    uploadedFile.value = uploadFile.raw;
    if (uploadedImageUrl.value) {
      URL.revokeObjectURL(uploadedImageUrl.value);
    }
    uploadedImageUrl.value = URL.createObjectURL(uploadFile.raw);
  }
};

const handleGenerate = async () => {
  if (!uploadedFile.value) {
    ElMessage.warning('请先上传户型图');
    return;
  }
  
  loading.value = true;
  generatedImageB64.value = '';

  try {
    const payload: FloorplanPayload = { ...form, file: uploadedFile.value };
    const result = await generateFromFloorplan(payload);
    
    generatedImageB64.value = result.generated_image_base64;

    await nextTick();
    ElMessage.success('🎉 效果图生成成功！');

  } catch (error: any) {
    console.error("生成效果图失败:", error);
    ElMessage.error({
      message: error.response?.data?.detail || '生成失败，请检查后端服务或GPU状态',
      duration: 5000
    });
  } finally {
    loading.value = false;
  }
};

const downloadImage = () => {
  if (!generatedImageB64.value) return;
  const link = document.createElement('a');
  link.href = generatedImageB64.value;
  link.download = `ai_designed_${form.is_panorama ? 'panorama' : 'room'}.png`;
  link.click();
};
</script>

<style scoped>
.floorplan-view, .main-row, .settings-col, .result-col {
  height: 100%;
}
.settings-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

/* 右侧卡片 */
.result-card {
  height: 100%;
  border: none;
  background-color: #f5f7fa; 
}

.settings-content {
  flex-grow: 1;
  overflow-y: auto;
  padding-right: 10px;
}
.settings-section {
  margin-bottom: 20px;
}

/* --- 上传区域优化 (240px 高度 + contain) --- */
.floorplan-uploader {
  width: 100%;
  height: 240px; 
  border: 1px dashed var(--el-border-color);
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  cursor: pointer;
  background-color: #fafafa;
}
.floorplan-uploader :deep(.el-upload),
.floorplan-uploader :deep(.el-upload-dragger) {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  padding: 0;
}
.floorplan-preview {
  max-width: 100%;
  max-height: 100%;
  width: auto;
  height: auto;
  object-fit: contain; 
}
/* ------------------------------- */

.uploader-icon {
  font-size: 28px;
  color: #8c939d;
}
.mode-selector {
  margin-top: 15px;
  width: 100%;
}
.mode-selector .el-radio-button {
  width: 50%;
}
.mode-selector :deep(.el-radio-button__inner) {
  width: 100%;
}
.generate-button {
  width: 100%;
  margin-top: 20px;
  flex-shrink: 0;
}
.placeholder, .loading-overlay {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: #999;
}
.placeholder .el-icon, .loading-overlay .el-icon {
  font-size: 64px;
  margin-bottom: 20px;
}
.loading-overlay p {
  margin-top: 20px;
  color: #666;
  font-size: 16px;
}

/* --- 结果展示区域核心修改 --- */
.result-display {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  /* 垂直和水平居中，为 70% 的视图做背景 */
  justify-content: center;
  align-items: center;
  position: relative;
  background-color: #2b2b2b; /* 深色背景，像电影院模式 */
}

/* 3D全景图 & 普通结果图：居中且只占 70% */
.pannellum-viewer,
.result-image {
  width: 70% !important;   /* 宽度限制为 70% */
  height: 70% !important;  /* 高度限制为 70% */
  flex-grow: 0;            /* 停止自动撑满 */
  object-fit: contain;
  background-color: #000;
  box-shadow: 0 20px 50px rgba(0,0,0,0.5); /* 添加阴影，增加立体感 */
  border-radius: 8px;      /* 稍微圆角 */
}

/* 悬浮下载按钮 */
.download-button {
  position: absolute;
  bottom: 30px;
  right: 30px;
  z-index: 10;
  box-shadow: 0 4px 12px rgba(0,0,0,0.3);
  width: auto;
  min-width: 120px;
  padding: 12px 24px;
}
</style>