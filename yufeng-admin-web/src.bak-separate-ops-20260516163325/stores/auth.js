import { defineStore } from 'pinia'
import request from '../utils/request'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('yf_admin_token') || '',
    user: JSON.parse(localStorage.getItem('yf_admin_user') || 'null'),
  }),
  getters: {
    isLoggedIn: (state) => !!state.token,
  },
  actions: {
    async login(payload) {
      const data = await request.post('/auth/login', payload)
      this.token = data.token
      this.user = data.user
      localStorage.setItem('yf_admin_token', data.token)
      localStorage.setItem('yf_admin_user', JSON.stringify(data.user))
      return data
    },
    async fetchMe() {
      const data = await request.get('/auth/me')
      this.user = data
      localStorage.setItem('yf_admin_user', JSON.stringify(data))
      return data
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem('yf_admin_token')
      localStorage.removeItem('yf_admin_user')
    },
  },
})
