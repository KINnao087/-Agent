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
let eventSource: EventSource | null = null

const STATUS_LABELS: Record<string, string> = {
  pending:        '未审核',
  reviewing:      '审核中',
  pending_review: '待复审',
  completed:      '已完成',
  failed:         '失败',
}

function statusLabel(s: string) {
  return STATUS_LABELS[s] || s
}

// ---- 连接 SSE 流（不调 start API，仅重连） ----
function connectStream() {
  if (!contract.value?.id) return

  closeStream()
  streaming.value = true

  const url = `/api/contracts/${contract.value.id}/review/stream?token=${encodeURIComponent(auth.token)}`
  eventSource = new EventSource(url)

  eventSource.onmessage = (e) => {
    try {
      const evt = JSON.parse(e.data)
      events.value.push(evt)

      if (evt.kind === 'final') {
        streaming.value = false
        eventSource?.close()
        if (contract.value) {
          contract.value.status = 'pending_review'
          contractsApi.updateStatus(contract.value.id, 'pending_review').catch(() => {})
        }
        loadMarkdown()
      }

      if (evt.kind === 'error') {
        streaming.value = false
        eventSource?.close()
        if (contract.value) {
          contract.value.status = 'failed'
          contractsApi.updateStatus(contract.value.id, 'failed').catch(() => {})
        }
      }
    } catch { /* skip */ }
  }

  eventSource.onerror = () => {
    streaming.value = false
    eventSource?.close()
    // 只在审核中状态才标记失败（网络错误可能只是暂时的）
    if (contract.value && contract.value.status === 'reviewing') {
      contract.value.status = 'failed'
      contractsApi.updateStatus(contract.value.id, 'failed').catch(() => {})
    }
  }
}

function closeStream() {
  eventSource?.close()
  eventSource = null
  streaming.value = false
}

// ---- 生命周期 ----
onMounted(async () => {
  const id = Number(route.params.id)
  try {
    const res = await contractsApi.get(id)
    contract.value = res.data

    // 有报告就加载
    if (res.data.reviewId) {
      loadMarkdown()
    }

    // 审核中 → 自动重连 SSE
    if (res.data.status === 'reviewing') {
      connectStream()
    }
  } catch (e: any) {
    error.value = '加载合同失败'
  }
})

onUnmounted(() => closeStream())

// ---- 操作 ----
async function loadMarkdown() {
  if (!contract.value) return
  try {
    const res = await contractsApi.getReportMarkdown(contract.value.id)
    markdown.value = res.data
  } catch { markdown.value = '' }
}

async function startReview() {
  if (!contract.value) return
  events.value = []
  error.value = ''
  markdown.value = ''

  try {
    await contractsApi.startReview(contract.value.id)
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
  if (contract.value) {
    contractsApi.cancelReview(contract.value.id).catch(() => {})
    contract.value.status = 'failed'
  }
}
</script>

<template>
  <div class="split-layout">
    <!-- 左栏 -->
    <div class="panel-left">
      <h3 v-if="contract" style="font-size:16px;margin-bottom:10px">{{ contract.title }}</h3>

      <div v-if="contract" style="margin:10px 0">
        <span :class="'status-tag status-' + contract.status">
          {{ statusLabel(contract.status) }}
        </span>
      </div>

      <div v-if="error" class="error-msg">{{ error }}</div>

      <div style="margin-top:20px;display:flex;flex-direction:column;gap:8px">
        <!-- 未审核 → 开始审核 -->
        <button
          v-if="contract && contract.status === 'pending'"
          class="btn btn-primary" style="width:100%" @click="startReview"
        >
          开始审核
        </button>

        <!-- 审核中 → 取消（不管 streaming 标志，状态是 reviewing 就显示） -->
        <button
          v-if="contract && contract.status === 'reviewing'"
          class="btn btn-danger" style="width:100%" @click="cancelReview"
        >
          取消审核
        </button>

        <!-- 待复审 → 审核通过 -->
        <button
          v-if="contract && contract.status === 'pending_review'"
          class="btn btn-primary" style="width:100%" :disabled="approving"
          @click="approveReview"
        >
          {{ approving ? '提交中...' : '✅ 审核通过' }}
        </button>

        <!-- 审核中/待复审/已完成/失败 → 重新审核（始终可重试） -->
        <button
          v-if="contract && contract.status !== 'pending'"
          class="btn btn-ghost" style="width:100%" @click="startReview"
        >
          重新审核
        </button>
      </div>
    </div>

    <!-- 中栏 -->
    <div class="panel-center">
      <div v-if="events.length === 0" class="empty-state">
        <p v-if="contract && contract.status === 'pending'">点击「开始审核」启动 AI 审核流程</p>
        <p v-else-if="contract && contract.status === 'reviewing'">正在重连审核流...</p>
        <p v-else-if="contract && contract.status === 'pending_review'">AI 审核已完成，请查看右侧报告并确认</p>
        <p v-else-if="contract && contract.status === 'completed'">审核已通过</p>
        <p v-else>暂无执行记录</p>
      </div>
      <ExecutionTree :events="events" />
      <div v-if="streaming" style="color:var(--accent);margin-top:8px;font-size:14px">⟳ 审核进行中...</div>
    </div>

    <!-- 右栏 -->
    <div class="panel-right">
      <MarkdownViewer :content="markdown" />
    </div>
  </div>
</template>
