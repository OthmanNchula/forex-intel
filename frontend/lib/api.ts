import axios from "axios";
import { getToken, clearAuth } from "@/lib/auth";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
});

// Attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 — redirect to login
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      clearAuth();
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

// Auth endpoints
export const authApi = {
  register: (data: { email: string; password: string; display_name: string }) =>
    api.post("/api/auth/register", data),
  login: (data: { email: string; password: string }) =>
    api.post("/api/auth/login", data),
  me: () => api.get("/api/auth/me"),
  updateMe: (data: object) => api.patch("/api/auth/me", data),
  logout: () => api.post("/api/auth/logout"),
};

// Market endpoints
export const marketApi = {
  getPairs: () => api.get("/api/market/pairs"),
  getQuote: (pair: string) =>
    api.get(`/api/market/${pair.replace("/", "-")}/quote`),
  getAllQuotes: () => api.get("/api/market/quotes/all"),
  getOHLCV: (pair: string, tf = "H1", limit = 200) =>
    api.get(`/api/market/${pair.replace("/", "-")}/ohlcv`, {
      params: { tf, limit },
    }),
  getIndicators: (pair: string, tf = "H1") =>
    api.get(`/api/market/${pair.replace("/", "-")}/indicators`, {
      params: { tf },
    }),
  getSupportResistance: (pair: string, tf = "H1") =>
    api.get(`/api/market/${pair.replace("/", "-")}/support-resistance`, {
      params: { tf },
    }),
};

// Analysis endpoints
export const analysisApi = {
  generateSignal: (pair: string, timeframe = "H1") =>
    api.post("/api/analysis/generate", { pair, timeframe }),
  getSignals: () => api.get("/api/analysis/signals"),
  getSignal: (id: string) => api.get(`/api/analysis/signals/${id}`),
  getLatestSignal: (pair: string) =>
    api.get(`/api/analysis/signals/${pair.replace("/", "-")}/latest`),
  dismissSignal: (id: string) =>
    api.post(`/api/analysis/signals/${id}/dismiss`),
};

// Risk endpoints
export const riskApi = {
  calculate: (data: object) => api.post("/api/risk/calculate", data),
  getDailyExposure: () => api.get("/api/risk/daily-exposure"),
};

// Journal endpoints
export const journalApi = {
  getTrades: (params?: object) => api.get("/api/journal", { params }),
  createTrade: (data: object) => api.post("/api/journal", data),
  getTrade: (id: string) => api.get(`/api/journal/${id}`),
  updateTrade: (id: string, data: object) =>
    api.patch(`/api/journal/${id}`, data),
  deleteTrade: (id: string) => api.delete(`/api/journal/${id}`),
  getStats: () => api.get("/api/journal/stats"),
};

// Alerts endpoints
export const alertsApi = {
  getAlerts: () => api.get("/api/alerts"),
  createAlert: (data: object) => api.post("/api/alerts", data),
  deleteAlert: (id: string) => api.delete(`/api/alerts/${id}`),
};

export default api;