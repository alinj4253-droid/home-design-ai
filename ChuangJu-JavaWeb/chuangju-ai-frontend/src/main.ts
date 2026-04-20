import { createApp } from 'vue'
import { createPinia } from 'pinia'

// 1. 完整引入 Element Plus
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'

import App from './App.vue'
import router from './router'

// 2. 引入基础样式 (可选，但推荐)
import './assets/main.css'

const app = createApp(App)

app.use(createPinia())
app.use(router)

// 3. 全局注册 Element Plus
app.use(ElementPlus)

app.mount('#app')
