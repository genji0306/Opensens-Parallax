import { useState, useEffect } from 'react';
import { usbService } from '../services/usb/usbService';

export const useDevice = () => {
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    const checkConnection = async () => {
      try {
        const connected = await usbService.checkDeviceConnection();
        setIsConnected(connected);
      } catch (error) {
        console.error('Error checking device connection:', error);
        setIsConnected(false);
      }
    };

    // Initial check
    checkConnection();

    // Set up periodic checks
    const interval = setInterval(checkConnection, 5000);

    // Subscribe to connection events
    const handleConnect = () => setIsConnected(true);
    const handleDisconnect = () => setIsConnected(false);

    usbService.on('connect', handleConnect);
    usbService.on('disconnect', handleDisconnect);

    return () => {
      clearInterval(interval);
      usbService.off('connect', handleConnect);
      usbService.off('disconnect', handleDisconnect);
    };
  }, []);

  return { isConnected };
}; 