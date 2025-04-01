import React, { useState, useEffect, useRef } from 'react';
import { X, Power, Zap } from 'lucide-react';
import { usbService } from '../../services/usb/usbService';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
} from 'chart.js';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

interface ManualControlModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const MAX_DATA_POINTS = 200;
const SAMPLING_INTERVAL = 90; // 90ms = ~11Hz

export const ManualControlModal: React.FC<ManualControlModalProps> = ({
  isOpen,
  onClose
}) => {
  const [isCellOn, setIsCellOn] = useState(false);
  const [mode, setMode] = useState(0);
  const [range, setRange] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Chart data state
  const [chartData, setChartData] = useState({
    labels: Array(MAX_DATA_POINTS).fill(''),
    datasets: [
      {
        label: 'Potential (V)',
        data: Array(MAX_DATA_POINTS).fill(0),
        borderColor: 'rgb(75, 192, 192)',
        tension: 0.1
      },
      {
        label: 'Current (mA)',
        data: Array(MAX_DATA_POINTS).fill(0),
        borderColor: 'rgb(255, 99, 132)',
        tension: 0.1
      }
    ]
  });

  // Refs for data management
  const potentialBuffer = useRef<number[]>(Array(MAX_DATA_POINTS).fill(0));
  const currentBuffer = useRef<number[]>(Array(MAX_DATA_POINTS).fill(0));
  const updateTimer = useRef<NodeJS.Timeout | null>(null);

  // Fetch initial device state
  useEffect(() => {
    if (isOpen) {
      fetchDeviceState();
      startLiveUpdates();
    }
    return () => {
      if (updateTimer.current) {
        clearInterval(updateTimer.current);
      }
    };
  }, [isOpen]);

  const startLiveUpdates = () => {
    if (updateTimer.current) {
      clearInterval(updateTimer.current);
    }
    
    updateTimer.current = setInterval(async () => {
      try {
        // Check device connection first
        const deviceStatus = usbService.getStatus();
        if (!deviceStatus.isConnected) {
          console.warn('Device not connected, stopping updates');
          if (updateTimer.current) {
            clearInterval(updateTimer.current);
          }
          return;
        }

        const response = await usbService.readPotentialCurrent();
        console.log('Received response:', response); // Debug log
        
        if (response.type === 'binary') {
          const data = response.data as Float32Array;
          console.log('Raw data array:', Array.from(data)); // Debug log
          
          // The data array contains [voltage, currentInmA]
          const potential = data[0];
          const current = data[1];
          
          console.log('Extracted values:', { potential, current }); // Debug log
          
          // Skip update if both values are zero (device might be disconnected or not ready)
          if (potential === 0 && current === 0) {
            console.log('Skipping update - zero values received');
            return;
          }
          
          // Update buffers with new values
          potentialBuffer.current = [...potentialBuffer.current.slice(1), potential];
          currentBuffer.current = [...currentBuffer.current.slice(1), current];
          
          // Create new chart data
          const newChartData = {
            labels: Array(MAX_DATA_POINTS).fill('').map((_, i) => `${i}`),
            datasets: [
              {
                label: `Potential (V) - ${potential.toFixed(3)}V`,
                data: potentialBuffer.current,
                borderColor: 'rgb(75, 192, 192)',
                tension: 0.1
              },
              {
                label: `Current (mA) - ${current.toFixed(3)}mA`,
                data: currentBuffer.current,
                borderColor: 'rgb(255, 99, 132)',
                tension: 0.1
              }
            ]
          };
          
          console.log('New chart data:', newChartData); // Debug log
          
          // Update chart data
          setChartData(newChartData);
        } else {
          console.warn('Received non-binary response:', response);
        }
      } catch (error) {
        console.error('Error reading data:', error);
        // If we get an error, stop the updates
        if (updateTimer.current) {
          clearInterval(updateTimer.current);
        }
      }
    }, SAMPLING_INTERVAL);
  };

  const fetchDeviceState = async () => {
    try {
      setIsLoading(true);
      setError(null);

      // Read cell state
      const cellResponse = await usbService.readCellState();
      if (cellResponse.type === 'text') {
        setIsCellOn(cellResponse.data === 'ON');
      }

      // Read mode
      const modeResponse = await usbService.readMode();
      if (modeResponse.type === 'text') {
        setMode(parseInt(modeResponse.data as string));
      }

      // Read ranges
      const rangesResponse = await usbService.readRanges();
      if (rangesResponse.type === 'binary') {
        // Assuming first range is current range
        setRange((rangesResponse.data as Uint8Array)[0]);
      }
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to fetch device state');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCellToggle = async () => {
    try {
      setError(null);
      setIsLoading(true);

      if (isCellOn) {
        await usbService.turnCellOff();
      } else {
        await usbService.turnCellOn();
      }

      setIsCellOn(!isCellOn);
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to toggle cell');
    } finally {
      setIsLoading(false);
    }
  };

  const handleModeChange = async (newMode: number) => {
    try {
      setError(null);
      setIsLoading(true);

      await usbService.setMode(newMode);
      setMode(newMode);
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to set mode');
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-gray-800 rounded-lg p-6 w-[800px] relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-gray-400 hover:text-white"
        >
          <X size={20} />
        </button>

        <h2 className="text-xl font-semibold text-white mb-6">Manual Control</h2>

        <div className="grid grid-cols-2 gap-6">
          {/* Left column - Controls */}
          <div className="space-y-6">
            {/* Cell Control */}
            <div>
              <h3 className="text-sm font-medium text-gray-300 mb-2">Cell Control</h3>
              <button
                onClick={handleCellToggle}
                disabled={isLoading}
                className={`w-full flex items-center justify-center px-4 py-2 rounded ${
                  isCellOn
                    ? 'bg-red-600 hover:bg-red-700'
                    : 'bg-green-600 hover:bg-green-700'
                } text-white disabled:opacity-50 disabled:cursor-not-allowed`}
              >
                <Power size={16} className="mr-2" />
                {isCellOn ? 'Turn Cell OFF' : 'Turn Cell ON'}
              </button>
            </div>

            {/* Mode Selection */}
            <div>
              <h3 className="text-sm font-medium text-gray-300 mb-2">Mode</h3>
              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={() => handleModeChange(0)}
                  disabled={isLoading}
                  className={`px-4 py-2 rounded ${
                    mode === 0
                      ? 'bg-blue-600'
                      : 'bg-gray-700 hover:bg-gray-600'
                  } text-white disabled:opacity-50 disabled:cursor-not-allowed`}
                >
                  Potentiostat
                </button>
                <button
                  onClick={() => handleModeChange(1)}
                  disabled={isLoading}
                  className={`px-4 py-2 rounded ${
                    mode === 1
                      ? 'bg-blue-600'
                      : 'bg-gray-700 hover:bg-gray-600'
                  } text-white disabled:opacity-50 disabled:cursor-not-allowed`}
                >
                  Galvanostat
                </button>
              </div>
            </div>

            {/* Range Selection */}
            <div>
              <h3 className="text-sm font-medium text-gray-300 mb-2">Current Range</h3>
              <select
                value={range}
                onChange={(e) => setRange(parseInt(e.target.value))}
                disabled={isLoading}
                className="w-full bg-gray-700 text-white px-3 py-2 rounded border border-gray-600 focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              >
                <option value={0}>±25 mA</option>
                <option value={1}>±2.5 mA</option>
                <option value={2}>±250 µA</option>
                <option value={3}>±25 µA</option>
              </select>
            </div>

            {error && (
              <div className="text-red-400 text-sm mt-2">
                {error}
              </div>
            )}

            {isLoading && (
              <div className="text-blue-400 text-sm flex items-center justify-center">
                <Zap size={16} className="mr-2 animate-pulse" />
                Processing...
              </div>
            )}
          </div>

          {/* Right column - Chart */}
          <div className="h-[400px]">
            <Line
              data={chartData}
              options={{
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                scales: {
                  y: {
                    beginAtZero: false,
                    grid: {
                      color: 'rgba(255, 255, 255, 0.1)'
                    },
                    ticks: {
                      color: 'white'
                    }
                  },
                  x: {
                    display: false, // Hide x-axis labels since we're showing time series
                    grid: {
                      color: 'rgba(255, 255, 255, 0.1)'
                    },
                    ticks: {
                      color: 'white'
                    }
                  }
                },
                plugins: {
                  legend: {
                    labels: {
                      color: 'white'
                    }
                  },
                  tooltip: {
                    mode: 'index',
                    intersect: false,
                    callbacks: {
                      label: function(context) {
                        const value = context.parsed.y;
                        const label = context.dataset.label || '';
                        return `${label}: ${value.toFixed(3)}`;
                      }
                    }
                  }
                }
              }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}; 