import React, { useState, useEffect } from 'react';
import { X } from 'lucide-react';
import { ModalBackdrop } from '../ModalBackdrop';
import { ExternalDevice } from '../../types';

interface ExternalDeviceModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (device: ExternalDevice) => void;
  device?: ExternalDevice | null;
}

export const ExternalDeviceModal: React.FC<ExternalDeviceModalProps> = ({
  isOpen,
  onClose,
  onSave,
  device = null
}) => {
  const [deviceName, setDeviceName] = useState(device?.name || 'USB Device');
  const [deviceType, setDeviceType] = useState(device?.type || 'USB');
  const [deviceAction, setDeviceAction] = useState(device?.action || 'ON');
  const [deviceColor, setDeviceColor] = useState(device?.color || '#6B7280');

  // Available device types and actions
  const deviceTypes = ['USB', 'GPIO', 'Pump', 'Temp Controller', 'Sensor'];
  const deviceActions = ['ON', 'OFF', 'TOGGLE', 'READ', 'WRITE'];

  // Predefined colors
  const colorOptions = [
    '#6B7280', // Gray
    '#EF4444', // Red
    '#F59E0B', // Amber
    '#10B981', // Emerald
    '#3B82F6', // Blue
    '#8B5CF6', // Violet
    '#EC4899'  // Pink
  ];

  // Update form when device changes
  useEffect(() => {
    if (device) {
      setDeviceName(device.name || 'USB Device');
      setDeviceType(device.type || 'USB');
      setDeviceAction(device.action || 'ON');
      setDeviceColor(device.color || '#6B7280');
    }
  }, [device]);

  // Handle form submission
  const handleSave = () => {
    onSave({
      id: device?.id || Date.now(),
      name: deviceName,
      type: deviceType,
      action: deviceAction,
      startTime: device?.startTime || 100,
      duration: device?.duration || 150,
      color: deviceColor
    });
  };

  if (!isOpen) return null;

  return (
    <ModalBackdrop isOpen={isOpen} onClose={onClose}>
      <div className="w-full max-w-md p-5">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-xl font-bold text-white">
            {device ? 'Edit External Device' : 'Add External Device'}
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        <div className="space-y-4">
          {/* Device Name */}
          <div className="space-y-2">
            <label className="text-md font-medium text-gray-300 block">Device Name</label>
            <input
              type="text"
              value={deviceName}
              onChange={(e) => setDeviceName(e.target.value)}
              className="bg-gray-700 text-white rounded w-full p-2 border border-gray-600"
              placeholder="Enter device name"
            />
          </div>

          {/* Device Type */}
          <div className="space-y-2">
            <label className="text-md font-medium text-gray-300 block">Device Type</label>
            <select
              value={deviceType}
              onChange={(e) => setDeviceType(e.target.value)}
              className="bg-gray-700 text-white rounded w-full p-2 border border-gray-600"
            >
              {deviceTypes.map(type => (
                <option key={type} value={type}>{type}</option>
              ))}
            </select>
          </div>

          {/* Device Action */}
          <div className="space-y-2">
            <label className="text-md font-medium text-gray-300 block">Device Action</label>
            <select
              value={deviceAction}
              onChange={(e) => setDeviceAction(e.target.value)}
              className="bg-gray-700 text-white rounded w-full p-2 border border-gray-600"
            >
              {deviceActions.map(action => (
                <option key={action} value={action}>{action}</option>
              ))}
            </select>
          </div>

          {/* Device Color */}
          <div className="space-y-2">
            <label className="text-md font-medium text-gray-300 block">Device Color</label>
            <div className="flex flex-wrap gap-2">
              {colorOptions.map(color => (
                <button
                  key={color}
                  onClick={() => setDeviceColor(color)}
                  className={`w-8 h-8 rounded-full ${
                    color === deviceColor ? 'ring-2 ring-white' : ''
                    }`}
                  style={{ backgroundColor: color }}
                />
              ))}
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex justify-end mt-8 pt-4 border-t border-gray-700">
          <div className="flex space-x-4">
            <button
              onClick={onClose}
              className="bg-gray-700 hover:bg-gray-600 text-white px-4 py-2 rounded"
            >
              Cancel
            </button>

            <button
              onClick={handleSave}
              className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded"
            >
              {device ? 'Save' : 'Add Device'}
            </button>
          </div>
        </div>
      </div>
    </ModalBackdrop>
  );
}; 