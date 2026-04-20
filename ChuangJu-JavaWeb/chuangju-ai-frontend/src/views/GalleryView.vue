<!-- 文件: src/views/GalleryView.vue -->
<template>
  <div class="gallery-view">
    <!-- 1. 筛选区域 -->
    <el-card shadow="never" class="filter-card">
      <el-form :inline="true" :model="filters" @submit.prevent="handleFilterChange">
        <el-form-item label="设计风格">
          <el-select
            v-model="filters.style"
            placeholder="所有风格"
            clearable
            @change="handleFilterChange"
            style="min-width: 180px;"
          >
            <el-option
              v-for="item in filterOptions.styles"
              :key="item"
              :label="item"
              :value="item"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="空间类型">
          <el-select
            v-model="filters.room_type"
            placeholder="所有空间"
            clearable
            @change="handleFilterChange"
            style="min-width: 180px;"
          >
            <el-option
              v-for="item in filterOptions.room_types"
              :key="item"
              :label="item"
              :value="item"
            />
          </el-select>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 2. 内容和分页区域 -->
    <el-card shadow="never" class="content-card">
      <template v-if="loading">
        <el-row :gutter="20">
          <el-col v-for="n in 9" :key="n" :xs="24" :sm="12" :md="8" class="skeleton-col">
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
        <el-empty v-if="images.length === 0" description="没有找到匹配的图片" />
        <el-row v-else :gutter="20">
          <el-col
            v-for="(image, index) in images"
            :key="image.id"
            :xs="24" :sm="12" :md="8"
            class="image-col"
          >
            <el-card class="image-card" :body-style="{ padding: '0px' }" @click="handlePreview(index)">
              <img :src="getImageUrlById(image.id)" class="image" :alt="`${image.style} - ${image.room_type}`" />
              <div class="card-info">
                <span class="card-title">{{ image.style }}</span>
                <div class="card-bottom">
                  <time class="card-subtitle">{{ image.room_type }}</time>
                </div>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </template>
      
      <el-pagination
        v-if="!loading && total > 0"
        background
        layout="prev, pager, next, jumper"
        :total="total"
        :page-size="pagination.pageSize"
        :current-page="pagination.currentPage"
        @current-change="handlePageChange"
        class="pagination-container"
      />
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
import { ref, reactive, onMounted, computed } from 'vue';
import '@/assets/shared-styles.css';
import { 
  getFilterOptions, 
  searchImages, 
  getImageUrlById, 
  type FilterOptions, 
  type ImageItem 
} from '@/services/apiService';

const loading = ref(true);
const filterOptions = reactive<FilterOptions>({ styles: [], room_types: [] });
const filters = reactive({ style: '', room_type: '' });
const images = ref<ImageItem[]>([]);
const total = ref(0);
const pagination = reactive({ currentPage: 1, pageSize: 9 });

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

const fetchImages = async () => {
  loading.value = true;
  try {
    const params = {
      style: filters.style || null,
      room_type: filters.room_type || null,
      page: pagination.currentPage,
      size: pagination.pageSize,
    };
    const data = await searchImages(params);
    images.value = data.results;
    total.value = data.total_results;
  } catch (error) { 
    console.error("获取图片数据失败:", error);
  } finally { 
    loading.value = false; 
  }
};

const handleFilterChange = () => {
  pagination.currentPage = 1;
  fetchImages();
};

const handlePageChange = (newPage: number) => {
  pagination.currentPage = newPage;
  fetchImages();
};

onMounted(async () => {
  try {
    const options = await getFilterOptions();
    filterOptions.styles = options.styles;
    filterOptions.room_types = options.room_types;
  } catch (error) { 
    console.error("获取筛选选项失败:", error); 
  }
  fetchImages();
});
</script>

<style scoped>
.gallery-view {
  display: flex;
  flex-direction: column;
  gap: 20px;
  height: 100%;
}
.filter-card {
  flex-shrink: 0;
}
.content-card {
  flex-grow: 1;
  overflow-y: auto;
}
.image-col, .skeleton-col {
  margin-bottom: 20px;
}
.pagination-container {
  margin-top: 20px;
  display: flex;
  justify-content: center;
}
</style>
