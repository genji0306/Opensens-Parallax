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
import { useDevice } from '../contexts/DeviceContext';
import { DeviceResponse } from '../services/usb/types';
import { usbService } from '../services/usb/usbService';
import { parseADC } from '../utils/adcParser';

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
import { CalibrationModal } from './modals/CalibrationModal';
import { ManualControlModal } from './modals/ManualControlModal';
import { AddMeasurementModal } from './modals/AddMeasurementModal';
import { AddExternalDeviceModal } from './modals/AddExternalDeviceModal';
import { PlaybackIndicator } from './PlaybackIndicator';
import { MEASUREMENT_TYPES } from '../constants/measurementTypes';
import { Measurement, ExternalDevice, DataPoint, ProtocolStep, ExperimentSettings } from '../types';
import { SettingsModal } from './modals/SettingsModal';
import { Navbar } from './Navbar';
import { Chart } from './Chart';
import { ExperimentControls } from './ExperimentControls';
import { ExportDataModal } from './modals/ExportDataModal';
import { Sidebar } from './Sidebar';

// Import custom components
import Header from './Header';
import DeviceControls from './Sidebar/DeviceControls';
import MeasurementLibrary, { MeasurementItem } from './Sidebar/MeasurementLibrary';
import ExternalDeviceLibrary from './Sidebar/ExternalDeviceLibrary';
import ExperimentTimeline from './Timeline/ExperimentTimeline';
import ExternalDeviceTimeline from './Timeline/ExternalDeviceTimeline';
import MeasurementGraph from './Graph/MeasurementGraph';
import { USBDeviceCheck } from './USBDeviceCheck';

// Import custom hooks
import useTimelineCalculation from '../hooks/useTimelineCalculation';
import useDragDrop from '../hooks/useDragDrop';
import { useRealtimeADC } from '../hooks/useRealtimeADC';

