import api from './client'

export const chat = (message) => api.post('/api/coach/chat', message)
export const getChatHistory = () => api.get('/api/coach/history')
