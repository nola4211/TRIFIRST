import api from './client'

export const getCalendar = () => api.get('/api/calendar')
export const scheduleWorkout = (workout) => api.post('/api/calendar/workouts', workout)
export const confirmWorkouts = (payload) => api.post('/api/calendar/confirm', payload)
