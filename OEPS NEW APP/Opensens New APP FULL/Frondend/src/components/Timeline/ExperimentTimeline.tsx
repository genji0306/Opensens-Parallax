import React, { useRef, useState } from 'react';
import { Play, Square, Save, Download, Edit2, X, Plus, Minus, Maximize2, Clock, ChevronDown, ChevronUp } from 'lucide-react';
import { Measurement, ExternalDevice } from '../../types';

interface ExperimentTimelineProps {
  timelineMeasurements: Measurement[];
  setTimelineMeasurements: React.Dispatch<React.SetStateAction<Measurement[]>>;
  externalDevices: ExternalDevice[];
  setExternalDevices: React.Dispatch<React.SetStateAction<ExternalDevice[]>>;
  isRunning: boolean;
  totalDuration: number;
  timelineZoom?: number;
  handleRunClick: () => void;
  handleSaveClick: () => void;
  handleLoadClick: () => void;
  handleDragOver: (e: React.DragEvent<HTMLDivElement>) => void;
  handleDragLeave: (e: React.DragEvent<HTMLDivElement>) => void;
  handleDrop: (e: React.DragEvent<HTMLDivElement>) => void;
  handleDragStart: (e: React.DragEvent<HTMLDivElement>, item: any, type: string) => void;
  handleEditTimelineBlock: (id: number) => void;
  handleRemoveTimelineBlock: (id: number) => void;
  handleResizeTimelineBlock: (id: number, newDuration: number) => void;
  handleEditExternalDevice: (id: number) => void;
  handleRemoveExternalDevice: (id: number) => void;
  handleResizeExternalDevice: (id: number, newDuration: number) => void;
  setWaitingAfterIndex: (index: number) => void;
  setIsWaitingTimeModalOpen: (isOpen: boolean) => void;
  dropHighlight: boolean;
  runningTime: string;
  handleZoomIn?: () => void;
  handleZoomOut?: () => void;
  handleAutoZoom?: () => void;
  handleTimelineScroll?: (e: React.UIEvent<HTMLDivElement>) => void;
}

