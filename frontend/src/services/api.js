import axios from 'axios';

const resolveApiBaseUrl = () => {
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL;
  }

  if (import.meta.env.DEV) {
    return '';
  }

  if (typeof window !== 'undefined') {
    const { protocol, hostname } = window.location;
    return `${protocol}//${hostname}:8000`;
  }

  return 'http://127.0.0.1:8000';
};

const apiBaseUrl = resolveApiBaseUrl();
const tokenStorageKey = 'omnikavach-auth-token';

const apiClient = axios.create({
  baseURL: apiBaseUrl,
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000,
});

apiClient.interceptors.request.use(
  (config) => {
    try {
      const token = localStorage.getItem(tokenStorageKey);
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    } catch {
      // localStorage unavailable
    }
    console.log(`[OmniKavach] ${config.method?.toUpperCase()} ${config.baseURL}${config.url}`);
    return config;
  },
  (error) => Promise.reject(error)
);

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401) {
      try {
        localStorage.removeItem(tokenStorageKey);
      } catch {
        // localStorage unavailable
      }
    }
    return Promise.reject(error);
  }
);

const withFriendlyError = (error, fallbackMessage) => {
  if (!error?.response) {
    throw new Error(`Unable to reach backend at ${apiBaseUrl}. Make sure the backend server is running.`);
  }

  const detail = error?.response?.data?.detail;
  const message = typeof detail === 'string' ? detail : fallbackMessage;
  throw new Error(message);
};

export const getAllPatients = async () => {
  try {
    return await apiClient.get('/patients/dashboard');
  } catch (error) {
    withFriendlyError(error, 'Unable to load ward dashboard data.');
  }
};

export const loginUser = async (credentials) => {
  try {
    return await apiClient.post('/auth/login', credentials);
  } catch (error) {
    withFriendlyError(error, 'Unable to sign in.');
  }
};

export const getCurrentUser = async () => {
  try {
    return await apiClient.get('/auth/me');
  } catch (error) {
    withFriendlyError(error, 'Unable to restore your session.');
  }
};

export const getPatientData = async (id) => {
  try {
    return await apiClient.get(`/patients/${id}/enriched`);
  } catch (error) {
    withFriendlyError(error, `Unable to load patient ${id}.`);
  }
};

export const addPatientNote = async (id, note) => {
  try {
    return await apiClient.post(`/patients/${id}/notes`, note);
  } catch (error) {
    withFriendlyError(error, `Unable to save a note for patient ${id}.`);
  }
};

export const deletePatientNote = async (id, noteId) => {
  try {
    return await apiClient.delete(`/patients/${id}/notes/${noteId}`);
  } catch (error) {
    withFriendlyError(error, `Unable to delete note ${noteId}.`);
  }
};

export const uploadPatientDocument = async (id, file) => {
  const formData = new FormData();
  formData.append('file', file);

  try {
    return await apiClient.post(`/patients/${id}/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  } catch (error) {
    withFriendlyError(error, `Unable to upload a report for patient ${id}.`);
  }
};

export const runAgentAnalysis = async (id) => {
  try {
    return await apiClient.post(`/analyze/${id}`);
  } catch (error) {
    withFriendlyError(error, `Unable to run agent analysis for patient ${id}.`);
  }
};

export const sendFamilyCommunicationEmail = async (id, recipientEmail) => {
  try {
    return await apiClient.post(`/patients/${id}/family-email`, {
      recipient_email: recipientEmail,
    });
  } catch (error) {
    withFriendlyError(error, `Unable to send family communication for patient ${id}.`);
  }
};

export const checkBackendHealth = async () => {
  try {
    return await apiClient.get('/health');
  } catch (error) {
    withFriendlyError(error, 'Backend health check failed.');
  }
};

export const authStorage = {
  tokenKey: tokenStorageKey,
  getToken() {
    try {
      return localStorage.getItem(tokenStorageKey);
    } catch {
      return null;
    }
  },
  setToken(token) {
    try {
      localStorage.setItem(tokenStorageKey, token);
    } catch {
      // localStorage unavailable
    }
  },
  clear() {
    try {
      localStorage.removeItem(tokenStorageKey);
    } catch {
      // localStorage unavailable
    }
  },
};

export default apiClient;
