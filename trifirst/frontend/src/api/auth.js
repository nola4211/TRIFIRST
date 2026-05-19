import api from './client'

export const login = (credentials) => api.post('/api/auth/login', credentials)
export const register = (payload) => api.post('/api/auth/register', payload)
export const getUser = () => api.get('/api/auth/me')
