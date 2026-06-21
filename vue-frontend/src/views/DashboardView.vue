<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { contractsApi, type ContractItem } from '@/api/contracts'

const contracts = ref<ContractItem[]>([])
const loading = ref(true)
const deleting = ref<number | null>(null)

onMounted(async () => {
  try {
    const res = await contractsApi.list()
    contracts.value = res.data
  } finally {
    loading.value = false
  }
})

function statusLabel(s: string) {
  const labels: Record<string, string> = {
    pending:        '未审核',
    reviewing:      '审核中',
    pending_review: '待复审',
    completed:      '已完成',
    failed:         '失败',
  }
  return labels[s] || s
}

async function handleDelete(contractId: number) {
  if (!confirm('确定要删除这份合同吗？此操作不可撤销。')) {
    return
  }
  deleting.value = contractId
  try {
    await contractsApi.delete(contractId)
    contracts.value = contracts.value.filter(c => c.id !== contractId)
  } catch (e: any) {
    alert(e.response?.data?.message || '删除失败')
  } finally {
    deleting.value = null
  }
}
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h2>我的合同</h2>
    </div>

    <p v-if="loading" class="loading">加载中...</p>

    <div v-else-if="contracts.length === 0" class="empty-state">
      <p>还没有合同，<router-link to="/contracts/upload">上传一份</router-link></p>
    </div>

    <div v-else style="display:flex;flex-wrap:wrap;gap:16px">
      <div v-for="c in contracts" :key="c.id" class="card" style="width:340px">
        <h3 style="font-size:15px;margin-bottom:10px">{{ c.title }}</h3>
        <div style="margin:10px 0">
          <span :class="'status-tag status-' + c.status">{{ statusLabel(c.status) }}</span>
        </div>
        <div style="font-size:12px;color:var(--text-tertiary)">创建于 {{ new Date(c.createdAt).toLocaleString() }}</div>
        <div style="display:flex;gap:8px;margin-top:14px">
          <router-link :to="'/contracts/' + c.id + '/review'" style="flex:1">
            <button class="btn btn-primary" style="width:100%">查看审核</button>
          </router-link>
          <button
            class="btn btn-danger"
            :disabled="deleting === c.id"
            @click="handleDelete(c.id)"
          >
            {{ deleting === c.id ? '删除中...' : '删除' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
