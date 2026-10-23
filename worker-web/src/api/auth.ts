import api from '../lib/axios'

export interface LoginPayload {
  username: string
  pin: string
}

export async function login(payload: LoginPayload) {
  const res = await api.post('/v1/auth/login/', payload)
  if (res.data?.access) {
    localStorage.setItem('access_token', res.data.access)
  }
  if (res.data?.refresh) {
    localStorage.setItem('refresh_token', res.data.refresh)
  }
  return res.data
}

export async function getMe() {
  const res = await api.get('/v1/auth/me/')
  return res.data
}
