<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { contractsApi, type ContractItem } from '@/api/contracts'
import ExecutionTree from '@/components/ExecutionTree.vue'
import MarkdownViewer from '@/components/MarkdownViewer.vue'

const route = useRoute()
const auth = useAuthStore()
const contract = ref<ContractItem | null>(null)
const events = ref<any[]>([])
const streaming = ref(false)
const error = ref('')
const markdown = ref('')
const approving = ref(false)
const fileBlobUrl = ref('')
const loadingFile = ref(false)
const isImage = ref(false)
const fileError = ref('')
const seenEventSeq = new Set<number>()
let eventSource: EventSource | null = null

const STATUS_LABELS: Record<string, string> = {
  pending: '未审核',
  reviewing: '审核中',
  pending_review: '待复审',
  completed: '已完成',
  failed: '失败',
}

function statusLabel(status: string) {
  return STATUS_LABELS[status] || status
}

function appendEvent(evt: any) {
  const seq = Number(evt?.seq)
  if (Number.isFinite(seq) && seq > 0) {
    if (seenEventSeq.has(seq)) return
    seenEventSeq.add(seq)
  }
  events.value.push(evt)
  events.value.sort((left, right) => (Number(left?.seq) || 0) - (Number(right?.seq) || 0))
}

async function loadFileBlob(contractId: number, filePath: string) {
  loadingFile.value = true
  fileError.value = ''
  try {
    const res = await contractsApi.getFile(contractId)
    const headerValue = res.headers['content-type']
    const contentType = typeof headerValue === 'string' ? headerValue : 'application/octet-stream'
    const blob = new Blob([res.data], { type: contentType })
    fileBlobUrl.value = URL.createObjectURL(blob)
    const ext = filePath.split('.').pop()?.toLowerCase() || ''
    isImage.value = ['png', 'jpg', 'jpeg'].includes(ext)
  } catch {
    console.error('ReviewView.loadFileBlob failed', { contractId, filePath })
    fileError.value = '文件加载失败'
    fileBlobUrl.value = ''
  } finally {
    loadingFile.value = false
  }
}

function closeStream() {
  eventSource?.close()
  eventSource = null
  streaming.value = false
}

function connectStream() {
  if (!contract.value?.id || !contract.value.reviewId) return

  closeStream()
  streaming.value = true
  const url = `/api/contracts/${contract.value.id}/review/stream?token=${encodeURIComponent(auth.token)}`
  eventSource = new EventSource(url)

  eventSource.onmessage = (rawEvent) => {
    try {
      const evt = JSON.parse(rawEvent.data)
      appendEvent(evt)

      if (evt.kind === 'final') {
        streaming.value = false
        eventSource?.close()
        if (contract.value?.status === 'reviewing') {
          contract.value.status = 'pending_review'
          contractsApi.updateStatus(contract.value.id, 'pending_review').catch(() => {})
        }
        loadMarkdown()
      }

      if (evt.kind === 'error') {
        streaming.value = false
        eventSource?.close()
        if (contract.value?.status === 'reviewing') {
          contract.value.status = 'failed'
          contractsApi.updateStatus(contract.value.id, 'failed').catch(() => {})
        }
      }
    } catch {
      // Ignore malformed SSE payloads.
    }
  }

  eventSource.onerror = () => {
    streaming.value = false
    eventSource?.close()
  }
}

async function loadMarkdown() {
  if (!contract.value) return
  try {
    const res = await contractsApi.getReportMarkdown(contract.value.id)
    markdown.value = res.data
  } catch {
    console.error('ReviewView.loadMarkdown failed', { contractId: contract.value.id })
    markdown.value = ''
  }
}

async function startReview() {
  if (!contract.value) return
  events.value = []
  seenEventSeq.clear()
  error.value = ''
  markdown.value = ''

  try {
    const res = await contractsApi.startReview(contract.value.id)
    contract.value.reviewId = res.data.reviewId
    contract.value.status = 'reviewing'
    connectStream()
  } catch (e: any) {
    error.value = '发起审核失败: ' + (e.response?.data?.message || e.message)
  }
}

