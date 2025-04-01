import React, { createContext, useContext, useEffect, useState } from 'react';
import { usbService } from '../services/usb/usbService';
import { DeviceStatus, DeviceConfig, DeviceResponse } from '../services/usb/types';

interface DeviceContextType {
  status: DeviceStatus;
  config: DeviceConfig;
  connect: () => Promise<void>;
  disconnect: () => Promise<void>;
  sendCommand: (command: string, params?: string[]) => Promise<DeviceResponse>;
  setCellState: (state: 'on' | 'off') => Promise<void>;
  setMode: (mode: 'potentiostatic' | 'galvanostatic') => Promise<void>;
  setRange: (range: number) => Promise<void>;
  readADC: () => Promise<DeviceResponse>;
}

const DeviceContext = createContext<DeviceContextType | null>(null);

export const useDevice = () => {
  const context = useContext(DeviceContext);
  if (!context) {
    throw new Error('useDevice must be used within a DeviceProvider');
  }
  return context;
};

export const DeviceProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [status, setStatus] = useState<DeviceStatus>(usbService.getStatus());
  const [config, setConfig] = useState<DeviceConfig>(usbService.getConfig());

  useEffect(() => {
    // Set up event listeners
    const handleStatusChange = (newStatus: DeviceStatus) => {
      setStatus(newStatus);
    };

    const handleConfigChange = (newConfig: DeviceConfig) => {
      setConfig(newConfig);
    };

    const handleError = (error: string) => {
      console.error('USB Error:', error);
    };

    usbService.on('connected', handleStatusChange);
    usbService.on('disconnected', handleStatusChange);
    usbService.on('error', handleError);

    // Cleanup
    return () => {
      usbService.off('connected', handleStatusChange);
      usbService.off('disconnected', handleStatusChange);
      usbService.off('error', handleError);
    };
  }, []);

  const connect = async () => {
    try {
      await usbService.connectDevice();
    } catch (error) {
      console.error('Failed to connect:', error);
      throw error;
    }
  };

  const disconnect = async () => {
    try {
      await usbService.disconnectDevice();
    } catch (error) {
      console.error('Failed to disconnect:', error);
      throw error;
    }
  };

  const sendCommand = async (command: string, params?: string[]) => {
    try {
      return await usbService.sendCommand({ command, params });
    } catch (error) {
      console.error('Failed to send command:', error);
      throw error;
    }
  };

  const setCellState = async (state: 'on' | 'off') => {
    try {
      await usbService.setCellState(state);
    } catch (error) {
      console.error('Failed to set cell state:', error);
      throw error;
    }
  };

  const setMode = async (mode: 'potentiostatic' | 'galvanostatic') => {
    try {
      await usbService.setMode(mode);
    } catch (error) {
      console.error('Failed to set mode:', error);
      throw error;
    }
  };

  const setRange = async (range: number) => {
    try {
      await usbService.setRange(range);
    } catch (error) {
      console.error('Failed to set range:', error);
      throw error;
    }
  };

  const readADC = async () => {
    try {
      return await usbService.readADC();
    } catch (error) {
      console.error('Failed to read ADC:', error);
      throw error;
    }
  };

  const value = {
    status,
    config,
    connect,
    disconnect,
    sendCommand,
    setCellState,
    setMode,
    setRange,
    readADC,
  };

  return (
    <DeviceContext.Provider value={value}>
      {children}
    </DeviceContext.Provider>
  );
}; 