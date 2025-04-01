import { useState, useEffect, useCallback, useRef } from 'react';
import { usbService } from '../services/usb/usbService';
import { parseADC, ADCData, CalibrationData } from '../utils/adcParser';

const MAX_SAMPLES = 1000; // Rolling window size
const POLL_INTERVAL = 100; // ms
const CONNECTION_CHECK_INTERVAL = 2000; // Check connection every 2 seconds
const MAX_CALIBRATION_RETRIES = 3;
const CALIBRATION_RETRY_DELAY = 1000; // ms

interface LatencyStats {
  current: number;
  average: number;
  samples: number;
}

export function useRealtimeADC() {
  const [chartData, setChartData] = useState<ADCData[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [latency, setLatency] = useState<LatencyStats>({
    current: 0,
    average: 0,
    samples: 0
  });
  const [calibration, setCalibration] = useState<CalibrationData | null>(null);

  // Use refs for values that shouldn't trigger re-renders
  const latencyRef = useRef<LatencyStats>(latency);
  const streamingRef = useRef<boolean>(false);
  const lastConnectionCheckRef = useRef<number>(0);
  const isDeviceConnectedRef = useRef<boolean>(false);
  const calibrationRef = useRef<CalibrationData | null>(null);
  const calibrationRetryCountRef = useRef<number>(0);

  // Update refs when state changes
  useEffect(() => {
    streamingRef.current = isStreaming;
    latencyRef.current = latency;
    calibrationRef.current = calibration;
  }, [isStreaming, latency, calibration]);

  // Fetch calibration data with retry logic
  const fetchCalibration = useCallback(async () => {
    try {
      console.log('Attempting to fetch DAC calibration...');
      const calData = await usbService.readDACCalibration();
      
      // Set calibration data
      const newCalibration = {
        dacOffset: calData.offset,
        dacGain: calData.gain
      };
      
      setCalibration(newCalibration);
      calibrationRetryCountRef.current = 0; // Reset retry count on success
      
      // Log successful calibration
      console.log('DAC calibration loaded:', newCalibration);
    } catch (error) {
      console.warn('Failed to fetch DAC calibration:', error);
      
      // Retry logic
      if (calibrationRetryCountRef.current < MAX_CALIBRATION_RETRIES) {
        calibrationRetryCountRef.current++;
        console.log(`Retrying DAC calibration (attempt ${calibrationRetryCountRef.current}/${MAX_CALIBRATION_RETRIES})`);
        setTimeout(fetchCalibration, CALIBRATION_RETRY_DELAY);
      } else {
        console.warn('Max calibration retries reached, using default values');
        // Set default calibration values
        const defaultCalibration = {
          dacOffset: 0,
          dacGain: 524288 // 2^19 default
        };
        setCalibration(defaultCalibration);
        console.log('Using default calibration:', defaultCalibration);
      }
    }
  }, []);

  const updateLatency = useCallback((newLatency: number) => {
    const stats = latencyRef.current;
    const newAverage = (stats.average * stats.samples + newLatency) / (stats.samples + 1);
    
    setLatency({
      current: newLatency,
      average: newAverage,
      samples: stats.samples + 1
    });
  }, []);

  const checkDeviceConnection = useCallback(async (force: boolean = false) => {
    const now = Date.now();
    if (!force && now - lastConnectionCheckRef.current < CONNECTION_CHECK_INTERVAL) {
      return isDeviceConnectedRef.current;
    }

    try {
      // Add delay before checking connection to avoid lock contention
      await new Promise(resolve => setTimeout(resolve, 100));
      
      const isConnected = await usbService.checkDeviceConnection();
      isDeviceConnectedRef.current = isConnected;
      lastConnectionCheckRef.current = now;
      
      // If we just connected, fetch calibration
      if (isConnected && !calibrationRef.current) {
        await fetchCalibration();
      }
      
      return isConnected;
    } catch (error) {
      console.warn('Failed to check device connection:', error);
      isDeviceConnectedRef.current = false;
      return false;
    }
  }, [fetchCalibration]);

  const readADC = useCallback(async () => {
    try {
      // Only check connection periodically or if we know it's disconnected
      if (!isDeviceConnectedRef.current) {
        const isConnected = await checkDeviceConnection();
        if (!isConnected) {
          console.warn('Device not connected, stopping stream');
          setIsStreaming(false);
          return;
        }
      }

      const startTime = performance.now();
      const response = await usbService.readADC();
      
      if (response.type === 'binary' && response.data instanceof Uint8Array) {
        const data = new DataView(response.data.buffer);
        const adcData = parseADC(data, calibrationRef.current || undefined);
        
        setChartData(prev => {
          const newData = [...prev, adcData];
          if (newData.length > MAX_SAMPLES) {
            return newData.slice(-MAX_SAMPLES);
          }
          return newData;
        });

        // Update latency
        const endTime = performance.now();
        updateLatency(endTime - startTime);
      }
    } catch (error) {
      console.error('Failed to read ADC:', error);
      // Only stop streaming if it's a connection error
      if (error instanceof Error && error.message.includes('Device not connected')) {
        isDeviceConnectedRef.current = false;
        setIsStreaming(false);
      }
    }
  }, [updateLatency, checkDeviceConnection]);

  // Start/stop polling
  useEffect(() => {
    let intervalId: number;

    const startStreaming = async () => {
      if (isStreaming) {
        // Force check device connection before starting
        const isConnected = await checkDeviceConnection(true);
        if (!isConnected) {
          console.warn('Device not connected, cannot start streaming');
          setIsStreaming(false);
          return;
        }

        // Initial read
        await readADC();
        
        // Set up polling interval
        intervalId = window.setInterval(readADC, POLL_INTERVAL);
      }
    };

    startStreaming();

    return () => {
      if (intervalId) {
        window.clearInterval(intervalId);
      }
    };
  }, [isStreaming, readADC, checkDeviceConnection]);

  // Stop streaming if device disconnects
  useEffect(() => {
    const handleDisconnect = () => {
      isDeviceConnectedRef.current = false;
      calibrationRef.current = null;
      setCalibration(null);
      if (streamingRef.current) {
        setIsStreaming(false);
      }
    };

    usbService.on('disconnect', handleDisconnect);
    return () => {
      usbService.off('disconnect', handleDisconnect);
    };
  }, []);

  const toggleStreaming = useCallback(async () => {
    if (!isStreaming) {
      // Force check device connection before starting
      const isConnected = await checkDeviceConnection(true);
      if (!isConnected) {
        console.warn('Device not connected, cannot start streaming');
        return;
      }
    }
    setIsStreaming(prev => !prev);
  }, [isStreaming, checkDeviceConnection]);

  const clearData = useCallback(() => {
    setChartData([]);
    setLatency({
      current: 0,
      average: 0,
      samples: 0
    });
  }, []);

  // Update calibration values
  const updateCalibration = useCallback(async (offset: number, gain: number) => {
    try {
      await usbService.setDACCalibration(offset, gain);
      setCalibration({ dacOffset: offset, dacGain: gain });
    } catch (error) {
      console.error('Failed to update DAC calibration:', error);
      throw error;
    }
  }, []);

  return {
    chartData,
    isStreaming,
    latency,
    calibration,
    toggleStreaming,
    clearData,
    updateCalibration
  };
} 