async function approveReview() {
  if (!contract.value) return
  approving.value = true
  try {
    await contractsApi.updateStatus(contract.value.id, 'completed')
    contract.value.status = 'completed'
  } catch (e: any) {
    error.value = '操作失败: ' + (e.response?.data?.message || e.message)
  } finally {
    approving.value = false
  }
}

function cancelReview() {
  closeStream()
  if (!contract.value) return
  contractsApi.cancelReview(contract.value.id).catch(() => {})
  contract.value.status = 'failed'
}

onMounted(async () => {
  const id = Number(route.params.id)
  try {
    const res = await contractsApi.get(id)
    contract.value = res.data

    if (res.data.filePath) {
      loadFileBlob(id, res.data.filePath)
    }
    if (res.data.reviewId) {
      loadMarkdown()
      connectStream()
    }
  } catch {
    console.error('ReviewView.onMounted get contract failed', { contractId: id })
    error.value = '加载合同失败'
  }
})

onUnmounted(() => {
  closeStream()
  if (fileBlobUrl.value) {
    URL.revokeObjectURL(fileBlobUrl.value)
  }
})
</script>

<template>
  <div class="split-layout">
    <div class="panel-left">
      <h3 v-if="contract" style="font-size:16px;margin-bottom:10px">{{ contract.title }}</h3>

      <div v-if="contract" style="margin:10px 0">
        <span :class="'status-tag status-' + contract.status">
          {{ statusLabel(contract.status) }}
        </span>
      </div>

      <div class="file-preview" style="margin:16px 0">
        <h4 style="font-size:13px;margin-bottom:8px;color:var(--text-secondary)">合同文件预览</h4>

        <div v-if="loadingFile" style="padding:20px;text-align:center;color:var(--text-tertiary)">
          文件加载中...
        </div>

        <div v-else-if="fileError" style="padding:20px;text-align:center;color:var(--danger)">
          {{ fileError }}
        </div>

        <template v-else-if="fileBlobUrl">
          <img
            v-if="isImage"
            :src="fileBlobUrl"
            :alt="contract?.title || '合同图片'"
            style="width:100%;max-height:500px;object-fit:contain;border:1px solid var(--border-color);border-radius:6px"
          />
          <iframe
            v-else
            :src="fileBlobUrl"
            style="width:100%;height:500px;border:1px solid var(--border-color);border-radius:6px"
          ></iframe>
        </template>
      </div>

      <div v-if="error" class="error-msg">{{ error }}</div>

      <div style="margin-top:20px;display:flex;flex-direction:column;gap:8px">
        <button
          v-if="contract && contract.status === 'pending'"
          class="btn btn-primary"
          style="width:100%"
          @click="startReview"
        >
          开始审核
        </button>

        <button
          v-if="contract && contract.status === 'reviewing'"
          class="btn btn-danger"
          style="width:100%"
          @click="cancelReview"
        >
          取消审核
        </button>

        <button
          v-if="contract && contract.status === 'pending_review'"
          class="btn btn-primary"
          style="width:100%"
          :disabled="approving"
          @click="approveReview"
        >
          {{ approving ? '提交中...' : '审核通过' }}
        </button>

        <button
          v-if="contract && contract.status !== 'pending'"
          class="btn btn-ghost"
          style="width:100%"
          @click="startReview"
        >
          重新审核
        </button>
      </div>
    </div>

    <div class="panel-center">
      <div v-if="events.length === 0" class="empty-state">
        <p v-if="contract && contract.status === 'pending'">点击“开始审核”启动 AI 审核流程</p>
        <p v-else-if="contract && contract.reviewId">正在恢复审核记录...</p>
        <p v-else-if="contract && contract.status === 'completed'">审核已通过</p>
        <p v-else>暂无执行记录</p>
      </div>
      <ExecutionTree :events="events" />
      <div v-if="streaming" style="color:var(--accent);margin-top:8px;font-size:14px">审核进行中...</div>
    </div>

    <div class="panel-right">
      <MarkdownViewer :content="markdown" />
    </div>
  </div>
</template>
