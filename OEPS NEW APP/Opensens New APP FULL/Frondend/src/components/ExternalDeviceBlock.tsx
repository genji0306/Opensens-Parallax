import React from 'react';
import { X, Edit2 } from 'lucide-react';
import { ExternalDevice } from '../types';

interface ExternalDeviceBlockProps {
  device: ExternalDevice;
  onRemove?: (id: number) => void;
  onEdit?: (device: ExternalDevice) => void;
}

export const ExternalDeviceBlock: React.FC<ExternalDeviceBlockProps> = ({ 
  device, 
  onRemove, 
  onEdit 
}) => {
  return (
    <div
      className="bg-gray-800 rounded-lg p-2 shadow-md h-16 flex flex-col justify-between group"
      style={{
        position: 'absolute',
        left: `${device.startTime}px`,
        width: `${device.duration}px`,
        borderLeft: `4px solid ${device.color || '#6B7280'}`
      }}
      draggable
    >
      <div className="flex justify-between items-center">
        <span className="text-sm font-medium">{device.name}</span>
        <div className="flex space-x-1">
          <button
            onClick={() => onEdit && onEdit(device)}
            className="hover:bg-gray-700 rounded p-0.5 transition-colors"
            title="Edit Device"
          >
            <Edit2 size={12} />
          </button>
          <button
            onClick={() => onRemove && onRemove(device.id)}
            className="hover:bg-red-600 rounded p-0.5 transition-colors"
            title="Remove Device"
          >
            <X size={12} />
          </button>
        </div>
      </div>
      <div className="text-xs text-gray-400 flex justify-between">
        <span>{device.action}</span>
        <span>{Math.round(device.duration / 10)}s</span>
      </div>
    </div>
  );
}; 