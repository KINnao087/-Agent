<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { contractsApi } from '@/api/contracts'

const router = useRouter()
const title = ref('')
const filePath = ref('')
const loading = ref(false)
const error = ref('')

async function handleUpload() {
  error.value = ''
  loading.value = true
  try {
    const res = await contractsApi.create(title.value, filePath.value)
    router.push('/contracts/' + res.data.id + '/review')
  } catch (e: any) {
    error.value = e.response?.data?.message || '创建失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="page">
    <h2 style="margin-bottom:20px">上传合同</h2>
    <div class="card" style="max-width:500px">
      <div v-if="error" style="color:#f56c6c;margin-bottom:12px">{{ error }}</div>
      <form @submit.prevent="handleUpload">
        <div class="form-group">
          <label>合同名称</label>
          <input v-model="title" required placeholder="例如: XX技术开发合同" />
        </div>
        <div class="form-group">
          <label>文件路径</label>
          <input v-model="filePath" required placeholder="D:\contracts\contract1.pdf" />
        </div>
        <button class="btn btn-primary" :disabled="loading">
          {{ loading ? '上传中...' : '创建并开始审核' }}
        </button>
      </form>
    </div>
  </div>
</template>
