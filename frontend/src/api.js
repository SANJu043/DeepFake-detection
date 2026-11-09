import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
});

// Attach JWT to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 → clear token
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      if (!window.location.pathname.includes('/login')) {
        window.location.href = '/login';
      }
    }
    return Promise.reject(err);
  }
);

// ── Auth ────────────────────────────────────────────────────
export const authAPI = {
  register: (data) => api.post('/auth/register', data),
  login: (data) => api.post('/auth/login', data),
  refresh: (refresh_token) => api.post('/auth/refresh', { refresh_token }),
  me: () => api.get('/auth/me'),
};

// ── Videos ──────────────────────────────────────────────────
export const videosAPI = {
  upload: (file, onProgress) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/videos/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: onProgress,
    });
  },
  list: (skip = 0, limit = 50) => api.get(`/videos/?skip=${skip}&limit=${limit}`),
  delete: (id) => api.delete(`/videos/${id}`),
};

// ── Jobs ────────────────────────────────────────────────────
export const jobsAPI = {
  list: (skip = 0, limit = 50) => api.get(`/jobs/?skip=${skip}&limit=${limit}`),
  get: (id) => api.get(`/jobs/${id}`),
};

// ── Attestations ────────────────────────────────────────────
export const attestationsAPI = {
  list: (skip = 0, limit = 50) => api.get(`/attestations/?skip=${skip}&limit=${limit}`),
  get: (id) => api.get(`/attestations/${id}`),
  package: (id) => api.get(`/attestations/${id}/package`),
};

// ── Verification (public) ──────────────────────────────────
export const verifyAPI = {
  byId: (attestation_id) => api.post('/verify/by-id', { attestation_id }),
  byUpload: (attestation_id, file) => {
    const formData = new FormData();
    formData.append('attestation_id', attestation_id);
    formData.append('file', file);
    return api.post('/verify/by-upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
};

// ── Admin ───────────────────────────────────────────────────
export const adminAPI = {
  keys: () => api.get('/admin/keys'),
  revoke: (data) => api.post('/admin/revoke', data),
  anomalies: (skip = 0, limit = 50) => api.get(`/admin/anomalies?skip=${skip}&limit=${limit}`),
};

export default api;
