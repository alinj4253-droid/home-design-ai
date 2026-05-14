<!-- 文件: src/components/AnalysisResultDisplay.vue -->
<template>
  <div v-if="result">
    <div class="analysis-summary">
      <b>分析摘要:</b> {{ summaryText }}
    </div>
    
    <el-image 
      v-if="result.visualized_image_base64"
      :src="result.visualized_image_base64" 
      fit="contain"
      class="visualized-image"
    >
      <template #placeholder>
        <div class="image-slot">加载中<span class="dot">...</span></div>
      </template>
    </el-image>

    <el-collapse class="json-collapse">
      <el-collapse-item title="查看详细JSON数据">
        <pre><code>{{ JSON.stringify(result, null, 2) }}</code></pre>
      </el-collapse-item>
    </el-collapse>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { AnalysisResult } from '@/services/apiService';

const props = defineProps<{
  result: AnalysisResult | null;
  confidence: number;
}>();

const summaryText = computed(() => {
  if (!props.result) return '';
  
  const main = props.result.main_task_analysis;
  const highConfObjects = props.result.sideline_task_analysis
    .filter(obj => obj.style_confidence >= props.confidence)
    .map(obj => `${obj.furniture_type}-${obj.predicted_style}`);
    
  return [main.predicted_room_type, main.predicted_style, ...highConfObjects]
    .filter(Boolean)
    .join(' | ');
});
</script>

<style scoped>
.analysis-summary {
  background-color: #FFFBEA;
  border-left: 5px solid #E6A23C;
  padding: 1rem 1.25rem;
  margin-bottom: 1rem;
  border-radius: 4px;
  font-size: 1.1em;
}
.analysis-summary b {
  color: #333;
}
.visualized-image {
  width: 100%;
  margin-bottom: 1rem;
  border: 1px solid #eee;
  border-radius: 4px;
}
.json-collapse {
  margin-top: 1rem;
}
pre {
  background-color: #f5f5f5;
  padding: 10px;
  border-radius: 4px;
  white-space: pre-wrap;
  word-wrap: break-word;
}
</style>
