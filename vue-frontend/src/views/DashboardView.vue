<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { contractsApi, type ContractItem } from '@/api/contracts'

const contracts = ref<ContractItem[]>([])
const loading = ref(true)

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
        <router-link :to="'/contracts/' + c.id + '/review'">
          <button class="btn btn-primary" style="margin-top:14px;width:100%">查看审核</button>
        </router-link>
      </div>
    </div>
  </div>
</template>
