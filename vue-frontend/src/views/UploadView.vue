<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { contractsApi } from '@/api/contracts'

const router = useRouter()
const title = ref('')
const file = ref<File | null>(null)
const loading = ref(false)
const error = ref('')

function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files && input.files.length > 0) {
    file.value = input.files[0]
  }
}

async function handleUpload() {
  error.value = ''
  if (!file.value) {
    error.value = '请选择文件'
    return
  }
  loading.value = true
  try {
    const formData = new FormData()
    formData.append('file', file.value)
    formData.append('title', title.value)
    const res = await contractsApi.create(formData)
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
      <form @submit.prevent="handleUpload" enctype="multipart/form-data">
        <div class="form-group">
          <label>合同名称</label>
          <input v-model="title" required placeholder="例如: XX技术开发合同" />
        </div>
        <div class="form-group">
          <label>合同文件</label>
          <input type="file" accept=".pdf,.png,.jpg,.jpeg,.doc,.docx" @change="onFileChange" required />
        </div>
        <button class="btn btn-primary" :disabled="loading">
          {{ loading ? '上传中...' : '创建并开始审核' }}
        </button>
      </form>
    </div>
  </div>
</template>
