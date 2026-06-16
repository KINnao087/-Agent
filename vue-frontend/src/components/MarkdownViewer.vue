<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'

const props = defineProps<{ content: string }>()

const html = computed(() => {
  if (!props.content) return ''
  return marked(props.content) as string
})
</script>

<template>
  <div v-if="content" class="markdown-body" v-html="html" />
  <p v-else class="empty-state">报告尚未生成，请先完成审核。</p>
</template>

<style>
.markdown-body {
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-primary);
}
.markdown-body h1 {
  font-size: 20px;
  margin: 20px 0 10px;
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 8px;
}
.markdown-body h2 { font-size: 17px; margin: 18px 0 8px; }
.markdown-body h3 { font-size: 15px; margin: 14px 0 6px; }
.markdown-body p { margin: 8px 0; }
.markdown-body code {
  background: var(--bg-tertiary);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
  color: var(--accent);
}
.markdown-body pre {
  background: var(--bg-tertiary);
  padding: 14px;
  border-radius: var(--radius-sm);
  overflow-x: auto;
}
.markdown-body pre code { background: none; padding: 0; color: var(--text-primary); }
.markdown-body table { border-collapse: collapse; width: 100%; margin: 10px 0; }
.markdown-body th, .markdown-body td {
  border: 1px solid var(--border-color);
  padding: 8px 12px;
  text-align: left;
}
.markdown-body th {
  background: var(--bg-tertiary);
  font-weight: 600;
}
.markdown-body ul, .markdown-body ol { padding-left: 24px; margin: 6px 0; }
.markdown-body blockquote {
  border-left: 4px solid var(--accent);
  padding: 10px 16px;
  color: var(--text-secondary);
  margin: 12px 0;
  background: var(--accent-light);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
}
</style>
