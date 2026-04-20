<!-- 文件: src/views/NlpSearchView.vue -->
<template>
  <div class="nlp-search-view">
    <!-- 1. 搜索输入区域 -->
    <el-card shadow="never" class="search-card">
      <div class="search-area">
        <el-input
          v-model="searchQuery"
          placeholder="例如：一个舒适温馨的奶油风卧室..."
          size="large"
          class="search-input"
          clearable
          @keyup.enter="handleSearch"
        />
        <el-button
          type="primary"
          size="large"
          @click="handleSearch"
          :loading="loading"
          icon="Search"
        >
          智能搜索
        </el-button>
      </div>
    </el-card>

    <!-- 2. 结果展示区域 -->
    <el-card shadow="never" class="result-card">
      <template v-if="loading">
        <el-row :gutter="20">
          <el-col v-for="n in 12" :key="n" :xs="24" :sm="12" :md="8" :lg="6" class="skeleton-col">
            <el-skeleton style="width: 100%" animated>
              <template #template>
                <el-skeleton-item variant="image" style="width: 100%; height: 200px;" />
                <div style="padding: 14px;">
                  <el-skeleton-item variant="p" style="width: 50%" />
                  <el-skeleton-item variant="text" style="margin-top: 16px; width: 30%;" />
                </div>
              </template>
            </el-skeleton>
          </el-col>
        </el-row>
      </template>
      <template v-else>
        <el-empty 
          v-if="!searched || (searched && images.length === 0)" 
          :description="searched ? '抱歉，没有找到与您描述相关的图片' : '请输入您的设计想法，开始智能搜索'"
        />
        <div v-else>
          <div class="result-summary">
            为您找到了 {{ images.length }} 张最相关的图片！
          </div>
          <el-row :gutter="20">
            <el-col
              v-for="(image, index) in images"
              :key="image.id"
              :xs="24" :sm="12" :md="8" :lg="6"
              class="image-col"
            >
              <el-card class="image-card" :body-style="{ padding: '0px' }" @click="handlePreview(index)">
                <img :src="getImageUrlById(image.id)" class="image" :alt="`${image.style} - ${image.room_type}`"/>
                <div class="card-info">
                  <span class="card-title">{{ image.style }}</span>
                  <div class="card-bottom">
                    <time class="card-subtitle">{{ image.room_type }}</time>
                  </div>
                </div>
              </el-card>
            </el-col>
          </el-row>
        </div>
      </template>
    </el-card>
    
    <!-- 图片预览组件 -->
    <el-image-viewer
      v-if="previewVisible"
      :url-list="previewUrlList"
      :initial-index="previewInitialIndex"
      :hide-on-click-modal="true"
      @close="closePreview"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { ElMessage } from 'element-plus';
import { Search } from '@element-plus/icons-vue'
import '@/assets/shared-styles.css';
import { 
  searchImagesByText, 
  getImageUrlById, 
  type ImageItem 
} from '@/services/apiService';

const searchQuery = ref('');
const loading = ref(false);
const images = ref<ImageItem[]>([]);
const searched = ref(false);

const previewVisible = ref(false);
const previewInitialIndex = ref(0);

const previewUrlList = computed(() => {
  return images.value.map(image => getImageUrlById(image.id));
});

const handlePreview = (index: number) => {
  previewInitialIndex.value = index;
  previewVisible.value = true;
};

const closePreview = () => {
  previewVisible.value = false;
};

const handleSearch = async () => {
  if (!searchQuery.value.trim()) {
    ElMessage.warning('请输入您的需求描述');
    return;
  }
  
  loading.value = true;
  searched.value = true;
  images.value = [];
  
  try {
    const data = await searchImagesByText(searchQuery.value);
    images.value = data.results;
  } catch (error) {
    console.error("自然语言搜索失败:", error);
    ElMessage.error('搜索时发生错误，请稍后再试');
  } finally {
    loading.value = false;
  }
};
</script>

<style scoped>
.nlp-search-view {
  display: flex;
  flex-direction: column;
  gap: 20px;
  height: 100%;
}
.search-card {
  flex-shrink: 0;
}
.search-area {
  display: flex;
  gap: 10px;
}
.search-input {
  flex-grow: 1;
}
.result-card {
  flex-grow: 1;
  overflow-y: auto;
}
.result-summary {
  margin-bottom: 20px;
  font-size: 16px;
  color: #606266;
}
.image-col, .skeleton-col {
  margin-bottom: 20px;
}
</style>
