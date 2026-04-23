import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'

const ACCESS_TOKEN_KEY = 'bom_access_token'
const REFRESH_TOKEN_KEY = 'bom_refresh_token'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
})

interface RetryConfig extends InternalAxiosRequestConfig {
  _retry?: boolean
}

export const tokenStorage = {
  getAccessToken: (): string => localStorage.getItem(ACCESS_TOKEN_KEY) ?? '',
  getRefreshToken: (): string => localStorage.getItem(REFRESH_TOKEN_KEY) ?? '',
  setTokens: (access: string, refresh: string): void => {
    localStorage.setItem(ACCESS_TOKEN_KEY, access)
    localStorage.setItem(REFRESH_TOKEN_KEY, refresh)
  },
  clearTokens: (): void => {
    localStorage.removeItem(ACCESS_TOKEN_KEY)
    localStorage.removeItem(REFRESH_TOKEN_KEY)
  },
}

apiClient.interceptors.request.use((config) => {
  const accessToken = tokenStorage.getAccessToken()
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as RetryConfig | undefined
    if (!originalRequest || error.response?.status !== 401 || originalRequest._retry) {
      return Promise.reject(error)
    }

    const refresh = tokenStorage.getRefreshToken()
    if (!refresh) {
      tokenStorage.clearTokens()
      return Promise.reject(error)
    }

    try {
      originalRequest._retry = true
      const refreshResponse = await axios.post<{ access: string }>(
        `${API_BASE_URL}/auth/refresh/`,
        { refresh },
      )

      tokenStorage.setTokens(refreshResponse.data.access, refresh)
      originalRequest.headers.Authorization = `Bearer ${refreshResponse.data.access}`
      return apiClient(originalRequest)
    } catch (refreshError) {
      tokenStorage.clearTokens()
      return Promise.reject(refreshError)
    }
  },
)