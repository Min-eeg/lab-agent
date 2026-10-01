// 文件/图片 URL 解析：后端返回的是相对路径（如 /uploads/xxx.png），
// 而前端(5173)与后端(8000)不同源，直接当 img src 会请求到前端域名导致 404，
// 因此需要统一补全成后端的绝对地址。
const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

export function resolveFileUrl(url) {
  if (!url) return ''
  // 已经是完整地址（http/https 或 data/base64）则原样返回
  if (/^(https?:|data:|blob:)/i.test(url)) return url
  return API_BASE + (url.startsWith('/') ? url : '/' + url)
}
