import api from './client'

export const getActivities = () => api.get('/api/activities')
export const syncStrava = () => api.post('/api/activities/sync-strava')
