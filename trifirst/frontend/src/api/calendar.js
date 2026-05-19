import api from './client'

export const getCalendar = (userId, month) => api.get(`/calendar/${userId}`, { params: { month } })
export const scheduleWorkout = (workout) => api.post('/calendar/workout', workout)
export const updateWorkoutStatus = (workoutId, status) => api.patch(`/calendar/workout/${workoutId}`, { status })
export const deleteWorkout = (workoutId) => api.delete(`/calendar/workout/${workoutId}`)
export const getPendingWorkouts = (userId) => api.get(`/calendar/pending/${userId}`)
export const confirmWorkouts = (payload) => api.post('/calendar/confirm', payload)
export const dismissPending = (pendingId) => api.delete(`/calendar/pending/${pendingId}`)
