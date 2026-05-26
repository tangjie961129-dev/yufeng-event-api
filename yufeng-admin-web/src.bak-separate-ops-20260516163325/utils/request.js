import axios from 'axios'

const request = axios.create({
  baseURL: '/api/admin',
  timeout: 15000,
})

request.interceptors.request.use((config) => {
  const token = localStorage.getItem('yf_admin_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

request.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('yf_admin_token')
      localStorage.removeItem('yf_admin_user')
      const currentPath = window.location.pathname
      if (!currentPath.endsWith('/login')) {
        window.location.href = '/admin/login'
      }
    }
    return Promise.reject(error)
  }
)

export default request
