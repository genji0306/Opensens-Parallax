import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  ReferenceLine, Scatter
} from 'recharts';
import {
  Settings, Maximize2, Minimize2, Play, Pause, Save, X, Edit2,
  Clock, Plus, RefreshCw, Minus, Download, Sun, Moon,
  SlidersHorizontal, CheckCircle, AlertTriangle, ChevronDown, ChevronUp, Square
} from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Switch } from './ui/switch';
import { cn } from '../lib/utils';
import { motion, AnimatePresence } from 'framer-motion';

// Import other components
import { ModalBackdrop } from './ModalBackdrop';
import { MeasurementLibraryBlock } from './MeasurementLibraryBlock';
import { AddMeasurementBlock } from './AddMeasurementBlock';
import { WaitingTimeBlock } from './WaitingTimeBlock';
import { TimelineMeasurementBlock } from './TimelineMeasurementBlock';
import { ExternalDeviceBlock } from './ExternalDeviceBlock';
import { MeasurementModal } from './modals/MeasurementModal';
import { ExternalDeviceModal } from './modals/ExternalDeviceModal';
import { WaitingTimeModal } from './modals/WaitingTimeModal';
import { PlaybackIndicator } from './PlaybackIndicator';
import { MEASUREMENT_TYPES } from '../constants/measurementTypes';
import { Measurement, ExternalDevice, DataPoint, ProtocolStep, ExperimentSettings } from '../types';
import { SettingsModal } from './modals/SettingsModal';
import { Navbar } from './Navbar';
import { Chart } from './Chart';
import { ExperimentControls } from './ExperimentControls';
import { ExportDataModal } from './modals/ExportDataModal';
import { Sidebar } from './Sidebar';

