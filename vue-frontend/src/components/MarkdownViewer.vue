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
  <p v-else style="color:#909399">报告尚未生成，请先完成审核。</p>
</template>

<style>
.markdown-body { font-size:14px; line-height:1.7; color:#333; }
.markdown-body h1 { font-size:20px; margin:16px 0 8px; border-bottom:1px solid #e4e7ed; padding-bottom:8px; }
.markdown-body h2 { font-size:17px; margin:14px 0 6px; }
.markdown-body h3 { font-size:15px; margin:12px 0 4px; }
.markdown-body p { margin:6px 0; }
.markdown-body code { background:#f0f2f5; padding:2px 6px; border-radius:3px; font-size:13px; }
.markdown-body pre { background:#f6f8fa; padding:12px; border-radius:6px; overflow-x:auto; }
.markdown-body pre code { background:none; padding:0; }
.markdown-body table { border-collapse:collapse; width:100%; margin:8px 0; }
.markdown-body th, .markdown-body td { border:1px solid #dcdfe6; padding:8px 12px; text-align:left; }
.markdown-body th { background:#f5f7fa; font-weight:600; }
.markdown-body ul, .markdown-body ol { padding-left:24px; margin:4px 0; }
.markdown-body blockquote { border-left:4px solid #409eff; padding:8px 16px; color:#666; margin:8px 0; background:#ecf5ff; }
</style>
