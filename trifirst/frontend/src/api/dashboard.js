import api from './client'

export const getRaceGoal = () => api.get('/api/dashboard/race-goal')
export const getDigests = () => api.get('/api/dashboard/digests')
export const getRaceCalculator = () => api.get('/api/dashboard/race-calculator')
