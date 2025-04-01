import React from 'react';
import { Plus, Edit2, X } from 'lucide-react';
import { ExternalDevice } from '../../types';

interface ExternalDeviceLibraryProps {
  externalDevices: ExternalDevice[];
  handleDragStart: (e: React.DragEvent<HTMLDivElement>, item: any, type: string) => void;
  handleEditExternalDevice: (id: number) => void;
  handleRemoveExternalDevice: (id: number) => void;
  handleAddExternalDeviceClick: () => void;
}

export const ExternalDeviceLibrary: React.FC<ExternalDeviceLibraryProps> = ({
  externalDevices,
  handleDragStart,
  handleEditExternalDevice,
  handleRemoveExternalDevice,
  handleAddExternalDeviceClick
}) => {
  return (
    <div className="p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-white font-medium">External Device</h2>
        <button 
          onClick={handleAddExternalDeviceClick}
          className="p-1 bg-gray-700 hover:bg-gray-600 rounded transition-all duration-200 hover:shadow-md flex items-center"
          title="Add External Device"
        >
          <Plus size={16} className="text-gray-300" />
        </button>
      </div>
      
      <div className="space-y-2 max-h-[calc(100vh-620px)] overflow-y-auto pr-1 scrollbar-thin scrollbar-track-gray-800 scrollbar-thumb-gray-600">
        {externalDevices
          .filter(device => !device.startTime || device.startTime === 0)
          .map(device => (
          <div 
            key={device.id}
            draggable
            onDragStart={(e) => handleDragStart(e, device, 'device')}
            className="w-full py-2 px-3 bg-gray-700 hover:bg-gray-600 text-white text-left rounded flex items-center justify-between cursor-move transition-colors group"
          >
            <span>{device.name}</span>
            <div className="flex items-center space-x-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <button 
                onClick={() => handleEditExternalDevice(device.id)}
                className="text-gray-400 hover:text-white hover:bg-blue-500 p-0.5 rounded transition-colors"
              >
                <Edit2 size={12} />
              </button>
              <button 
                onClick={() => handleRemoveExternalDevice(device.id)}
                className="text-gray-400 hover:text-white hover:bg-red-500 p-0.5 rounded transition-colors"
              >
                <X size={12} />
              </button>
            </div>
          </div>
        ))}
        {externalDevices.filter(device => !device.startTime || device.startTime === 0).length === 0 && (
          <div className="text-gray-500 text-sm text-center py-2">
            No external devices added
          </div>
        )}
      </div>
    </div>
  );
};

export default ExternalDeviceLibrary; 