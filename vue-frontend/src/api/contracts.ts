import client from './client'

export interface ContractItem {
  id: number
  title: string
  filePath: string
  reviewId: string | null
  status: string
  createdAt: string
}

export const contractsApi = {
  list() {
    return client.get<ContractItem[]>('/contracts')
  },
  get(id: number) {
    return client.get<ContractItem>(`/contracts/${id}`)
  },
  create(formData: FormData) {
    // 不要手动设置 Content-Type，浏览器/axios 会自动带上 boundary
    return client.post<ContractItem>('/contracts', formData)
  },
  startReview(id: number) {
    return client.post(`/contracts/${id}/review`)
  },
  getReport(id: number) {
    return client.get(`/contracts/${id}/report`)
  },
  getReportMarkdown(id: number) {
    return client.get<string>(`/contracts/${id}/report/markdown`, { responseType: 'text' })
  },
  updateStatus(id: number, status: string) {
    return client.patch<ContractItem>(`/contracts/${id}/status`, { status })
  },
  cancelReview(id: number) {
    return client.delete(`/contracts/${id}/review`)
  },
  delete(id: number) {
    return client.delete(`/contracts/${id}`)
  },
  /** 获取合同文件 blob，用于前端预览（图片 / PDF）。 */
  getFile(id: number) {
    return client.get(`/contracts/${id}/file`, { responseType: 'blob' })
  },
}

/**
 * 返回 SSE EventSource URL（带 JWT token）
 */
export function reviewStreamUrl(contractId: number, token: string): string {
  return `/api/contracts/${contractId}/review?token=${encodeURIComponent(token)}`
}
