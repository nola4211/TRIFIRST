import api from './client'

export const chat = (userId, message) => api.post('/coach/chat', { user_id: userId, message })
export const getChatHistory = (userId) => api.get(`/coach/history/${userId}`)
export const getAthleteProfile = (userId) => api.get(`/athlete-profile/${userId}`)
export const saveAthleteProfile = (payload) => api.post('/athlete-profile', payload)
