import api from './client'

export const login = (credentials) => api.post('/auth/login', credentials)
export const register = (payload) => api.post('/auth/register', payload)
export const getUser = (userId) => api.get(`/auth/user/${userId}`)
