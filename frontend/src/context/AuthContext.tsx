import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import axios from 'axios'

import { fetchMe, login as loginRequest, logout as logoutRequest } from '../api/endpoints'
import { tokenStorage } from '../api/client'
import type { MeResponse } from '../types'

interface AuthContextValue {
  user: MeResponse | null
  isLoading: boolean
  isAuthenticated: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<MeResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const bootstrapAuth = useCallback(async () => {
    const access = tokenStorage.getAccessToken()
    if (!access) {
      setUser(null)
      setIsLoading(false)
      return
    }

    try {
      const me = await fetchMe()
      setUser(me)
    } catch {
      tokenStorage.clearTokens()
      setUser(null)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void bootstrapAuth()
  }, [bootstrapAuth])

  const login = useCallback(async (username: string, password: string) => {
    const tokens = await loginRequest(username, password)
    tokenStorage.setTokens(tokens.access, tokens.refresh)

    const me = await fetchMe()
    setUser(me)
  }, [])

  const logout = useCallback(async () => {
    const refresh = tokenStorage.getRefreshToken()

    if (refresh) {
      try {
        await logoutRequest(refresh)
      } catch (error) {
        if (!axios.isAxiosError(error) || error.response?.status !== 400) {
          throw error
        }
      }
    }

    tokenStorage.clearTokens()
    setUser(null)
  }, [])

  const value = useMemo(
    () => ({
      user,
      isLoading,
      isAuthenticated: Boolean(user),
      login,
      logout,
    }),
    [user, isLoading, login, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}