import axios from "axios"
import { getToken, logout } from "./auth"
import router from '@/router'
import { ElMessage } from "element-plus"

const service = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || ' ', // 设置基础URL
  timeout: 30000, // 设置请求超时时间
})

// 请求拦截的配置
service.interceptors.request.use(
  (config) => {
    const token = getToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (err) => Promise.reject(err)
)

//返回的拦截的配置
service.interceptors.response.use(
  (res) => {
    const data = res.data
    if (data.code !== 200) {
      ElMessage.error(data.message || '请求失败')
      if (data.code === 401) {
        logout()
        router.push('/login')
        return Promise.reject(data)
      }
    }
    return data
  },
  (err) => {
    if (err.response) {
      const httpStatusCode = err.response.status
      if (httpStatusCode === 401) {
        ElMessage.error('登录状态已失效，请重新登录')
        logout()
        router.push('/login')
      } else {
        ElMessage.error(err.response.data?.message || '请求失败')
      }
    } else {
      // 后端没启动，网络异常了
      ElMessage.error('网络异常，请检查后端服务')
    }
    return Promise.reject(err)
  }
)

export default service