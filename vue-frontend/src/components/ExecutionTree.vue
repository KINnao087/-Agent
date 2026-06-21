<script setup lang="ts">
defineProps<{ events: any[] }>()

function iconFor(kind: string): string {
  const icons: Record<string, string> = {
    turn_start: '▶', decision: '🧠', tool_start: '🔧',
    tool_result: '📋', final: '✅', error: '❌',
  }
  return icons[kind] || '•'
}

function rowClass(kind: string, evt: any): string {
  if (evt.is_error) return 'row-error'
  return 'row-' + (kind || 'default')
}

function formatMs(ms: number | null): string {
  if (!ms) return ''
  return ms > 1000 ? `${(ms / 1000).toFixed(1)}s` : `${Math.round(ms)}ms`
}
</script>

<template>
  <div class="exec-tree">
    <div v-for="(evt, i) in events" :key="evt.seq || i" class="exec-row">
      <span class="exec-icon">{{ iconFor(evt.kind) }}</span>
      <span :class="'exec-text ' + rowClass(evt.kind, evt)">
        <strong v-if="evt.tool_name">{{ evt.tool_name }}</strong>
        <span v-else>{{ evt.summary }}</span>
      </span>
      <span v-if="evt.elapsed_ms" class="exec-time">{{ formatMs(evt.elapsed_ms) }}</span>

      <!-- 最终结果 -->
      <div v-if="evt.kind === 'final' && evt.detail" class="exec-final">
        {{ evt.detail }}
      </div>

      <!-- 工具错误 -->
      <div v-if="evt.is_error && evt.detail" class="exec-error-detail">
        {{ evt.detail }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.exec-tree {
  font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', Consolas, monospace;
  font-size: 13px;
  line-height: 1.8;
}

.exec-row {
  padding: 5px 0;
  border-bottom: 1px solid var(--border-light);
}

.exec-icon { margin-right: 6px; }

.exec-text.row-final     { color: var(--success); }
.exec-text.row-tool_result { color: var(--accent); }
.exec-text.row-tool_start { color: var(--warning); }
.exec-text.row-decision   { color: var(--text-tertiary); }
.exec-text.row-error      { color: var(--danger); }
.exec-text.row-default    { color: var(--text-secondary); }

.exec-time {
  color: var(--text-tertiary);
  margin-left: 8px;
  font-size: 12px;
}

.exec-final {
  margin-top: 8px;
  padding: 14px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-sm);
  white-space: pre-wrap;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-primary);
  max-height: 400px;
  overflow-y: auto;
}

.exec-error-detail {
  margin-top: 4px;
  padding: 10px 12px;
  background: var(--danger-light);
  border-radius: 6px;
  white-space: pre-wrap;
  font-size: 12px;
  color: var(--danger);
  max-height: 200px;
  overflow-y: auto;
}
</style>
