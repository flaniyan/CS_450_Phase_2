import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
})

export interface Package {
  name: string
  version: string
  id: string
}

export interface PackageRating {
  NetScore: number
  RampUp: number
  Correctness: number
  BusFactor: number
  ResponsiveMaintainer: number
  LicenseScore: number
}

export const packageAPI = {
  getAll: () => api.get<Package[]>('/packages'),
  search: (query: string) => api.get<Package[]>(`/packages/search?q=${query}`),
  upload: (file: File, debloat: boolean) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('debloat', String(debloat))
    return api.post('/packages/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  rate: (name: string) => api.get<PackageRating>(`/packages/rate/${name}`),
  download: (name: string, version: string) => 
    api.get(`/packages/${name}/${version}`, { responseType: 'blob' }),
  reset: () => api.post('/reset'),
}

export default api