// Main component
const PotentiostatApp: React.FC = () => {
  // State management
  const [deviceConnected, setDeviceConnected] = useState(true);
  const [graphData, setGraphData] = useState<{ current: number; potential: number }[]>([]);
  const [autoFocus, setAutoFocus] = useState(true);
  const [currentValue, setCurrentValue] = useState(0.4);
  const [potentialValue, setPotentialValue] = useState(0.34);
  const [measurementStatus, setMeasurementStatus] = useState('Ready');
  const [isRunning, setIsRunning] = useState(false);
  const [runningTime, setRunningTime] = useState('00:03:17');
  const [timelineScale, setTimelineScale] = useState(100);
  const [isDarkMode, setIsDarkMode] = useState(true);
  const [isSimulation, setIsSimulation] = useState(true);

  // Timeline state
  const [timelineMeasurements, setTimelineMeasurements] = useState<Measurement[]>([
    {
      id: 1,
      type: 'CV',
      status: 'queued',
      estimatedTime: 120,
      color: '#4A90E2',
      parameters: {
        initialPotential: 0.0,
        finalPotential: 0.8,
        scanRate: 100,
        cycles: 3
      },
      filePath: '/data/cv_default.csv'
    }
  ]);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);

  // External Device state
  const [externalDevices, setExternalDevices] = useState<ExternalDevice[]>([
    {
      id: 101,
      name: 'USB Device 01',
      type: 'USB',
      action: 'ON',
      startTime: 100,
      duration: 150,
      color: '#6B7280'
    }
  ]);

  // Measurement library state
  const [libraryMeasurements, setLibraryMeasurements] = useState<Measurement[]>(
    MEASUREMENT_TYPES.map((type, index) => ({
      ...type,
      id: index + 100,
      parameters: type.parameters.reduce((acc, param) => {
        acc[param.name] = param.default;
        return acc;
      }, {}),
      filePath: `/data/${type.type.toLowerCase()}_default.csv`
    }))
  );

  // Playback state
  const [playheadPosition, setPlayheadPosition] = useState(100);
  const [totalDuration, setTotalDuration] = useState(600);

  // Modal state
  const [isMeasurementModalOpen, setIsMeasurementModalOpen] = useState(false);
  const [isExternalDeviceModalOpen, setIsExternalDeviceModalOpen] = useState(false);
  const [isWaitingTimeModalOpen, setIsWaitingTimeModalOpen] = useState(false);
  const [currentEditingMeasurement, setCurrentEditingMeasurement] = useState<Measurement | null>(null);
  const [currentEditingDevice, setCurrentEditingDevice] = useState<ExternalDevice | null>(null);
  const [measurementModalMode, setMeasurementModalMode] = useState<'add' | 'edit'>('add');
  const [waitingAfterIndex, setWaitingAfterIndex] = useState(-1);

  // Settings Panel State
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [displayUnits, setDisplayUnits] = useState<'SI' | 'engineering'>('SI');

  // Calibration and Manual Control Modal State
  const [isCalibrationModalOpen, setIsCalibrationModalOpen] = useState(false);
  const [isManualModalOpen, setIsManualModalOpen] = useState(false);

  // Refs
  const timelineRef = useRef<HTMLDivElement>(null);
  const [timelineWidth, setTimelineWidth] = useState(0);

  // New state for protocol
  const [data, setData] = useState<DataPoint[]>([]);
  const [protocol, setProtocol] = useState<ProtocolStep[]>([]);
  const [currentStepIndex, setCurrentStepIndex] = useState<number | null>(null);
  const [settings, setSettings] = useState<ExperimentSettings>({
    baudRate: 9600,
    comPort: '',
    sampleRate: 10,
  });

  // New modals
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false);
  const [isExportModalOpen, setIsExportModalOpen] = useState(false);

  // Handle protocol execution
  useEffect(() => {
    if (isRunning && protocol.length > 0) {
      // This would be where we would connect to the actual device
      // and start executing the protocol
      setCurrentStepIndex(0);
      
      return () => {
        // Clean up (disconnect device, etc)
      };
    }
  }, [isRunning, protocol]);

  // Start/stop experiment
  const toggleExperiment = useCallback(() => {
    if (isRunning) {
      // Stop the experiment
      setIsRunning(false);
      setCurrentStepIndex(null);
    } else {
      // Start the experiment
      if (protocol.length > 0) {
        setIsRunning(true);
      } else {
        alert('Please add steps to your protocol before starting');
      }
    }
  }, [isRunning, protocol]);

  // Add a waiting time step to the protocol
  const addWaitingTime = useCallback((duration: number) => {
    setProtocol(prev => [...prev, { type: 'wait', duration }]);
    setIsWaitingTimeModalOpen(false);
  }, []);

  // Update settings
  const updateSettings = useCallback((newSettings: ExperimentSettings) => {
    setSettings(newSettings);
    setIsSettingsModalOpen(false);
  }, []);

  // Export data
  const exportData = useCallback((format: 'csv' | 'json') => {
    // Implement data export logic
    setIsExportModalOpen(false);
  }, []);

  // Handle measurement save
  const handleSaveMeasurement = useCallback((measurement: Measurement) => {
    if (measurementModalMode === 'add') {
      setTimelineMeasurements(prev => [...prev, measurement]);
    } else {
      setTimelineMeasurements(prev => 
        prev.map(m => m.id === measurement.id ? measurement : m)
      );
    }
    setIsMeasurementModalOpen(false);
  }, [measurementModalMode]);

  // Handle external device save
  const handleSaveExternalDevice = useCallback((device: ExternalDevice) => {
    if (device.id) {
      // Update existing device
      setExternalDevices(prev => 
        prev.map(d => d.id === device.id ? device : d)
      );
    } else {
      // Add new device
      const newDevice = {
        ...device,
        id: Date.now(), // Generate a temporary ID
      };
      setExternalDevices(prev => [...prev, newDevice]);
    }
    setIsExternalDeviceModalOpen(false);
  }, []);

  return (
    <div className="flex h-screen overflow-hidden bg-gray-900">
      <div className="w-64 bg-gray-800 border-r border-gray-700 flex flex-col">
        <div className="p-4 border-b border-gray-700 flex items-center space-x-3">
          <div className="h-8 w-8 rounded-full bg-gray-700 flex items-center justify-center">
            <img src="/logo.svg" alt="Logo" className="h-6 w-6" />
          </div>
          <h1 className="text-lg font-bold text-white">OpenSens Potentiostat</h1>
        </div>

        {/* Device Section */}
        <div className="p-4 border-b border-gray-700">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center space-x-2">
              <div className="w-3 h-3 bg-green-500 rounded-full"></div>
              <h2 className="text-white font-medium">Device</h2>
            </div>
            <button className="bg-red-600 hover:bg-red-700 text-white text-xs py-1 px-2 rounded">
              Disconnect
            </button>
          </div>
          
          <div className="grid grid-cols-2 gap-2 mt-3">
            <button className="bg-gray-700 hover:bg-gray-600 text-white text-sm py-2 px-3 rounded">
              Calibration
            </button>
            <button className="bg-gray-700 hover:bg-gray-600 text-white text-sm py-2 px-3 rounded">
              Manual
            </button>
          </div>
          
          <div className="mt-3 text-sm">
            <div className="flex justify-between text-gray-400">
              <span>Manufacturer:</span>
              <span className="text-white">OpenSens INC.</span>
            </div>
            <div className="flex justify-between text-gray-400 mt-1">
              <span>Device version:</span>
              <span className="text-white">V2a</span>
            </div>
          </div>
        </div>
        
        {/* Measurement Library */}
        <div className="p-4 border-b border-gray-700">
          <h2 className="text-white font-medium mb-3">Measurement Library</h2>
          <div className="space-y-2">
            <button className="w-full py-2 px-3 bg-gray-700 hover:bg-gray-600 text-white text-left rounded flex items-center">
              <div className="w-2 h-full bg-blue-500 rounded-l absolute left-0"></div>
              <span className="ml-1">CV</span>
            </button>
            <button className="w-full py-2 px-3 bg-gray-700 hover:bg-gray-600 text-white text-left rounded flex items-center">
              <div className="w-2 h-full bg-green-500 rounded-l absolute left-0"></div>
              <span className="ml-1">DPV</span>
            </button>
            <button className="w-full py-2 px-3 bg-gray-700 hover:bg-gray-600 text-white text-left rounded flex items-center">
              <div className="w-2 h-full bg-purple-500 rounded-l absolute left-0"></div>
              <span className="ml-1">CA</span>
            </button>
            <button className="w-full py-2 px-3 bg-gray-700 hover:bg-gray-600 text-white text-left rounded flex items-center">
              <div className="w-2 h-full bg-yellow-500 rounded-l absolute left-0"></div>
              <span className="ml-1">EIS</span>
            </button>
            <button className="w-full py-2 px-3 bg-gray-700 hover:bg-gray-600 text-white text-left rounded flex items-center justify-center">
              <Plus size={16} />
            </button>
          </div>
        </div>
        
        {/* External Device */}
        <div className="p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-white font-medium">External Device</h2>
            <button className="p-1 bg-gray-700 hover:bg-gray-600 rounded">
              <Plus size={16} />
            </button>
          </div>
        </div>
      </div>
      
      <div className="flex-1 flex flex-col">
        {/* Main content */}
        <div className="p-4 flex items-center justify-between border-b border-gray-700">
          <h1 className="text-xl font-bold text-white">Potentiostat Experiment</h1>
          
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2">
              <div className="w-2 h-2 rounded-full bg-green-500"></div>
              <span className="text-sm text-gray-300">Connected</span>
            </div>
            
            <div className="flex space-x-2">
              <button className="p-1.5 bg-gray-700 hover:bg-gray-600 rounded">
                <Settings size={18} />
              </button>
              <button className="p-1.5 bg-gray-700 hover:bg-gray-600 rounded">
                <Sun size={18} />
              </button>
            </div>
          </div>
        </div>
        
        {/* Main Graph Area */}
        <div className="flex-1 p-4">
          {data.length > 0 ? (
            <Chart data={data} />
          ) : (
            <div className="bg-gray-800 rounded-lg h-full flex flex-col items-center justify-center">
              <ResponsiveContainer width="100%" height="90%">
                <LineChart data={[
                  {x: -1.0, y: 0.2},
                  {x: -0.8, y: 0.21},
                  {x: -0.6, y: 0.22},
                  {x: -0.5, y: 0.15},
                  {x: -0.4, y: 0.05},
                  {x: -0.3, y: 0.02},
                  {x: -0.2, y: 0.15},
                  {x: 0.0, y: 0.22},
                  {x: 0.2, y: 0.25},
                  {x: 0.3, y: 0.27},
                  {x: 0.4, y: 0.29},
                  {x: 0.5, y: 0.35},
                  {x: 0.7, y: 0.55},
                  {x: 0.8, y: 0.70},
                  {x: 0.9, y: 0.45},
                  {x: 1.0, y: 0.40},
                ]}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                  <XAxis 
                    dataKey="x" 
                    label={{ value: 'Current (μA)', position: 'insideBottom', offset: -5 }}
                    tick={{ fill: '#aaa' }}
                    domain={[-1, 1]}
                  />
                  <YAxis 
                    label={{ value: 'Potential (V)', angle: -90, position: 'insideLeft' }}
                    tick={{ fill: '#aaa' }}
                    domain={[0, 0.8]}
                  />
                  <Tooltip contentStyle={{ backgroundColor: '#333', border: 'none' }} />
                  <Line 
                    type="monotone" 
                    dataKey="y" 
                    stroke="#3B82F6" 
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
              
              <div className="mt-4 flex justify-between w-full px-6 text-gray-400">
                <div>
                  <div className="text-white">Status: <span className="text-blue-400">Ready</span></div>
                  <div>Voltage: <span className="text-white">0.340 V</span></div>
                </div>
                <div>
                  <div>Current: <span className="text-white">0.40 μA</span></div>
                  <button className="mt-2 bg-blue-600 text-white px-3 py-1 rounded">
                    Auto Focus ON
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
        
        {/* Experiment Timeline */}
        <div className="border-t border-gray-700 p-4">
          <div className="flex justify-between items-center mb-3">
            <h2 className="text-white font-medium">Experiment Timeline</h2>
            <div className="flex space-x-2">
              <button className="bg-gray-700 hover:bg-gray-600 text-white px-3 py-1.5 rounded flex items-center text-sm">
                <Download size={14} className="mr-1" />
                Load
              </button>
              <button className="bg-gray-700 hover:bg-gray-600 text-white px-3 py-1.5 rounded flex items-center text-sm">
                <Save size={14} className="mr-1" />
                Save
              </button>
              <button className="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded flex items-center text-sm">
                <Play size={14} className="mr-1" />
                Run
              </button>
            </div>
          </div>
          
          <div className="h-32 bg-gray-800 rounded-lg p-2 relative">
            <div className="grid grid-cols-12 h-6">
              {[...Array(12)].map((_, i) => (
                <div key={i} className="text-xs text-gray-500 border-l border-gray-700 pl-1">
                  {i * 30}s
                </div>
              ))}
            </div>
            
            <div className="mt-2 h-16 relative border-t border-gray-700 flex">
              <div className="absolute left-16 right-0 bg-gray-700 h-6 mt-2 rounded-sm flex items-center px-2 text-white text-xs">
                CV <span className="ml-2 text-gray-400">120s</span>
                <div className="absolute right-2 flex space-x-1">
                  <button className="text-gray-400 hover:text-white">
                    <Edit2 size={12} />
                  </button>
                  <button className="text-gray-400 hover:text-white">
                    <X size={12} />
                  </button>
                </div>
              </div>
              
              <div className="absolute left-16 right-0 top-12 bg-gray-700 h-6 mt-2 rounded-sm flex items-center px-2 text-white text-xs">
                USB Device 01 <span className="ml-2 text-gray-400">150s</span>
              </div>
            </div>
          </div>
          
          <div className="flex justify-between items-center mt-2">
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-1">
                <div className="w-3 h-3 rounded-full bg-green-500"></div>
                <span className="text-xs text-gray-400">In Progress</span>
              </div>
              <div className="flex items-center space-x-1">
                <div className="w-3 h-3 rounded-full bg-blue-500"></div>
                <span className="text-xs text-gray-400">Completed</span>
              </div>
              <div className="flex items-center space-x-1">
                <div className="w-3 h-3 rounded-full bg-red-500"></div>
                <span className="text-xs text-gray-400">Queued</span>
              </div>
            </div>
            
            <div className="flex items-center space-x-2">
              <span className="text-white">Elapsed Time</span>
              <span className="bg-gray-800 px-2 py-1 rounded text-white font-mono">00:03:17</span>
            </div>
          </div>
        </div>
      </div>
      
      {/* Modals */}
      <MeasurementModal
        isOpen={isMeasurementModalOpen}
        onClose={() => setIsMeasurementModalOpen(false)}
        onSave={handleSaveMeasurement}
        initialData={currentEditingMeasurement}
        mode={measurementModalMode}
      />

      <ExternalDeviceModal
        isOpen={isExternalDeviceModalOpen}
        onClose={() => setIsExternalDeviceModalOpen(false)}
        onSave={handleSaveExternalDevice}
        device={currentEditingDevice}
      />

      <WaitingTimeModal
        isOpen={isWaitingTimeModalOpen}
        onClose={() => setIsWaitingTimeModalOpen(false)}
        onSave={addWaitingTime}
      />

      <SettingsModal
        isOpen={isSettingsModalOpen}
        onClose={() => setIsSettingsModalOpen(false)}
        onSave={updateSettings}
        initialSettings={settings}
      />
      
      <ExportDataModal
        isOpen={isExportModalOpen}
        onClose={() => setIsExportModalOpen(false)}
        onExport={exportData}
        data={data}
      />
    </div>
  );
};

export default PotentiostatApp; 