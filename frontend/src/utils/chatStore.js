import { ref, reactive, watch } from 'vue'
import { chatStreamApi } from '@/api/ai'
import { getChatHistoryApi, clearChatHistoryApi } from '@/api/chat'

/**
 * 对话模块级 store（单例）。
 *
 * 为什么不放组件里: 路由切换会销毁组件, 内存消息和进行中的流式请求都会跟着丢。
 * 状态放在模块作用域: 组件只是视图, 切走后流继续跑、字继续拼, 切回来接着看。
 * 持久化两层: 后端 MySQL 为主(换设备登录也能看到历史), localStorage 为兜底(后端不可用时还能恢复)。
 * 后端写入由流式接口在 done 时自动完成, 前端只负责「读取」和「清空」。
 */

const WELCOME = {
  role: 'assistant',
  content:
    '你好，我是实验室预约助手。可以问规则和开放实验室，也可以说「帮我预约明天下午的实验室」，确认后我会帮你提交。'
}

// 模块级单例状态
const messages = ref([])
const loading = ref(false)
// 输入框草稿也放这里: 切页面组件销毁后草稿还在(和消息同一套持久化)
const draft = ref('')
let currentUsername = null

const storageKey = () => `lab_agent_chat_${currentUsername || 'guest'}`
const draftKey = () => `lab_agent_chat_draft_${currentUsername || 'guest'}`

// 只存 role/content; status、steps 是临时 UI 状态; content 为空的不存(流式中途残留)
function plainMessages() {
  return messages.value
    .filter(
      (item) =>
        (item.role === 'user' || item.role === 'assistant') &&
        String(item.content || '').trim()
    )
    .map(({ role, content }) => ({ role, content }))
}

function save() {
  if (!currentUsername) return
  try {
    localStorage.setItem(storageKey(), JSON.stringify(plainMessages()))
  } catch {
    // 存储异常不阻塞聊天
  }
}

// 模块级 watch 永不销毁: 流式期间每个 token 都会触发保存, 消息量小, 简单可靠
watch(messages, save, { deep: true })

// 草稿单独落盘: 切页面/刷新后回到输入框, 之前打到一半的话还在
watch(draft, (val) => {
  if (!currentUsername) return
  try {
    if (val) localStorage.setItem(draftKey(), val)
    else localStorage.removeItem(draftKey())
  } catch {
    // 存储异常不阻塞输入
  }
})

function loadDraft() {
  try {
    draft.value = localStorage.getItem(draftKey()) || ''
  } catch {
    draft.value = ''
  }
}

// 同步版本号: initChat / sendMessage 都会自增。异步拉历史返回时版本已变,
// 说明等待期间用户有了新动作(换账号/已发新消息), 直接丢弃这次结果, 防止覆盖新状态
let syncVersion = 0

// 后端是历史记录的主数据源: 拉到就以后端为准(包括"后端为空"——可能在别的设备清空了),
// 只有请求失败才保留 localStorage 兜底内容
async function loadHistoryFromServer(version) {
  try {
    const res = await getChatHistoryApi()
    if (version !== syncVersion) return
    const list = (res?.data?.messages || [])
      .filter((item) => String(item.content || '').trim())
      .map(({ role, content }) => ({ role, content }))
    if (list.length) {
      messages.value = list
    } else {
      // 后端没有记录: 本地缓存是别的设备清空前的残留, 一并作废
      messages.value = [{ ...WELCOME }]
      try {
        localStorage.removeItem(storageKey())
      } catch {}
    }
  } catch {
    // 后端不可用: 不打扰用户, 继续用本地缓存
  }
}

// 进入页面时调用: 同一用户直接复用内存状态(切页面回来流式还在继续), 换用户才读缓存
function initChat(username) {
  if (currentUsername === username && messages.value.length) return
  currentUsername = username || null
  try {
    const raw = localStorage.getItem(storageKey())
    const list = raw ? JSON.parse(raw) : null
    messages.value =
      Array.isArray(list) && list.length
        ? list.filter((item) => String(item.content || '').trim())
        : []
  } catch {
    messages.value = []
  }
  if (!messages.value.length) messages.value = [{ ...WELCOME }]
  loadDraft()
  loadHistoryFromServer(++syncVersion) // 异步覆盖: 本地缓存先上屏, 后端记录到了再以它为准
}

// 发送一条消息并消费 SSE 流。onEvent 供组件做提示等视图反应, 不参与状态管理
async function sendMessage(text, { onEvent } = {}) {
  const content = String(text || '').trim()
  if (!content || loading.value) return
  syncVersion++ // 用户已经开始新对话, 作废任何还没返回的历史拉取, 免得新消息被旧历史盖掉

  messages.value.push({ role: 'user', content })
  // 必须用 reactive: 普通对象 push 后再改字段, 视图可能不更新
  const assistant = reactive({
    role: 'assistant',
    content: '',
    status: '正在思考…',
    steps: []
  })
  messages.value.push(assistant)
  loading.value = true

  try {
    // 历史只传纯文本(role/content), 空 assistant 已被过滤
    const history = plainMessages()
    await chatStreamApi({ messages: history }, (evt) => {
      if (evt.type === 'status') {
        assistant.status = evt.message || '正在思考…'
      } else if (evt.type === 'tool_start') {
        const label = evt.label || evt.name || '工具'
        assistant.status = `正在${label}…`
        assistant.steps.push(`开始：${label}`)
      } else if (evt.type === 'tool_end') {
        const label = evt.label || evt.name || '工具'
        assistant.status = `${label}完成`
        assistant.steps.push(`完成：${label}`)
      } else if (evt.type === 'token') {
        assistant.content += evt.content || '' // 打字机：追加，不是覆盖
        assistant.status = '' // 开始出字后清掉「正在…」
      } else if (evt.type === 'done') {
        assistant.status = ''
      } else if (evt.type === 'error') {
        assistant.status = ''
        if (!assistant.content) {
          assistant.content = evt.message || '请求失败'
        }
      }
      onEvent?.(evt)
    })
  } catch (err) {
    assistant.status = ''
    if (!assistant.content) {
      assistant.content = err.message || '网络异常'
    }
    onEvent?.({ type: 'error', message: err.message || '网络异常' })
  } finally {
    loading.value = false
    assistant.status = ''
    save() // 兜底: 确保流结束后的完整内容已落盘
  }
}

function clearChat() {
  messages.value = [{ ...WELCOME }]
  draft.value = ''
  try {
    localStorage.removeItem(storageKey())
  } catch {}
  // 后端记录同步清掉: 否则换设备登录旧对话又冒出来
  clearChatHistoryApi().catch(() => {})
}

export function useChatStore() {
  return { messages, loading, draft, initChat, sendMessage, clearChat }
}
