import axios from 'axios';

const BASE_URL = (typeof process !== 'undefined' && process.env.REACT_APP_API_URL) 
  || (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL)
  || 'http://localhost:8000';

const api = axios.create({ baseURL: BASE_URL });

api.interceptors.request.use(cfg => {
  const token = localStorage.getItem('access_token');
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  return cfg;
});

api.interceptors.response.use(r => r, async err => {
  if (err.response?.status === 401) {
    const refresh = localStorage.getItem('refresh_token');
    if (refresh) {
      try {
        const r = await axios.post(`${BASE_URL}/api/auth/refresh/`, { refresh });
        localStorage.setItem('access_token', r.data.access);
        err.config.headers.Authorization = `Bearer ${r.data.access}`;
        return api.request(err.config);
      } catch {
        localStorage.clear();
        window.location.reload();
      }
    }
  }
  return Promise.reject(err);
});

export default api;

export const login = (u, p) =>
  api.post('/api/auth/token/', { username: u, password: p });
export const getDashboard = () => api.get('/api/dashboard/');
export const getRecords = (params) => api.get('/api/records/', { params });
export const getBatches = () => api.get('/api/batches/');
export const reviewRecord = (id, action, notes) =>
  api.post(`/api/records/${id}/review/`, { action, notes });
export const getAuditTrail = (id) => api.get(`/api/records/${id}/audit_trail/`);
export const uploadFile = (formData) =>
  api.post('/api/upload/', formData, { headers: { 'Content-Type': 'multipart/form-data' } });
