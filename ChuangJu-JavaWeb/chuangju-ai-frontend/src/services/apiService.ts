// 文件: src/services/apiService.ts

import axios, { type AxiosRequestConfig } from 'axios';


const apiClient = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface ImageItem {
  id: number;
  image_path: string;
  style: string;
  room_type: string;
}

export interface SearchResult {
  total_results: number;
  page: number;
  page_size: number;
  results: ImageItem[];
}

export interface FilterOptions {
  styles: string[];
  room_types: string[];
}

export interface SidelineAnalysis {
  furniture_type: string;
  bounding_box: [number, number, number, number];
  predicted_style: string;
  style_confidence: number;
}

export interface AnalysisResult {
  image_path: string;
  main_task_analysis: {
    predicted_style: string;
    style_confidence: number;
    predicted_room_type: string;
    room_type_confidence: number;
  };
  sideline_task_analysis: SidelineAnalysis[];
  visualized_image_base64: string;
}

export interface BatchTaskStatus {
  task_id: string;
  status: 'pending' | 'processing' | 'complete' | 'failed';
  progress?: string;
  error?: string;
}

export interface BatchResultItem {
  filename: string;
  analysis: AnalysisResult;
}

export interface FloorplanPayload {
  prompt: string;
  negative_prompt: string;
  guidance_scale: number;
  num_steps: number;
  seed: number;
  is_panorama: boolean;
  file: File;
}

export const getFilterOptions = (): Promise<FilterOptions> => {
  return apiClient.get('/get-filter-options').then(res => res.data);
};

/**
 * 根据条件搜索图片
 * @param params - 包含 style, room_type, page, size 的对象
 */
export const searchImages = (params: {
  style?: string | null;
  room_type?: string | null;
  page: number;
  size: number;
}): Promise<SearchResult> => {

  const cleanedParams = Object.fromEntries(
    Object.entries(params).filter(([, v]) => v != null && v !== '')
  );
  return apiClient.get('/search', { params: cleanedParams }).then(res => res.data);
};

/**
 * 根据图片ID获取图片URL
 * @param imageId - 图片的ID
 * @returns 返回可直接用于 <img> src 属性的 URL
 */
export const getImageUrlById = (imageId: number): string => {
  return `/api/get_image_by_id/${imageId}`;
};

/**
 * 根据自然语言文本描述搜索图片
 * @param query - 用户的输入文本
 * @param size - 希望返回的结果数量
 */
export const searchImagesByText = (query: string, size: number = 12): Promise<{ query: string, results: ImageItem[] }> => {
  return apiClient.get('/search-text', {
    params: { query, size }
  }).then(res => res.data);
};

/**
 * 上传单张图片进行分析
 * @param file - 图片文件
 * @param confidenceThreshold - 置信度阈值
 */
export const analyzeImage = (file: File, confidenceThreshold: number): Promise<AnalysisResult> => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('confidence_threshold', String(confidenceThreshold));
  return apiClient.post('/analyze-image', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }).then(res => res.data);
};

/**
 * 提交批量分析任务
 * @param file - 包含多图片或ZIP的ZIP文件
 * @param confidenceThreshold - 置信度阈值
 */
export const submitBatchAnalysis = (file: File, confidenceThreshold: number): Promise<{ task_id: string }> => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('confidence_threshold', String(confidenceThreshold));
  return apiClient.post('/analyze-batch', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }).then(res => res.data);
};

/**
 * 查询批量任务状态
 * @param taskId - 任务ID
 */
export const getBatchTaskStatus = (taskId: string): Promise<BatchTaskStatus> => {
  return apiClient.get(`/batch-status/${taskId}`).then(res => res.data);
};

/**
 * 获取批量任务的完整结果
 * @param taskId - 任务ID
 */
export const getBatchTaskResults = (taskId: string): Promise<BatchResultItem[]> => {
  return new Promise(async (resolve, reject) => {
    try {
      let allResults: BatchResultItem[] = [];
      let currentPage = 1;
      let totalPages = 1;
      
      do {
        const response = await apiClient.get(`/batch-results/${taskId}`, {
          params: { page: currentPage, size: 5 } // 每页5条
        });
        const data = response.data;
        allResults = allResults.concat(data.results);
        totalPages = data.total_pages;
        currentPage++;
      } while (currentPage <= totalPages);

      resolve(allResults);
    } catch (error) {
      reject(error);
    }
  });
};

/**
 * 从户型图生成效果图
 * @param payload - 包含所有参数和文件的对象
 */
export const generateFromFloorplan = (payload: FloorplanPayload): Promise<{ generated_image_base64: string }> => {
  const formData = new FormData();
  Object.entries(payload).forEach(([key, value]) => {
    if (typeof value === 'boolean') {
      formData.append(key, String(value));
    } else {
      formData.append(key, value);
    }
  });
  // 设置一个较长的超时时间
  const config: AxiosRequestConfig = {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 300000, // 300秒 = 5分钟
  };

  return apiClient.post('/generate-from-floorplan', formData, config).then(res => res.data);
};
