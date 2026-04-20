<!-- 文件: src/views/TaggingView.vue (最终优化版) -->
<template>
  <div class="tagging-view">
    <!-- 1. 上传与设置区域 -->
    <el-card shadow="never" class="setup-card">
      <el-upload
        ref="uploadRef"
        drag
        action="#"
        multiple
        :auto-upload="false"
        :on-change="handleFileChange"
        class="upload-area"
      >
        <el-icon class="el-icon--upload"><upload-filled /></el-icon>
        <div class="el-upload__text">
          拖拽文件到此处或 <em>点击上传</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">支持 png / jpg / jpeg / zip 格式</div>
        </template>
      </el-upload>

      <div class="slider-container">
        <span class="slider-label">局部风格置信度阈值:</span>
        <el-slider v-model="confidence" :min="0.1" :max="1.0" :step="0.05" show-input class="confidence-slider" />
      </div>

      <el-button
        type="primary"
        size="large"
        @click="startAnalysis"
        :loading="isUploading"
        :disabled="files.length === 0"
        class="analysis-button"
        icon="MagicStick"
      >
        {{ isUploading ? '正在分析中...' : '开始智能分析' }}
      </el-button>
    </el-card>

    <!-- 2. 结果展示区域 (这是一个独立的卡片) -->
    <el-card shadow="never" class="result-card" v-if="analysisState !== 'idle'">
      <div v-if="analysisState === 'batch_processing'" class="batch-progress">
        <h3>批量任务处理中...</h3>
        <el-progress :percentage="batchProgress.percentage" :text-inside="true" :stroke-width="20" status="success">
          <span>{{ batchProgress.text }}</span>
        </el-progress>
      </div>
      <div v-if="analysisState === 'single_done' && singleResult">
        <AnalysisResultDisplay :result="singleResult" :confidence="confidence" />
      </div>
      <div v-if="analysisState === 'batch_done' && batchResults.length > 0">
        <h3>批量分析完成！共处理 {{ batchResults.length }} 个文件。</h3>
        <el-collapse v-model="activeCollapse" accordion>
          <el-collapse-item v-for="(item, index) in batchResults" :key="item.filename" :title="item.filename" :name="index">
            <AnalysisResultDisplay :result="item.analysis" :confidence="confidence" />
          </el-collapse-item>
        </el-collapse>
      </div>
      <el-alert v-if="analysisState === 'error'" title="分析失败" :description="errorMessage" type="error" show-icon />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { UploadFilled, MagicStick } from '@element-plus/icons-vue';
import type { UploadInstance, UploadFile, UploadFiles } from 'element-plus';
import { ElMessage } from 'element-plus';
import JSZip from 'jszip';
import { 
  analyzeImage, 
  submitBatchAnalysis, 
  getBatchTaskStatus, 
  getBatchTaskResults,
  type AnalysisResult, 
  type BatchResultItem 
} from '@/services/apiService';
import AnalysisResultDisplay from '@/components/AnalysisResultDisplay.vue';

type AnalysisState = 'idle' | 'single_processing' | 'batch_processing' | 'single_done' | 'batch_done' | 'error';

const uploadRef = ref<UploadInstance>();
const confidence = ref(0.5);
const files = ref<UploadFile[]>([]);
const isUploading = ref(false);
const analysisState = ref<AnalysisState>('idle');
const singleResult = ref<AnalysisResult | null>(null);
const batchResults = ref<BatchResultItem[]>([]);
const activeCollapse = ref(0);
const batchProgress = ref({ percentage: 0, text: '提交任务中...' });
const errorMessage = ref('');

const handleFileChange = (uploadFile: UploadFile, uploadFiles: UploadFiles) => {
  files.value = uploadFiles;
  analysisState.value = 'idle';
};

const startAnalysis = async () => {
  if (files.value.length === 0) return ElMessage.warning('请先上传文件');
  
  isUploading.value = true;
  analysisState.value = files.value.length === 1 && !files.value[0].name.toLowerCase().endsWith('.zip')
    ? 'single_processing'
    : 'batch_processing';

  try {
    if (analysisState.value === 'single_processing') {
      singleResult.value = await analyzeImage(files.value[0].raw!, confidence.value);
      analysisState.value = 'single_done';
    } else {
      await handleBatchAnalysis();
    }
  } catch (err: any) {
    errorMessage.value = err.response?.data?.detail || err.message || '未知错误';
    analysisState.value = 'error';
  } finally {
    isUploading.value = false;
    uploadRef.value?.clearFiles();
    files.value = [];
  }
};

const handleBatchAnalysis = async () => {
  const zip = new JSZip();
  files.value.forEach(file => zip.file(file.name, file.raw!));
  const zipBlob = await zip.generateAsync({ type: 'blob' });
  const zipFile = new File([zipBlob], 'batch_upload.zip');
  const { task_id } = await submitBatchAnalysis(zipFile, confidence.value);
  await pollBatchStatus(task_id);
};

const pollBatchStatus = (taskId: string) => {
  return new Promise<void>((resolve, reject) => {
    const interval = setInterval(async () => {
      try {
        const status = await getBatchTaskStatus(taskId);
        if (status.status === 'processing' && status.progress) {
          const [current, total] = status.progress.split('/').map(Number);
          batchProgress.value = { percentage: total > 0 ? Math.round((current / total) * 100) : 0, text: `处理中: ${status.progress}` };
        } else if (status.status === 'complete') {
          clearInterval(interval);
          batchProgress.value = { percentage: 100, text: '任务完成，正在获取结果...' };
          batchResults.value = await getBatchTaskResults(taskId);
          analysisState.value = 'batch_done';
          resolve();
        } else if (status.status === 'failed') {
          throw new Error(status.error || '批量任务处理失败');
        }
      } catch (err) {
        clearInterval(interval);
        reject(err);
      }
    }, 2000);
  });
};
</script>

<style scoped>
.tagging-view {
  display: flex;
  flex-direction: column;
  gap: 20px;
  height: 100%;
}
.setup-card, .result-card {
  flex-shrink: 0;
}
.result-card {
  flex-grow: 1;
}
.slider-container {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-top: 20px;
}
.slider-label {
  white-space: nowrap;
  color: var(--el-text-color-secondary);
}
.confidence-slider {
  flex-grow: 1;
}
.analysis-button {
  margin-top: 20px;
  width: 100%;
}
.batch-progress {
  margin-bottom: 20px;
}
</style>
