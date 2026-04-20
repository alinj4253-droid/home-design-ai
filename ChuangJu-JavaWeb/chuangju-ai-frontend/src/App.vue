<!-- 文件: src/App.vue -->
<template>
  <el-container class="app-container">
    <el-header class="app-header">
      <div class="logo-area">
        <img alt="logo" class="logo-img" src="@/assets/logo.svg" />
        <span class="logo-text">创居AI</span>
      </div>
      <el-menu
        :router="true"
        :default-active="$route.path"
        class="main-menu"
        mode="horizontal"
        :ellipsis="false"
      >
        <el-menu-item index="/tagging">智能打标</el-menu-item>
        <el-menu-item index="/gallery">图库检索</el-menu-item>
        <el-menu-item index="/nlp-search">自然语言搜索</el-menu-item>
        <el-menu-item index="/floorplan-design">户型图AI设计</el-menu-item>
      </el-menu>
    </el-header>
    <el-main class="app-main">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
</script>

<style scoped>
.app-container {
  height: 100%; /* 现在它可以继承来自 #app 的 100% 高度 */
  display: flex;
  flex-direction: column;
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #dcdfe6;
  padding: 0 20px;
  background-color: #ffffff;
  flex-shrink: 0; /* 防止 header 在内容过多时被压缩 */
}

.logo-area {
  display: flex;
  align-items: center;
}

.logo-img {
  height: 30px;
  width: 30px;
  margin-right: 12px;
}

.logo-text {
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}

.main-menu {
  border-bottom: none;
  height: 100%;
}

.app-main {
  padding: 20px;
  flex-grow: 1; /* 让主内容区域占据所有剩余空间 */
  overflow-y: auto; /* 内容超出时，允许主区域滚动，而不是整个页面 */
  display: flex; /* 使用 flex 布局，让子元素更容易撑满 */
  flex-direction: column; /* 垂直排列子元素 */
}
</style>
