// 文件: vite.config.ts

import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const BACKEND_API_PORT = 8000;

export default defineConfig({
  plugins: [
    vue(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  // 新增 server 配置
  server: {
    proxy: {
      '/api': {
        target: `http://127.0.0.1:${BACKEND_API_PORT}`,
        changeOrigin: true, 
        rewrite: (path) => path.replace(/^\/api/, ''),
      }
    }
  },
    optimizeDeps: {
    include: ['lodash.debounce'],
  }
})
