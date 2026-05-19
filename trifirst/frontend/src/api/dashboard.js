import api from './client'

export const getRaceGoal = (userId) => api.get(`/race-goal/${userId}`)
export const getFitnessBackground = (userId) => api.get(`/fitness-background/${userId}`)
export const saveRaceGoal = (payload) => api.post('/race-goal', payload)
export const getDigests = (userId) => api.get(`/digest/${userId}`)
export const generateDigest = (userId) => api.post('/digest/generate', { user_id: userId })
export const getRaceCalculator = (userId) => api.get(`/race-calculator/${userId}`)
