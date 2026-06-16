<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { contractsApi } from '@/api/contracts'

const router = useRouter()
const title = ref('')
const file = ref<File | null>(null)
const loading = ref(false)
const error = ref('')
const dragging = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files && input.files.length > 0) {
    file.value = input.files[0]
  }
}

function onDragOver(e: DragEvent) {
  e.preventDefault()
  dragging.value = true
}
function onDragLeave() {
  dragging.value = false
}
function onDrop(e: DragEvent) {
  e.preventDefault()
  dragging.value = false
  const dropped = e.dataTransfer?.files?.[0]
  if (dropped) {
    file.value = dropped
  }
}

function triggerBrowse() {
  fileInput.value?.click()
}

function removeFile() {
  file.value = null
  if (fileInput.value) fileInput.value.value = ''
}

function fileSize(size: number): string {
  if (size < 1024) return size + ' B'
  if (size < 1024 * 1024) return (size / 1024).toFixed(1) + ' KB'
  return (size / (1024 * 1024)).toFixed(1) + ' MB'
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
    <div class="page-header">
      <h2>上传合同</h2>
    </div>
    <div class="card" style="max-width:540px">
      <div v-if="error" class="error-msg">{{ error }}</div>
      <form @submit.prevent="handleUpload">
        <div class="form-group">
          <label>合同名称</label>
          <input v-model="title" required placeholder="例如: XX技术开发合同" />
        </div>

        <div class="form-group">
          <label>合同文件</label>

          <!-- 拖拽上传区 -->
          <div
            class="drop-zone"
            :class="{ 'drop-zone--active': dragging, 'drop-zone--has-file': file }"
            @dragover="onDragOver"
            @dragleave="onDragLeave"
            @drop="onDrop"
            @click="triggerBrowse"
          >
            <input
              ref="fileInput"
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,.doc,.docx"
              class="drop-zone__input"
              @change="onFileChange"
            />

            <template v-if="!file">
              <div class="drop-zone__icon">📄</div>
              <div class="drop-zone__text">将文件拖拽到此处</div>
              <div class="drop-zone__hint">支持 PDF、PNG、JPG、DOC、DOCX</div>
            </template>

            <template v-else>
              <div class="drop-zone__file">
                <span class="drop-zone__file-icon">📎</span>
                <span class="drop-zone__file-name">{{ file.name }}</span>
                <span class="drop-zone__file-size">{{ fileSize(file.size) }}</span>
                <button type="button" class="drop-zone__remove" @click.stop="removeFile" title="移除">✕</button>
              </div>
            </template>
          </div>
        </div>

        <button class="btn btn-primary" style="width:100%" :disabled="loading">
          {{ loading ? '上传中...' : '创建并开始审核' }}
        </button>
      </form>
    </div>
  </div>
</template>

<style scoped>
.drop-zone {
  position: relative;
  border: 2px dashed var(--border-color);
  border-radius: var(--radius-md);
  padding: 36px 24px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s ease;
  background: var(--bg-secondary);
}
.drop-zone:hover {
  border-color: var(--accent);
  background: var(--accent-light);
}
.drop-zone--active {
  border-color: var(--accent);
  background: var(--accent-light);
  border-style: solid;
}
.drop-zone--has-file {
  padding: 18px 24px;
}

.drop-zone__input {
  display: none;
}

.drop-zone__icon {
  font-size: 36px;
  margin-bottom: 10px;
  opacity: 0.5;
}

.drop-zone__text {
  font-size: 15px;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 6px;
}

.drop-zone__hint {
  font-size: 12px;
  color: var(--text-tertiary);
}

/* 已选文件 */
.drop-zone__file {
  display: flex;
  align-items: center;
  gap: 10px;
}

.drop-zone__file-icon {
  font-size: 18px;
}

.drop-zone__file-name {
  flex: 1;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  text-align: left;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.drop-zone__file-size {
  font-size: 12px;
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.drop-zone__remove {
  width: 26px;
  height: 26px;
  border: none;
  border-radius: 50%;
  background: var(--bg-tertiary);
  color: var(--text-tertiary);
  cursor: pointer;
  font-size: 13px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.15s ease;
}
.drop-zone__remove:hover {
  background: var(--danger-light);
  color: var(--danger);
}
</style>
