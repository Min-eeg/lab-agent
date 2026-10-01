import request from '@/utils/request'

export function loginApi(data) {
    return request({
        url: '/api/auth/login',
        method: 'post',
        data
    })
}

//注册请求
export function registerApi(data) {
    return request({
        url: '/api/auth/register',
        method: 'post',
        data
    })
}