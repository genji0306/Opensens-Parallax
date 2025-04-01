import React from 'react';
import { Edit2, X } from 'lucide-react';
import { ExternalDevice } from '../../types';

interface ExternalDeviceTimelineProps {
  externalDevices: ExternalDevice[];
  totalDuration: number;
  timelineZoom: number;
  handleDragOver: (e: React.DragEvent<HTMLDivElement>) => void;
  handleDragLeave: (e: React.DragEvent<HTMLDivElement>) => void;
  handleDrop: (e: React.DragEvent<HTMLDivElement>) => void;
  handleDragStart: (e: React.DragEvent<HTMLDivElement>, item: any, type: string) => void;
  handleEditExternalDevice: (id: number) => void;
  handleRemoveExternalDevice: (id: number) => void;
  handleResizeExternalDevice: (id: number, newDuration: number) => void;
  handleTimelineScroll: (e: React.UIEvent<HTMLDivElement>) => void;
}

export const ExternalDeviceTimeline: React.FC<ExternalDeviceTimelineProps> = ({
  externalDevices,
  totalDuration,
  timelineZoom,
  handleDragOver,
  handleDragLeave,
  handleDrop,
  handleDragStart,
  handleEditExternalDevice,
  handleRemoveExternalDevice,
  handleResizeExternalDevice,
  handleTimelineScroll,
}) => {
  return (
    <div className="mt-6">
      <div className="flex justify-between items-center mb-2">
        <h3 className="text-white font-medium text-sm">External Device Timeline</h3>
      </div>
      
      <div 
        className="h-20 bg-gray-800 rounded-lg p-2 relative overflow-x-auto"
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onScroll={handleTimelineScroll}
      >
        <div 
          className="grid h-6 relative" 
          style={{ 
            gridTemplateColumns: `repeat(${Math.ceil(totalDuration / 30)}, minmax(60px, 1fr))`,
            width: `${(totalDuration / 3.6) * (timelineZoom / 100)}px`,
          }}
        >
          {Array.from({ length: Math.ceil(totalDuration / 30) + 1 }).map((_, i) => (
            <div key={i} className="text-xs text-gray-500 border-l border-gray-700 pl-1">
              {i * 30}s
            </div>
          ))}
        </div>
        
        <div 
          className="mt-2 h-10 relative border-t border-gray-700"
          style={{ 
            width: `${(totalDuration / 3.6) * (timelineZoom / 100)}px`, 
          }}
        >
          {/* External devices on timeline */}
          {externalDevices
            .filter(device => device.startTime !== undefined && device.startTime > 0)
            .map(device => {
              const scaledPosition = (device.startTime || 0) / 3.6 * (timelineZoom / 100);
              const scaledWidth = device.duration / 3.6 * (timelineZoom / 100);
              
              return (
                <div 
                  key={device.id}
                  style={{ 
                    left: `${scaledPosition}px`,
                    width: `${scaledWidth}px`, 
                    backgroundColor: device.color || '#6B7280'
                  }}
                  className="absolute h-6 mt-2 rounded-sm flex items-center px-2 text-white text-xs group hover:brightness-110 transition-all"
                  draggable
                  onDragStart={(e) => handleDragStart(e, device, 'device')}
                >
                  {device.name} 
                  <span className="ml-2 text-gray-200">{device.duration}s</span>
                  <div className="absolute right-2 flex space-x-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button 
                      onClick={() => handleEditExternalDevice(device.id)}
                      className="text-gray-200 hover:text-white hover:bg-blue-500 p-0.5 rounded transition-colors"
                    >
                      <Edit2 size={12} />
                    </button>
                    <button 
                      onClick={() => handleRemoveExternalDevice(device.id)}
                      className="text-gray-200 hover:text-white hover:bg-red-500 p-0.5 rounded transition-colors"
                    >
                      <X size={12} />
                    </button>
                  </div>
                  
                  {/* Resize handle */}
                  <div 
                    className="absolute right-0 top-0 bottom-0 w-2 cursor-ew-resize hover:bg-white hover:bg-opacity-30"
                    onMouseDown={(e) => {
                      // Resize handling
                      const startX = e.clientX;
                      const startWidth = scaledWidth;
                      
                      const handleMouseMove = (moveEvent: MouseEvent) => {
                        const diffX = moveEvent.clientX - startX;
                        const newWidth = Math.max(30, startWidth + diffX); // Minimum width
                        
                        // Calculate new duration based on width
                        const newDuration = Math.round((newWidth / (timelineZoom / 100)) * 3.6);
                        handleResizeExternalDevice(device.id, newDuration);
                      };
                      
                      const handleMouseUp = () => {
                        document.removeEventListener('mousemove', handleMouseMove);
                        document.removeEventListener('mouseup', handleMouseUp);
                      };
                      
                      document.addEventListener('mousemove', handleMouseMove);
                      document.addEventListener('mouseup', handleMouseUp);
                    }}
                  />
                </div>
              );
            })}
        </div>
      </div>
    </div>
  );
};

export default ExternalDeviceTimeline; 