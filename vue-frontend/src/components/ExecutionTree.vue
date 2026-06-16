<script setup lang="ts">
defineProps<{ events: any[] }>()

function iconFor(kind: string): string {
  const icons: Record<string, string> = {
    turn_start: '▶', decision: '🧠', tool_start: '🔧',
    tool_result: '📋', final: '✅', error: '❌',
  }
  return icons[kind] || '•'
}

function colorFor(kind: string, event: any): string {
  if (event.is_error) return '#f56c6c'
  if (kind === 'final') return '#67c23a'
  if (kind === 'tool_result') return '#409eff'
  if (kind === 'tool_start') return '#e6a23c'
  if (kind === 'decision') return '#909399'
  return '#606266'
}

function formatMs(ms: number | null): string {
  if (!ms) return ''
  return ms > 1000 ? `${(ms / 1000).toFixed(1)}s` : `${Math.round(ms)}ms`
}
</script>

<template>
  <div style="font-family:monospace;font-size:13px;line-height:1.8">
    <div v-for="(evt, i) in events" :key="i" style="padding:4px 0;border-bottom:1px solid #f0f0f0">
      <span style="margin-right:6px">{{ iconFor(evt.kind) }}</span>
      <span :style="{ color: colorFor(evt.kind, evt) }">
        <strong v-if="evt.tool_name">{{ evt.tool_name }}</strong>
        <span v-else>{{ evt.summary }}</span>
      </span>
      <span v-if="evt.elapsed_ms" style="color:#909399;margin-left:8px;font-size:12px">
        {{ formatMs(evt.elapsed_ms) }}
      </span>
      <!-- 最终结果展示完整内容 -->
      <div v-if="evt.kind === 'final' && evt.detail"
           style="margin-top:8px;padding:12px;background:#f9fafb;border-radius:6px;
                  white-space:pre-wrap;font-size:13px;line-height:1.6;color:#333;
                  max-height:400px;overflow-y:auto">
        {{ evt.detail }}
      </div>
      <!-- 工具出错时展示错误详情 -->
      <div v-if="evt.is_error && evt.detail"
           style="margin-top:4px;padding:8px;background:#fef0f0;border-radius:4px;
                  white-space:pre-wrap;font-size:12px;color:#f56c6c;
                  max-height:200px;overflow-y:auto">
        {{ evt.detail }}
      </div>
    </div>
  </div>
</template>
