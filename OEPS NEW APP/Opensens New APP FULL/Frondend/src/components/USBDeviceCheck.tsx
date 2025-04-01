import React, { useEffect, useState } from 'react';
import { USBDeviceInfo, DeviceResponse } from '../services/usb/types';
import { usbService } from '../services/usb/usbService';
import { AlertCircle, RefreshCw, AlertTriangle, CheckCircle, Power } from 'lucide-react';
import { Input } from './ui/input';

const MAX_RETRIES = 3;
const RETRY_DELAY = 1000; // ms

export const USBDeviceCheck: React.FC = () => {
  const [devices, setDevices] = useState<USBDeviceInfo[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [vid, setVid] = useState('a0a0');
  const [pid, setPid] = useState('0002');
  const [retryCount, setRetryCount] = useState(0);

  const checkDevices = async () => {
    setIsRefreshing(true);
    setError(null);
    try {
      // Add delay before checking to avoid lock contention
      await new Promise(resolve => setTimeout(resolve, 100));
      
      // First just list available devices without trying to connect
      const availableDevices = await usbService.listAvailableDevices();
      setDevices(availableDevices);
      
      // Then check if our device is already connected
      const connected = await usbService.checkDeviceConnection();
      setIsConnected(connected);
      setRetryCount(0);
    } catch (error) {
      console.error('Device check error:', error);
      setError(error instanceof Error ? error.message : 'Failed to check device connection');
      
      // Retry logic
      if (retryCount < MAX_RETRIES) {
        setRetryCount(prev => prev + 1);
        setTimeout(checkDevices, RETRY_DELAY);
      }
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    checkDevices();
    
    // Set up periodic checks
    const interval = setInterval(checkDevices, 5000);
    
    return () => clearInterval(interval);
  }, []);

  const handleConnect = async () => {
    try {
      setError(null);
      // Update the VID/PID in the service
      const vidNum = parseInt(vid, 16);
      const pidNum = parseInt(pid, 16);
      
      if (isNaN(vidNum) || isNaN(pidNum)) {
        setError('Invalid VID or PID format');
        return;
      }
      
      usbService.setDeviceIds(vidNum, pidNum);
      
      // Try to connect
      await usbService.connectDevice();
      setIsConnected(true);
      
      // Refresh device list
      await checkDevices();
    } catch (err) {
      console.error('Connection error:', err);
      if (err instanceof Error) {
        if (err.message.includes('No device selected')) {
          setError('No device was selected. Please try again.');
        } else if (err.message.includes('Failed to initialize')) {
          setError('Device initialization failed. Please try disconnecting and reconnecting the device.');
        } else {
          setError(err.message);
        }
      } else {
        setError('Failed to connect to device');
      }
      setIsConnected(false);
    }
  };

  const handleDisconnect = async () => {
    try {
      setError(null);
      await usbService.disconnectDevice();
      setIsConnected(false);
      
      // Refresh device list
      const availableDevices = await usbService.listAvailableDevices();
      setDevices(availableDevices);
    } catch (err) {
      console.error('Disconnection error:', err);
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Failed to disconnect device');
      }
    }
  };

  return (
    <div className="space-y-4">
      {/* Connection Controls */}
      <div className="flex flex-col space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}></div>
            <span className="text-sm text-gray-300">{isConnected ? 'Device Connected' : 'Device Disconnected'}</span>
          </div>
          <button
            onClick={checkDevices}
            disabled={isRefreshing}
            className="p-1.5 text-gray-400 hover:text-gray-300 bg-gray-700 rounded-md transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
          </button>
        </div>
        
        <button
          onClick={isConnected ? handleDisconnect : handleConnect}
          className={`flex items-center space-x-1 px-3 py-1.5 rounded-md text-white font-medium transition-colors w-fit ${
            isConnected
              ? 'bg-red-600 hover:bg-red-700'
              : 'bg-green-600 hover:bg-green-700'
          }`}
        >
          <Power className="w-4 h-4" />
          <span>{isConnected ? 'Disconnect' : 'Connect'}</span>
        </button>
      </div>

      {/* Error Display */}
      {error && (
        <div className="flex items-start space-x-2 text-red-400 text-sm">
          <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* VID/PID Input Row */}
      <div className="grid grid-cols-2 gap-2">
        <div className="flex items-center space-x-2">
          <span className="text-xs text-gray-400">VID:</span>
          <Input
            value={vid}
            onChange={(e) => setVid(e.target.value.replace(/[^0-9a-fA-F]/g, ''))}
            className="h-7 px-2 text-xs bg-gray-700 border-gray-600 text-gray-200"
            maxLength={4}
          />
        </div>
        <div className="flex items-center space-x-2">
          <span className="text-xs text-gray-400">PID:</span>
          <Input
            value={pid}
            onChange={(e) => setPid(e.target.value.replace(/[^0-9a-fA-F]/g, ''))}
            className="h-7 px-2 text-xs bg-gray-700 border-gray-600 text-gray-200"
            maxLength={4}
          />
        </div>
      </div>

      {/* Device List */}
      {devices.length > 0 && (
        <div className="space-y-2">
          <div className="text-xs font-medium text-gray-400">Available Devices:</div>
          {devices.map((device, index) => (
            <div key={index} className="text-xs text-gray-300 space-y-1">
              <div>{device.manufacturerName} {device.productName}</div>
              <div className="text-gray-500">
                VID: {device.vendorId.toString(16).padStart(4, '0')} 
                PID: {device.productId.toString(16).padStart(4, '0')}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}; 