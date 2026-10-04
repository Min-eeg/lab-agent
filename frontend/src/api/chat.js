import request from '@/utils/request'

/** 拉取当前用户最近的对话记录（后端落库，换设备可恢复） */
export function getChatHistoryApi() {
  return request({
    url: '/api/chat/history',
    method: 'get'
  })
}

/** 清空当前用户的全部对话记录（对应「清空对话」按钮） */
export function clearChatHistoryApi() {
  return request({
    url: '/api/chat/history',
    method: 'delete'
  })
}
