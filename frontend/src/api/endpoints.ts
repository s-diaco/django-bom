import { apiClient } from './client'
import type { MeResponse, PaginatedResponse, PartBomResponse, PartDetail, PartListRow } from '../types'

interface TokenPair {
  access: string
  refresh: string
}

export async function login(username: string, password: string): Promise<TokenPair> {
  const response = await apiClient.post<TokenPair>('/auth/login/', { username, password })
  return response.data
}

export async function fetchMe(): Promise<MeResponse> {
  const response = await apiClient.get<MeResponse>('/auth/me/')
  return response.data
}

export async function logout(refresh: string): Promise<void> {
  await apiClient.post('/auth/logout/', { refresh })
}

export async function fetchParts(params: {
  q?: string
  page?: number
  pageSize?: number
}): Promise<PaginatedResponse<PartListRow>> {
  const response = await apiClient.get<PaginatedResponse<PartListRow>>('/parts/', {
    params: {
      q: params.q || undefined,
      page: params.page,
      page_size: params.pageSize,
    },
  })
  return response.data
}

export async function fetchPartDetail(partId: string): Promise<PartDetail> {
  const response = await apiClient.get<PartDetail>(`/parts/${partId}/`)
  return response.data
}

export async function fetchPartBom(params: {
  partId: string
  view: 'indented' | 'flat'
  quantity: number
}): Promise<PartBomResponse> {
  const response = await apiClient.get<PartBomResponse>(`/parts/${params.partId}/bom/`, {
    params: {
      view: params.view,
      quantity: params.quantity,
    },
  })
  return response.data
}