// Timeline Item Tooltip Component
const TimelineItemTooltip: React.FC<{ item: Measurement | ExternalDevice; visible: boolean; position: { x: number; y: number } }> = ({ 
  item, 
  visible, 
  position 
}) => {
  if (!visible) return null;
  
  const isMeasurement = 'parameters' in item;
  const duration = isMeasurement ? item.estimatedTime : item.duration;
  const parameters = isMeasurement ? item.parameters : {};
  
  return (
    <div 
      className="absolute bg-gray-800 border border-gray-700 rounded-md p-2 shadow-lg text-white text-xs z-50"
      style={{
        top: `${position.y}px`,
        left: `${position.x}px`,
        maxWidth: '200px'
      }}
    >
      <div className="font-bold mb-1">{item.name || item.type}</div>
      <div className="flex items-center mb-1">
        <Clock size={10} className="mr-1 text-gray-400" />
        <span>{duration}s</span>
      </div>
      {isMeasurement && (
        <div className="mt-1 pt-1 border-t border-gray-700">
          <div className="text-gray-400">Parameters:</div>
          {Object.entries(parameters).map(([key, value]) => (
            <div key={key} className="flex justify-between mt-1">
              <span>{key}:</span>
              <span className="font-mono">{String(value)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// Timeline Item Component
const TimelineItem: React.FC<{
  item: Measurement | ExternalDevice;
  index: number;
  onRemove: (id: number) => void;
  onEdit: (id: number) => void;
  isDragging: boolean;
  isDevice?: boolean;
}> = ({ item, index, onRemove, onEdit, isDragging, isDevice = false }) => {
  const [showTooltip, setShowTooltip] = useState(false);
  const [tooltipPosition, setTooltipPosition] = useState({ x: 0, y: 0 });
  
  const handleMouseEnter = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    setTooltipPosition({ 
      x: rect.right + 10, 
      y: rect.top 
    });
    setShowTooltip(true);
  };
  
  const handleMouseLeave = () => {
    setShowTooltip(false);
  };
  
  const isMeasurement = 'position' in item;
  const scaledPosition = isMeasurement ? (item.position || 0) / 3.6 * (100 / 100) : 0;
  const scaledWidth = (isMeasurement ? item.estimatedTime : item.duration) / 3.6 * (100 / 100);
  
  const handleMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    const startX = e.clientX;
    const startWidth = scaledWidth;
    
    const handleMouseMove = (moveEvent: MouseEvent) => {
      const diffX = moveEvent.clientX - startX;
      const newWidth = Math.max(30, startWidth + diffX);
      
      // Calculate new duration based on width
      const newDuration = Math.round((newWidth / (100 / 100)) * 3.6);
      if (item.id) {
        onRemove(item.id);
        onEdit(item.id);
      }
    };
    
    const handleMouseUp = () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
    
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  };
  
  return (
    <div 
      className={`group relative ${isDragging ? 'opacity-50' : ''}`}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <div 
        className="relative flex items-center bg-gray-800 text-white rounded-lg p-2 m-1 shadow-md border-l-4 cursor-grab hover:shadow-lg transition-all duration-200"
        style={{ 
          borderLeftColor: item.color || '#4A90E2',
          width: `${scaledWidth}px`,
          left: `${scaledPosition}px`,
          position: 'absolute',
          height: '32px'
        }}
        draggable
      >
        <div className="flex-grow overflow-hidden">
          <span className="font-semibold block text-sm">{item.name || item.type} {index + 1}</span>
          <div className="flex items-center text-xs text-gray-400 mt-0.5">
            <Clock size={12} className="mr-1 flex-shrink-0" />
            <span>{isMeasurement ? item.estimatedTime : item.duration}s</span>
          </div>
        </div>
        
        {/* Action buttons */}
        <div className="flex space-x-1 ml-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button 
            onClick={() => onEdit(item.id)} 
            className="hover:bg-gray-700 rounded p-1 transition-colors"
            title="Edit"
          >
            <Edit2 size={14} />
          </button>
          <button 
            onClick={() => onRemove(item.id)} 
            className="hover:bg-red-600 rounded p-1 transition-colors"
            title="Remove"
          >
            <X size={14} />
          </button>
        </div>
        
        {/* Resize handle */}
        <div 
          className="absolute right-0 top-0 bottom-0 w-2 cursor-e-resize opacity-0 group-hover:opacity-100 hover:bg-white hover:bg-opacity-20"
          onMouseDown={handleMouseDown}
        />
      </div>
      
      {/* Tooltip */}
      <TimelineItemTooltip
        item={item}
        visible={showTooltip}
        position={tooltipPosition}
      />
    </div>
  );
};

export const ExperimentTimeline: React.FC<ExperimentTimelineProps> = ({
  timelineMeasurements,
  setTimelineMeasurements,
  externalDevices,
  setExternalDevices,
  isRunning,
  totalDuration,
  timelineZoom = 100,
  handleRunClick,
  handleSaveClick,
  handleLoadClick,
  handleDragOver,
  handleDragLeave,
  handleDrop,
  handleDragStart,
  handleEditTimelineBlock,
  handleRemoveTimelineBlock,
  handleResizeTimelineBlock,
  handleEditExternalDevice,
  handleRemoveExternalDevice,
  handleResizeExternalDevice,
  setWaitingAfterIndex,
  setIsWaitingTimeModalOpen,
  dropHighlight,
  runningTime,
  handleZoomIn = () => {},
  handleZoomOut = () => {},
  handleAutoZoom = () => {},
  handleTimelineScroll = () => {}
}) => {
  const timelineRef = useRef<HTMLDivElement>(null);
  const [draggingItem, setDraggingItem] = useState<number | null>(null);
  const [isDevicesCollapsed, setIsDevicesCollapsed] = useState(false);
  const [isMeasurementsCollapsed, setIsMeasurementsCollapsed] = useState(false);

  // Format time (convert seconds to MM:SS)
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  // Generate time markers (every 30 seconds)
  const getTimeMarkers = () => {
    const markers = [];
    for (let time = 0; time <= totalDuration + 60; time += 30) {
      markers.push({
        time,
        position: time * 2, // 2px per second
        label: formatTime(time)
      });
    }
    return markers;
  };

  const timeMarkers = getTimeMarkers();

  return (
    <div className="flex flex-col h-48 bg-gray-900"> {/* Reduced height */}
      {/* Timeline Header */}
      <div className="h-8 bg-gray-800 border-b border-gray-700 flex items-center justify-between px-4">
        <div className="text-sm font-medium text-white">
          Timeline Editor
        </div>
        <div className="flex items-center space-x-2">
          <div className="text-sm text-gray-400">
            Total Duration: <span className="text-white">{formatTime(totalDuration)}</span>
          </div>
          <div className="flex bg-gray-700 rounded overflow-hidden mr-2">
            <button 
              onClick={handleZoomOut}
              className="bg-gray-700 hover:bg-gray-600 text-white p-1 transition-all duration-200 hover:brightness-110"
              title="Zoom Out"
            >
              <Minus size={14} />
            </button>
            <div className="px-2 flex items-center text-gray-300 text-sm">
              {timelineZoom}%
            </div>
            <button 
              onClick={handleZoomIn}
              className="bg-gray-700 hover:bg-gray-600 text-white p-1 transition-all duration-200 hover:brightness-110"
              title="Zoom In"
            >
              <Plus size={14} />
            </button>
            <button 
              onClick={handleAutoZoom}
              className="bg-gray-700 hover:bg-gray-600 text-white p-1 transition-all duration-200 hover:brightness-110 ml-1"
              title="Auto-fit Timeline"
            >
              <Maximize2 size={14} />
            </button>
          </div>
          <button 
            onClick={handleLoadClick}
            className="bg-gray-700 hover:bg-gray-600 text-white px-2 py-1 rounded flex items-center text-sm transition-all duration-200 hover:shadow-md hover:-translate-y-0.5"
          >
            <Download size={14} className="mr-1" />
            Load
          </button>
          <button 
            onClick={handleSaveClick}
            className="bg-gray-700 hover:bg-gray-600 text-white px-2 py-1 rounded flex items-center text-sm transition-all duration-200 hover:shadow-md hover:-translate-y-0.5"
          >
            <Save size={14} className="mr-1" />
            Save
          </button>
          <button 
            onClick={handleRunClick}
            className={`text-white px-2 py-1 rounded flex items-center text-sm transition-all duration-200 hover:shadow-md hover:-translate-y-0.5 ${
              isRunning ? 'bg-red-600 hover:bg-red-700' : 'bg-blue-600 hover:bg-blue-700'
            }`}
          >
            {isRunning ? (
              <><Square size={14} className="mr-1" />Stop</>
            ) : (
              <><Play size={14} className="mr-1" />Run</>
            )}
          </button>
        </div>
      </div>

      {/* Time Ruler */}
      <div className="h-6 bg-gray-800 border-b border-gray-700 flex px-14 relative">
        <div className="absolute left-0 top-0 bottom-0 w-14 bg-gray-800 border-r border-gray-700 flex items-center justify-center">
          <span className="text-xs text-gray-500 font-bold">TIME</span>
        </div>
        
        <div className="flex-grow relative">
          {timeMarkers.map((marker, index) => (
            <div key={index} className="absolute top-0 bottom-0 flex flex-col justify-between items-center" style={{ left: `${marker.position}px` }}>
              <span className="text-xs text-gray-400 mt-0.5">{marker.label}</span>
              <div className="h-1 border-l border-gray-600"></div>
            </div>
          ))}
        </div>
      </div>

      {/* Timeline Content */}
      <div className="flex-grow overflow-x-auto relative">
        {/* Playhead */}
        <div 
          className="absolute top-0 bottom-0 w-px bg-white z-10 pointer-events-none"
          style={{ 
            left: `${(parseInt(runningTime.split(':')[0]) * 60 + parseInt(runningTime.split(':')[1])) * 2 + 14}px`,
            boxShadow: '0 0 4px rgba(255, 255, 255, 0.7)'
          }}
        ></div>

        {/* Measurement Track */}
        <div className={`h-1/2 flex border-b border-gray-700 transition-all duration-200 ${isMeasurementsCollapsed ? 'h-8' : ''}`}>
          <div className="w-14 bg-gray-800 border-r border-gray-700 flex items-center justify-center flex-shrink-0">
            <button 
              onClick={() => setIsMeasurementsCollapsed(!isMeasurementsCollapsed)}
              className="flex items-center text-xs text-gray-400 hover:text-white transition-colors"
            >
              {isMeasurementsCollapsed ? <ChevronDown size={12} /> : <ChevronUp size={12} />}
              <span className="ml-1 transform -rotate-90">Measurements</span>
            </button>
          </div>
          
          <div 
            className={`flex-grow pl-px relative transition-all duration-200 ${
              dropHighlight ? 'border-2 border-blue-500 bg-blue-500 bg-opacity-10' : ''
            }`}
            onDragOver={(e) => {
              e.preventDefault();
              e.stopPropagation();
              handleDragOver(e);
            }}
            onDragLeave={(e) => {
              e.preventDefault();
              e.stopPropagation();
              handleDragLeave(e);
            }}
            onDrop={(e) => {
              e.preventDefault();
              e.stopPropagation();
              handleDrop(e);
            }}
            onScroll={handleTimelineScroll}
          >
            <div className="absolute top-0 left-0 right-0 bottom-0">
              {!isMeasurementsCollapsed && timelineMeasurements.map((item, index) => (
                <TimelineItem
                  key={item.id}
                  item={item}
                  index={index}
                  onRemove={handleRemoveTimelineBlock}
                  onEdit={handleEditTimelineBlock}
                  isDragging={draggingItem === item.id}
                />
              ))}
            </div>
          </div>
        </div>

        {/* External Device Track */}
        <div className={`h-1/2 flex transition-all duration-200 ${isDevicesCollapsed ? 'h-8' : ''}`}>
          <div className="w-14 bg-gray-800 border-r border-gray-700 flex items-center justify-center flex-shrink-0">
            <button 
              onClick={() => setIsDevicesCollapsed(!isDevicesCollapsed)}
              className="flex items-center text-xs text-gray-400 hover:text-white transition-colors"
            >
              {isDevicesCollapsed ? <ChevronDown size={12} /> : <ChevronUp size={12} />}
              <span className="ml-1 transform -rotate-90">Devices</span>
            </button>
          </div>
          
          <div 
            className={`flex-grow pl-px relative transition-all duration-200 ${
              dropHighlight ? 'border-2 border-blue-500 bg-blue-500 bg-opacity-10' : ''
            }`}
            onDragOver={(e) => {
              e.preventDefault();
              e.stopPropagation();
              handleDragOver(e);
            }}
            onDragLeave={(e) => {
              e.preventDefault();
              e.stopPropagation();
              handleDragLeave(e);
            }}
            onDrop={(e) => {
              e.preventDefault();
              e.stopPropagation();
              handleDrop(e);
            }}
          >
            {!isDevicesCollapsed && (
              <div className="absolute top-0 left-0 right-0 bottom-0">
                {externalDevices.map((device, index) => (
                  <TimelineItem
                    key={device.id}
                    item={device}
                    index={index}
                    onRemove={handleRemoveExternalDevice}
                    onEdit={handleEditExternalDevice}
                    isDragging={draggingItem === device.id}
                    isDevice
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ExperimentTimeline; 