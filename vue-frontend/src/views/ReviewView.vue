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
const reviewing = ref(false)
const error = ref('')
const markdown = ref('')
let eventSource: EventSource | null = null

onMounted(async () => {
  const id = Number(route.params.id)
  try {
    const res = await contractsApi.get(id)
    contract.value = res.data
    // 只要有 reviewId 就尝试加载报告（有报告就展示，没有就空）
    if (res.data.reviewId) {
      loadMarkdown()
    }
  } catch (e: any) {
    error.value = '加载合同失败'
  }
})

async function loadMarkdown() {
  if (!contract.value) return
  try {
    const res = await contractsApi.getReportMarkdown(contract.value.id)
    markdown.value = res.data
  } catch { markdown.value = '' }
}

async function startReview() {
  if (!contract.value) return
  reviewing.value = true
  events.value = []
  error.value = ''
  markdown.value = ''

  try {
    await contractsApi.startReview(contract.value.id)
  } catch (e: any) {
    error.value = '发起审核失败: ' + (e.response?.data?.message || e.message)
    reviewing.value = false
    return
  }

  const url = `/api/contracts/${contract.value.id}/review/stream?token=${encodeURIComponent(auth.token)}`
  eventSource = new EventSource(url)

  eventSource.onmessage = (e) => {
    try {
      const evt = JSON.parse(e.data)
      events.value.push(evt)
      if (evt.kind === 'final') {
        reviewing.value = false
        eventSource?.close()
        // 更新本地状态为已完成
        if (contract.value) contract.value.status = 'completed'
        // 审核完成，拉取 Markdown 报告
        loadMarkdown()
      }
      if (evt.kind === 'error') {
        reviewing.value = false
        eventSource?.close()
      }
    } catch { /* skip */ }
  }

  eventSource.onerror = () => {
    reviewing.value = false
    eventSource?.close()
  }
}

function cancelReview() {
  eventSource?.close()
  reviewing.value = false
  if (contract.value) {
    contractsApi.cancelReview(contract.value.id).catch(() => {})
  }
}

onUnmounted(() => {
  eventSource?.close()
})
</script>

<template>
  <div class="split-layout">
    <!-- 左栏：合同信息 -->
    <div class="panel-left card">
      <h3 v-if="contract">{{ contract.title }}</h3>
      <div v-if="contract" style="margin:8px 0">
        <span :class="'status-tag status-' + contract.status">
          {{ { pending:'待审核',reviewing:'审核中',completed:'已完成',failed:'失败' }[contract.status] }}
        </span>
      </div>
      <div v-if="error" style="color:#f56c6c">{{ error }}</div>
      <div style="margin-top:16px">
        <button v-if="!reviewing" class="btn btn-primary" @click="startReview">
          开始审核
        </button>
        <button v-else class="btn btn-danger" @click="cancelReview">
          取消审核
        </button>
      </div>
    </div>

    <!-- 中栏：AI 执行追踪树 -->
    <div class="panel-center card">
      <h3 style="margin-bottom:12px">AI 执行追踪</h3>
      <div v-if="events.length === 0" style="color:#909399">
        点击「开始审核」启动 AI 审核流程
      </div>
      <ExecutionTree :events="events" />
      <div v-if="reviewing" style="color:#409eff;margin-top:8px">⟳ 审核进行中...</div>
    </div>

    <!-- 右栏：审核报告 Markdown -->
    <div class="panel-right card">
      <h3 style="margin-bottom:12px">审核报告</h3>
      <MarkdownViewer :content="markdown" />
    </div>
  </div>
</template>
