import axios from 'axios'

const api = axios.create({ baseURL: 'http://localhost:8000' })

// Attach user_id to every request from localStorage if available
api.interceptors.request.use((config) => {
  const user = JSON.parse(localStorage.getItem('trifirst_user') || '{}')
  if (user.user_id) {
    config.headers['X-User-Id'] = user.user_id
  }
  return config
})

export default api
