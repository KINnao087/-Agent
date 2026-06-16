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
  return { pending: '待审核', reviewing: '审核中', completed: '已完成', failed: '失败' }[s] || s
}
</script>

<template>
  <div class="page">
    <h2 style="margin-bottom:20px">我的合同</h2>
    <p v-if="loading">加载中...</p>
    <div v-else-if="contracts.length === 0" style="color:#909399">
      还没有合同，<router-link to="/contracts/upload">上传一份</router-link>
    </div>
    <div v-else style="display:flex;flex-wrap:wrap;gap:16px">
      <div v-for="c in contracts" :key="c.id" class="card" style="width:320px">
        <h3>{{ c.title }}</h3>
        <div style="margin:8px 0">
          <span :class="'status-tag status-' + c.status">{{ statusLabel(c.status) }}</span>
        </div>
        <div style="font-size:12px;color:#909399">创建于 {{ new Date(c.createdAt).toLocaleString() }}</div>
        <router-link :to="'/contracts/' + c.id + '/review'">
          <button class="btn btn-primary" style="margin-top:12px">查看审核</button>
        </router-link>
      </div>
    </div>
  </div>
</template>
