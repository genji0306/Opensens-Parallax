import axios from 'axios';
import { Measurement, ExternalDevice, DataPoint, ProtocolStep, ExperimentSettings } from '../types';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Measurement API
export const measurementApi = {
  // Get all measurements
  getAll: () => api.get<Measurement[]>('/measurements'),
  
  // Get a single measurement by ID
  getById: (id: number) => api.get<Measurement>(`/measurements/${id}`),
  
  // Create a new measurement
  create: (data: Partial<Measurement>) => api.post<Measurement>('/measurements', data),
  
  // Update a measurement
  update: (id: number, data: Partial<Measurement>) => api.put<Measurement>(`/measurements/${id}`, data),
  
  // Delete a measurement
  delete: (id: number) => api.delete(`/measurements/${id}`),
  
  // Get measurement data
  getData: (id: number) => api.get<DataPoint[]>(`/measurements/${id}/data`),
  
  // Start a measurement
  start: (id: number) => api.post(`/measurements/${id}/start`),
  
  // Stop a measurement
  stop: (id: number) => api.post(`/measurements/${id}/stop`),
};

// External Device API
export const deviceApi = {
  // Get all devices
  getAll: () => api.get<ExternalDevice[]>('/devices'),
  
  // Get a single device by ID
  getById: (id: number) => api.get<ExternalDevice>(`/devices/${id}`),
  
  // Create a new device
  create: (data: Partial<ExternalDevice>) => api.post<ExternalDevice>('/devices', data),
  
  // Update a device
  update: (id: number, data: Partial<ExternalDevice>) => api.put<ExternalDevice>(`/devices/${id}`, data),
  
  // Delete a device
  delete: (id: number) => api.delete(`/devices/${id}`),
  
  // Connect to a device
  connect: (id: number) => api.post(`/devices/${id}/connect`),
  
  // Disconnect from a device
  disconnect: (id: number) => api.post(`/devices/${id}/disconnect`),
};

// Protocol API
export const protocolApi = {
  // Get all protocols
  getAll: () => api.get<ProtocolStep[]>('/protocols'),
  
  // Get a single protocol by ID
  getById: (id: number) => api.get<ProtocolStep>(`/protocols/${id}`),
  
  // Create a new protocol
  create: (data: Partial<ProtocolStep[]>) => api.post<ProtocolStep[]>('/protocols', data),
  
  // Update a protocol
  update: (id: number, data: Partial<ProtocolStep[]>) => api.put<ProtocolStep[]>(`/protocols/${id}`, data),
  
  // Delete a protocol
  delete: (id: number) => api.delete(`/protocols/${id}`),
};

// Settings API
export const settingsApi = {
  // Get settings
  get: () => api.get<ExperimentSettings>('/settings'),
  
  // Update settings
  update: (data: Partial<ExperimentSettings>) => api.put<ExperimentSettings>('/settings', data),
};

// Error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Handle errors here
    console.error('API Error:', error);
    return Promise.reject(error);
  }
);

export default api; 