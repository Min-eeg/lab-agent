<template>
  <div>
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span style="font-size: 16px; font-weight: bold">AI智能助手</span>
          <el-button size="small" @click="clearChat" :disabled="loading">清空对话</el-button>
        </div>
      </template>

      <div ref="listRef" class="chat-list" @scroll="onScroll">
        <div
          v-for="(item, index) in messages"
          :key="index"
          class="chat-row"
          :class="item.role"
        >
          <div class="bubble" :class="item.role">
            <!-- 工具调用过程：状态 + 流水（只给 assistant 显示） -->
            <div v-if="item.role === 'assistant' && item.status" class="status-line">
              {{ item.status }}
            </div>
            <div
              v-if="item.role === 'assistant' && item.steps?.length"
              class="steps-line"
            >
              <div v-for="(step, i) in item.steps" :key="i">· {{ step }}</div>
            </div>
            <div class="md-body" v-html="parseMarkdown(item.content)"></div>
          </div>
        </div>
      </div>

      <div style="margin-top: 12px; display: flex; gap: 8px; align-items: flex-end">
        <el-input
          v-model="draft"
          type="textarea"
          :rows="2"
          placeholder="问问实验室怎么预约、开放时间..."
          @keydown.enter.exact.prevent="handleSend"
          @keydown.enter.shift.stop
        ></el-input>
        <el-button type="primary" @click="handleSend" :loading="loading">发送</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, watch } from 'vue'
import { useUser } from '@/utils/user'
import { useChatStore } from '@/utils/chatStore'
import { marked } from 'marked'
import { ElMessage } from 'element-plus'
import DOMPurify from 'dompurify' // 过滤危险的 HTML，防止 XSS 攻击

const { userInfo } = useUser()

// 对话状态与流式任务都住在模块级 store 里:
// 路由切换销毁组件也不丢消息、不中断流, 切回来接着看(和 DeepSeek 一致)
const { messages, loading, draft, initChat, sendMessage, clearChat } = useChatStore()

const listRef = ref()

// 贴底跟随: 只有用户本来就在底部才自动滚动;
// 往上翻看历史时保持不动, 避免被强行拽回底部(DeepSeek 的行为)
const stickToBottom = ref(true)

const onScroll = () => {
  const elem = listRef.value
  if (!elem) return
  // 距底部 80px 以内视为"贴着底部"
  stickToBottom.value = elem.scrollHeight - elem.scrollTop - elem.clientHeight < 80
}

// force=true 用于"进入页面/刚发出消息"这类无条件滚到底的场景
const scrollToBottom = (force = false) => {
  nextTick(() => {
    const elem = listRef.value
    if (!elem) return
    if (!force && !stickToBottom.value) return
    elem.scrollTop = elem.scrollHeight
    // markdown 渲染后高度还会变一帧, 再兜一次
    requestAnimationFrame(() => {
      elem.scrollTop = elem.scrollHeight
    })
  })
}

onMounted(() => {
  initChat(userInfo.value?.username)
  scrollToBottom(true)
})

// deep 必须开: 发消息是 push、流式是不断追加 token,
 // 不加 deep 时 watch 只在整体替换数组时才触发, 长对话就滚不动了
watch(messages, () => scrollToBottom(), { deep: true })

const handleSend = async () => {
  const text = draft.value.trim()
  if (!text || loading.value) return
  draft.value = ''
  // 自己发了消息, 一定滚到底看自己的问题和后续回复
  stickToBottom.value = true
  await sendMessage(text, {
    onEvent: (evt) => {
      // 状态变更都在 store 里完成, 组件只负责提示类视图反应
      if (evt.type === 'error') {
        ElMessage.error(evt.message || '请求失败')
      }
    }
  })
}

// 将 markdown 字符串转换为安全的 HTML 字符串
const parseMarkdown = (text) => {
  if (!text) return ''
  marked.setOptions({ breaks: true }) // 把 \n 转换成 <br>
  // 使用 marked 解析，然后用 DOMPurify 清理
  const rawHtml = marked.parse(text)
  return DOMPurify.sanitize(rawHtml)
}
</script>

<style scoped>
/* ---------- 消息区 ---------- */
.chat-list {
  height: 520px;
  overflow-y: auto;
  padding: 14px 10px;
  background-color: #fafafa;
  border-radius: 8px;
}

.chat-row {
  display: flex;
  margin-bottom: 14px;
}
.chat-row.user {
  justify-content: flex-end;
}
.chat-row.assistant {
  justify-content: flex-start;
}

/* ---------- 气泡 ---------- */
.bubble {
  max-width: 85%;
  padding: 10px 14px;
  border-radius: 10px;
  font-size: 14px;
  line-height: 1.7;
  word-break: break-word;
}
.bubble.user {
  background: #409eff;
  color: #fff;
  border-top-right-radius: 3px;
}
.bubble.assistant {
  background: #fff;
  color: #303133;
  border-top-left-radius: 3px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

/* 工具调用状态与过程流水 */
.status-line {
  font-size: 12px;
  color: #909399;
  margin-bottom: 6px;
}
.steps-line {
  font-size: 12px;
  color: #909399;
  line-height: 1.6;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px dashed #e4e7ed;
}

/* ---------- markdown 正文排版(关键: v-html 内容需 :deep 穿透) ---------- */
.md-body :deep(p) {
  margin: 0 0 8px;
}
.md-body :deep(p:last-child) {
  margin-bottom: 0;
}
/* AI 常用表格回复(实验室列表等), 不加样式会挤成一坨 */
.md-body :deep(table) {
  border-collapse: collapse;
  margin: 6px 0 10px;
  font-size: 13px;
  display: block;
  overflow-x: auto;
  white-space: nowrap;
}
.md-body :deep(th),
.md-body :deep(td) {
  border: 1px solid #e4e7ed;
  padding: 5px 12px;
  text-align: left;
}
.md-body :deep(th) {
  background: #f5f7fa;
  font-weight: 600;
}
.md-body :deep(ul),
.md-body :deep(ol) {
  margin: 4px 0 8px;
  padding-left: 20px;
}
.md-body :deep(li) {
  margin: 3px 0;
}
.md-body :deep(h1),
.md-body :deep(h2),
.md-body :deep(h3),
.md-body :deep(h4) {
  font-size: 15px;
  margin: 10px 0 6px;
}
.md-body :deep(code) {
  background: #f0f2f5;
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 13px;
}
.md-body :deep(pre) {
  background: #f6f8fa;
  padding: 10px 12px;
  border-radius: 6px;
  overflow-x: auto;
  margin: 6px 0 10px;
}
.md-body :deep(pre code) {
  background: none;
  padding: 0;
}
.md-body :deep(blockquote) {
  margin: 6px 0;
  padding: 4px 12px;
  border-left: 3px solid #dcdfe6;
  color: #606266;
}
</style>