// Main component
const PotentiostatApp: React.FC = () => {
  const {
    status,
    connect,
    disconnect,
    setCellState,
    setMode,
    setRange
  } = useDevice();

  const { isStreaming } = useRealtimeADC();

  // State management
  const [deviceConnected, setDeviceConnected] = useState(status.isConnected);
  const [connectionText, setConnectionText] = useState(status.isConnected ? "Connected" : "Disconnect");
  const [autoFocus, setAutoFocus] = useState(true);
  const [currentValue, setCurrentValue] = useState(0.4);
  const [potentialValue, setPotentialValue] = useState(0.34);
  const [measurementStatus, setMeasurementStatus] = useState('Ready');
  const [isRunning, setIsRunning] = useState(false);
  const [runningTime, setRunningTime] = useState('00:03:17');
  const [timelineScale, setTimelineScale] = useState(100);
  const [isDarkMode, setIsDarkMode] = useState(true);
  const [isSimulation, setIsSimulation] = useState(true);
  const [commandLog, setCommandLog] = useState<Array<{ command: string; response: string; timestamp: number }>>([]);

  // Timeline state
  const [timelineMeasurements, setTimelineMeasurements] = useState<Measurement[]>([
    {
      id: 1,
      type: 'CV',
      name: 'Cyclic Voltammetry',
      description: 'Default CV measurement',
      status: 'queued',
      estimatedTime: 120,
      color: '#4A90E2',
      parameters: {
        initialPotential: 0.0,
        finalPotential: 0.8,
        scanRate: 100,
        cycles: 3
      },
      defaultParameters: {
        initialPotential: 0.0,
        finalPotential: 0.8,
        scanRate: 100,
        cycles: 3
      },
      filePath: '/data/cv_default.csv',
      position: 0
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
  const [measurementLibrary, setMeasurementLibrary] = useState([
    { id: 'cv', name: 'CV', color: 'blue' },
    { id: 'dpv', name: 'DPV', color: 'green' },
    { id: 'ca', name: 'CA', color: 'purple' },
    { id: 'eis', name: 'EIS', color: 'yellow' }
  ]);

  // Playback state
  const [playheadPosition, setPlayheadPosition] = useState(100);
  const [totalDuration, setTotalDuration] = useState(600);

  // Modal state
  const [isMeasurementModalOpen, setIsMeasurementModalOpen] = useState(false);
  const [isExternalDeviceModalOpen, setIsExternalDeviceModalOpen] = useState(false);
  const [isWaitingTimeModalOpen, setIsWaitingTimeModalOpen] = useState(false);
  const [isCalibrationModalOpen, setIsCalibrationModalOpen] = useState(false);
  const [isManualControlModalOpen, setIsManualControlModalOpen] = useState(false);
  const [isAddMeasurementModalOpen, setIsAddMeasurementModalOpen] = useState(false);
  const [isAddExternalDeviceModalOpen, setIsAddExternalDeviceModalOpen] = useState(false);
  const [currentEditingMeasurement, setCurrentEditingMeasurement] = useState<Measurement | null>(null);
  const [currentEditingDevice, setCurrentEditingDevice] = useState<ExternalDevice | null>(null);
  const [measurementModalMode, setMeasurementModalMode] = useState<'add' | 'edit'>('add');
  const [waitingAfterIndex, setWaitingAfterIndex] = useState(-1);

  // Settings Panel State
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [displayUnits, setDisplayUnits] = useState<'SI' | 'engineering'>('SI');

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

  // Drag and Drop state
  const [isDragging, setIsDragging] = useState(false);
  const [draggedItem, setDraggedItem] = useState(null);
  const [dropHighlight, setDropHighlight] = useState(false);

  // Timeline zoom functions
  const [timelineZoom, setTimelineZoom] = useState(100); // 100% is default zoom
  const [timelineScrollPosition, setTimelineScrollPosition] = useState(0);

  // External Device Timeline
  const [externalDeviceTimeline, setExternalDeviceTimeline] = useState<JSX.Element[]>([]);

  // Use custom hooks
  const { calculateTimelinePositions, addWaitingTime } = useTimelineCalculation(
    timelineMeasurements,
    setTimelineMeasurements,
    setTotalDuration
  );

  const { 
    dropHighlight: dragDropHighlight,
    handleDragStart,
    handleDragOver,
    handleDragLeave,
    handleDrop
  } = useDragDrop({
    setTimelineMeasurements,
    setExternalDevices,
    timelineZoom
  });

  // Update timeline positions when measurements change
  useEffect(() => {
    // Only recalculate if there are measurements and they've changed
    if (timelineMeasurements.length > 0) {
      const hasInvalidPositions = timelineMeasurements.some((measurement, index) => {
        const expectedPosition = timelineMeasurements
          .slice(0, index)
          .reduce((sum, m) => sum + (m.estimatedTime || 120), 0);
        return measurement.position !== expectedPosition;
      });

      if (hasInvalidPositions) {
        calculateTimelinePositions();
      }
    }
  }, [timelineMeasurements, calculateTimelinePositions]);

  // Handle device connection
  const handleConnect = async () => {
    try {
      if (deviceConnected) {
        await disconnect();
        setDeviceConnected(false);
        setConnectionText("Disconnect");
      } else {
        await connect();
        setDeviceConnected(true);
        setConnectionText("Connected");
      }
    } catch (error) {
      console.error('Failed to connect/disconnect:', error);
      // Show error toast or notification
    }
  };

  // Handle cell state toggle
  const handleCellToggle = async () => {
    try {
      const newState = deviceConnected ? 'off' : 'on';
      await setCellState(newState);
      // Update UI state
    } catch (error) {
      console.error('Failed to toggle cell:', error);
      // Show error toast or notification
    }
  };

  // Handle mode switch
  const handleModeSwitch = async (mode: 'potentiostatic' | 'galvanostatic') => {
    try {
      await setMode(mode);
      // Update UI state
    } catch (error) {
      console.error('Failed to switch mode:', error);
      // Show error toast or notification
    }
  };

  // Handle range selection
  const handleRangeSelect = async (range: number) => {
    try {
      await setRange(range);
      // Update UI state
    } catch (error) {
      console.error('Failed to set range:', error);
      // Show error toast or notification
    }
  };

  // Toggle Device Connection
  const toggleDeviceConnection = useCallback(() => {
    setDeviceConnected(!deviceConnected);
    setConnectionText(deviceConnected ? "Connect" : "Disconnect");
  }, [deviceConnected]);

  // Handle Auto Focus Toggle
  const toggleAutoFocus = useCallback(() => {
    setAutoFocus(!autoFocus);
  }, [autoFocus]);

  // Handle Calibration Button Click
  const handleCalibrationClick = useCallback(() => {
    setIsCalibrationModalOpen(true);
  }, []);

  // Handle Manual Control Button Click
  const handleManualControlClick = useCallback(() => {
    setIsManualControlModalOpen(true);
  }, []);

  // Handle Add Measurement Button Click
  const handleAddMeasurementClick = useCallback(() => {
    setIsAddMeasurementModalOpen(true);
  }, []);

  // Handle Add External Device Button Click
  const handleAddExternalDeviceClick = useCallback(() => {
    setIsAddExternalDeviceModalOpen(true);
  }, []);

  // Handle Run Button Click
  const handleRunClick = useCallback(() => {
    setIsRunning(!isRunning);
    setMeasurementStatus(isRunning ? 'Ready' : 'Running');
  }, [isRunning]);

  // Handle Save Button Click
  const handleSaveClick = useCallback(() => {
    // Mock save functionality
    const configuration = {
      timelineMeasurements,
      settings: {
        sampleRate: 10,
        // other settings
      }
    };
    
    const blob = new Blob([JSON.stringify(configuration, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'potentiostat_config.json';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [timelineMeasurements]);

  // Handle Load Button Click
  const handleLoadClick = useCallback(() => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json';
    input.onchange = (e) => {
      const target = e.target as HTMLInputElement;
      const file = target.files?.[0];
      if (file) {
        const reader = new FileReader();
        reader.onload = (event) => {
          const result = event.target?.result;
          if (typeof result === 'string') {
            try {
              const config = JSON.parse(result);
              if (config.timelineMeasurements) {
                setTimelineMeasurements(config.timelineMeasurements);
                // Load other settings
              }
            } catch (error) {
              console.error('Error parsing configuration file:', error);
            }
          }
        };
        reader.readAsText(file);
      }
    };
    input.click();
  }, []);

  // Edit Timeline Block
  const handleEditTimelineBlock = useCallback((id: number) => {
    const block = timelineMeasurements.find(block => block.id === id);
    if (!block) return;
    
    setCurrentEditingMeasurement(block);
    setMeasurementModalMode('edit');
    setIsMeasurementModalOpen(true);
  }, [timelineMeasurements]);

  // Remove Timeline Block
  const handleRemoveTimelineBlock = useCallback((id: number) => {
    setTimelineMeasurements(timelineMeasurements.filter(block => block.id !== id));
  }, [timelineMeasurements]);

  // Timeline Block Resize
  const handleResizeTimelineBlock = useCallback((id: number, newDuration: number) => {
    setTimelineMeasurements(timelineMeasurements.map(block => 
      block.id === id ? { ...block, estimatedTime: newDuration } : block
    ));
  }, [timelineMeasurements]);

  // External Device Block Resize
  const handleResizeExternalDevice = useCallback((id: number, newDuration: number) => {
    setExternalDevices(externalDevices.map(device => 
      device.id === id ? { ...device, duration: newDuration } : device
    ));
  }, [externalDevices]);

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

  // Handle waiting time addition
  const handleAddWaitingTime = useCallback((duration: number) => {
    addWaitingTime(duration, waitingAfterIndex);
    setIsWaitingTimeModalOpen(false);
  }, [addWaitingTime, waitingAfterIndex]);

  // Timeline zoom functions
  const handleZoomIn = () => {
    setTimelineZoom(prev => Math.min(prev + 25, 200)); // Max 200%
  };

  const handleZoomOut = () => {
    setTimelineZoom(prev => Math.max(prev - 25, 25)); // Min 25%
  };

  const handleAutoZoom = () => {
    const containerWidth = timelineRef.current?.clientWidth || 800;
    const totalTimelineWidth = totalDuration / 3.6; // Using the same scaling factor
    const newZoom = Math.min(100, (containerWidth / totalTimelineWidth) * 100);
    setTimelineZoom(newZoom);
  };

  // Handle timeline scroll
  const handleTimelineScroll = (e: React.UIEvent<HTMLDivElement>) => {
    setTimelineScrollPosition(e.currentTarget.scrollLeft);
  };

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

  // Handle adding a new measurement from the AddMeasurementModal
  const handleAddNewMeasurement = useCallback((measurement: any) => {
    setMeasurementLibrary(prev => [
      ...prev, 
      {
        ...measurement,
        id: `${measurement.type.toLowerCase()}-${Date.now()}`, // Ensure unique ID
        name: measurement.name || measurement.type,
        color: measurement.color || 'blue'
      }
    ]);
    setIsAddMeasurementModalOpen(false);
  }, []);

  // Handle adding a new external device from the ExternalDeviceModal
  const handleAddNewExternalDevice = useCallback((device: ExternalDevice) => {
    setExternalDevices(prev => [...prev, device]);
    setIsExternalDeviceModalOpen(false);
  }, []);

  // Handle measurement edit
  const handleEditMeasurement = useCallback((measurement: MeasurementItem) => {
    setCurrentEditingMeasurement({
      id: parseInt(measurement.id),
      type: measurement.name as any,
      name: measurement.name,
      description: `Edit ${measurement.name} measurement`,
      status: 'queued',
      estimatedTime: 120,
      color: measurement.color,
      parameters: {},
      defaultParameters: {},
      filePath: '',
      position: 0
    });
    setMeasurementModalMode('edit');
    setIsMeasurementModalOpen(true);
  }, []);

  // Handle external device edit
  const handleEditExternalDevice = useCallback((id: number) => {
    const device = externalDevices.find(d => d.id === id);
    if (device) {
      setCurrentEditingDevice(device);
      setIsExternalDeviceModalOpen(true);
    }
  }, [externalDevices]);

  // Handle external device remove
  const handleRemoveExternalDevice = useCallback((id: number) => {
    setExternalDevices(prev => prev.filter(d => d.id !== id));
  }, []);

  // Add command logging
  useEffect(() => {
    const handleResponse = (response: DeviceResponse) => {
      setCommandLog(prev => [...prev, {
        command: Array.from(response.data as Uint8Array).map(b => b.toString(16).padStart(2, '0')).join(' '),
        response: response.type === 'text' ? response.data as string : 'Binary response',
        timestamp: response.timestamp
      }]);
    };

    usbService.on('response', handleResponse);
    return () => {
      usbService.off('response', handleResponse);
    };
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

        {/* USB Device Check */}
        <div className="p-4 border-b border-gray-700">
          <USBDeviceCheck />
        </div>

        {/* Device Controls Section */}
        <DeviceControls 
          deviceConnected={deviceConnected}
          connectionText={connectionText}
          toggleDeviceConnection={toggleDeviceConnection}
          handleCalibrationClick={handleCalibrationClick}
          handleManualControlClick={handleManualControlClick}
        />
        
        {/* Measurement Library */}
        <MeasurementLibrary 
          measurementLibrary={measurementLibrary}
          setMeasurementLibrary={setMeasurementLibrary}
          handleDragStart={handleDragStart}
          handleAddMeasurementClick={handleAddMeasurementClick}
          handleEditMeasurement={handleEditMeasurement}
        />
        
        {/* External Device */}
        <ExternalDeviceLibrary 
          externalDevices={externalDevices}
          handleDragStart={handleDragStart}
          handleEditExternalDevice={handleEditExternalDevice}
          handleRemoveExternalDevice={handleRemoveExternalDevice}
          handleAddExternalDeviceClick={handleAddExternalDeviceClick}
        />
      </div>
      
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <Header 
          deviceConnected={deviceConnected}
          openSettingsModal={() => setIsSettingsModalOpen(true)}
          toggleDarkMode={() => setIsDarkMode(!isDarkMode)}
        />
        
        {/* Main Graph Area */}
        <div className="flex-1 p-4">
          <div className="bg-gray-800 rounded-lg h-full">
            <Chart />
          </div>
        </div>
        
        {/* Timeline Area */}
        <div className="h-48 bg-gray-800 border-t border-gray-700 p-4">
          <ExperimentTimeline 
            timelineMeasurements={timelineMeasurements}
            setTimelineMeasurements={setTimelineMeasurements}
            externalDevices={externalDevices}
            setExternalDevices={setExternalDevices}
            isRunning={isRunning}
            totalDuration={totalDuration}
            handleRunClick={handleRunClick}
            handleSaveClick={handleSaveClick}
            handleLoadClick={handleLoadClick}
            handleDragOver={handleDragOver}
            handleDragLeave={handleDragLeave}
            handleDrop={handleDrop}
            handleDragStart={handleDragStart}
            handleEditTimelineBlock={handleEditTimelineBlock}
            handleRemoveTimelineBlock={handleRemoveTimelineBlock}
            handleResizeTimelineBlock={handleResizeTimelineBlock}
            handleEditExternalDevice={handleEditExternalDevice}
            handleRemoveExternalDevice={handleRemoveExternalDevice}
            handleResizeExternalDevice={handleResizeExternalDevice}
            setWaitingAfterIndex={setWaitingAfterIndex}
            setIsWaitingTimeModalOpen={setIsWaitingTimeModalOpen}
            dropHighlight={dragDropHighlight}
            runningTime={runningTime}
            handleZoomIn={handleZoomIn}
            handleZoomOut={handleZoomOut}
            handleAutoZoom={handleAutoZoom}
          />
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
        onSave={currentEditingDevice ? handleSaveExternalDevice : handleAddNewExternalDevice}
        device={currentEditingDevice}
      />

      <WaitingTimeModal
        isOpen={isWaitingTimeModalOpen}
        onClose={() => setIsWaitingTimeModalOpen(false)}
        onSave={handleAddWaitingTime}
      />

      <CalibrationModal
        isOpen={isCalibrationModalOpen}
        onClose={() => setIsCalibrationModalOpen(false)}
      />

      <ManualControlModal
        isOpen={isManualControlModalOpen}
        onClose={() => setIsManualControlModalOpen(false)}
      />
      
      <AddMeasurementModal
        isOpen={isAddMeasurementModalOpen}
        onClose={() => setIsAddMeasurementModalOpen(false)}
        onSave={handleAddNewMeasurement}
      />
      
      <AddExternalDeviceModal
        isOpen={isAddExternalDeviceModalOpen}
        onClose={() => setIsAddExternalDeviceModalOpen(false)}
        onSave={handleAddNewExternalDevice}
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