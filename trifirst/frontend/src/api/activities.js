import api from './client'

export const getActivities = (userId) => api.get(`/activities/${userId}`)
export const syncStrava = (userId) => api.post('/sync/strava', { user_id: userId })
