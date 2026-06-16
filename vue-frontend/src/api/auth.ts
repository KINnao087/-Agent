import client from './client'

export const authApi = {
  login(email: string, password: string) {
    return client.post('/auth/login', { email, password })
  },
  register(username: string, email: string, password: string) {
    return client.post('/auth/register', { username, email, password })
  },
  me() {
    return client.get('/auth/me')
  },
}
