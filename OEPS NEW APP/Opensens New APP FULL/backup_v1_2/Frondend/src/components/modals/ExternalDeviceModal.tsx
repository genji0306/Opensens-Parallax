import React, { useState, useEffect } from 'react';
import { X, ExternalLink, Save, Clock } from 'lucide-react';
import { ModalBackdrop } from '../ModalBackdrop';
import { ExternalDevice, DeviceAction, DeviceActionType } from '../../types';

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
  // Basic device information
  const [deviceName, setDeviceName] = useState(device?.name || 'USB Device');
  const [deviceType, setDeviceType] = useState(device?.type || 'USB');
  const [deviceAction, setDeviceAction] = useState(device?.action || 'ON');
  const [deviceColor, setDeviceColor] = useState(device?.color || '#6B7280');
  const [vid, setVid] = useState(device?.vid || '');
  const [pid, setPid] = useState(device?.pid || '');
  const [actions, setActions] = useState<DeviceAction[]>(device?.actions || [
    { type: 'ON', duration: 10 }
  ]);

  // Available options
  const deviceTypes = [
    { id: 'USB', name: 'USB Device' },
    { id: 'GPIO', name: 'GPIO Device' },
    { id: 'PUMP', name: 'Peristaltic Pump' },
    { id: 'TEMP', name: 'Temperature Controller' },
    { id: 'SENSOR', name: 'Sensor' },
    { id: 'CUSTOM', name: 'Custom Device' }
  ];

  const deviceActions: DeviceActionType[] = ['ON', 'OFF', 'TOGGLE', 'READ', 'WRITE', 'PULSE'];

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
      setVid(device.vid || '');
      setPid(device.pid || '');
      setActions(device.actions || [{ type: 'ON', duration: 10 }]);
    }
  }, [device]);

  // Action handlers
  const addAction = () => {
    setActions(prev => [...prev, { type: 'ON', duration: 10 }]);
  };

  const removeAction = (index: number) => {
    setActions(prev => prev.filter((_, i) => i !== index));
  };

  const updateAction = (index: number, field: keyof DeviceAction, value: DeviceActionType | number) => {
    setActions(prev => prev.map((action, i) => 
      i === index ? { ...action, [field]: value } : action
    ));
  };

  // Handle form submission
  const handleSave = () => {
    onSave({
      id: device?.id || Date.now(),
      name: deviceName,
      type: deviceType,
      action: deviceAction,
      startTime: device?.startTime || 0,
      duration: device?.duration || 150,
      color: deviceColor,
      vid,
      pid,
      actions
    });
  };

  if (!isOpen) return null;

  return (
    <ModalBackdrop isOpen={isOpen} onClose={onClose}>
      <div className="w-full max-w-md p-5">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-xl font-bold text-white flex items-center">
            <ExternalLink size={20} className="mr-2 text-gray-400" />
            <span>{device ? 'Edit' : 'Add'} External Device</span>
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
              className="bg-gray-700 text-white rounded w-full p-2 border border-gray-600 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors"
              placeholder="Enter device name"
            />
          </div>

          {/* Device Type */}
          <div className="space-y-2">
            <label className="text-md font-medium text-gray-300 block">Device Type</label>
            <div className="grid grid-cols-2 gap-2">
              {deviceTypes.map(type => (
                <button
                  key={type.id}
                  onClick={() => setDeviceType(type.id)}
                  className={`py-2 px-3 rounded text-center transition-colors ${
                    deviceType === type.id 
                      ? 'bg-blue-600 text-white' 
                      : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                  }`}
                >
                  {type.name}
                </button>
              ))}
            </div>
          </div>

          {/* Connection Settings Group */}
          <div className="space-y-4 bg-gray-800 p-4 rounded-lg">
            <h3 className="text-sm font-medium text-gray-400">Connection Settings</h3>
            
            {/* Connection Type */}
            <div className="space-y-2">
              <label className="text-md font-medium text-gray-300 block">Connection</label>
              <select
                value={deviceType}
                onChange={(e) => setDeviceType(e.target.value)}
                className="bg-gray-700 text-white rounded w-full p-2 border border-gray-600 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors"
              >
                {deviceTypes.map(type => (
                  <option key={type.id} value={type.id}>{type.name}</option>
                ))}
              </select>
            </div>

            {/* VID & PID Fields in single row */}
            <div className="flex items-end gap-4">
              <div className="flex-1 space-y-1">
                <label className="text-sm font-medium text-gray-300 block">VID</label>
                <input
                  type="text"
                  value={vid}
                  onChange={(e) => setVid(e.target.value)}
                  className="bg-gray-700 text-white rounded w-full p-1.5 text-sm border border-gray-600 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors"
                  placeholder="Vendor ID"
                />
              </div>
              <div className="flex-1 space-y-1">
                <label className="text-sm font-medium text-gray-300 block">PID</label>
                <input
                  type="text"
                  value={pid}
                  onChange={(e) => setPid(e.target.value)}
                  className="bg-gray-700 text-white rounded w-full p-1.5 text-sm border border-gray-600 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors"
                  placeholder="Product ID"
                />
              </div>
            </div>
          </div>

          {/* Device Action */}
          <div className="space-y-2">
            <label className="text-md font-medium text-gray-300 block">Default Action</label>
            <select
              value={deviceAction}
              onChange={(e) => setDeviceAction(e.target.value)}
              className="bg-gray-700 text-white rounded w-full p-2 border border-gray-600 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors"
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
                  className={`w-8 h-8 rounded-full transition-transform hover:scale-110 ${
                    color === deviceColor ? 'ring-2 ring-white ring-offset-2 ring-offset-gray-800' : ''
                  }`}
                  style={{ backgroundColor: color }}
                />
              ))}
            </div>
          </div>

          {/* Actions Sequence */}
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <label className="text-md font-medium text-gray-300">Actions Sequence</label>
              <button
                onClick={addAction}
                className="bg-gray-700 hover:bg-gray-600 text-white px-2 py-1 rounded text-sm flex items-center transition-colors"
              >
                Add Action
              </button>
            </div>
            
            <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
              {actions.map((action, index) => (
                <div key={index} className="bg-gray-800 p-3 rounded flex items-center space-x-2">
                  <select
                    value={action.type}
                    onChange={(e) => updateAction(index, 'type', e.target.value as DeviceActionType)}
                    className="bg-gray-700 text-white rounded p-2 border border-gray-600 flex-shrink-0 w-24"
                  >
                    {deviceActions.map(actionType => (
                      <option key={actionType} value={actionType}>{actionType}</option>
                    ))}
                  </select>
                  
                  <div className="flex items-center space-x-2 flex-grow">
                    <Clock size={16} className="text-gray-400" />
                    <input
                      type="number"
                      value={action.duration}
                      onChange={(e) => updateAction(index, 'duration', parseInt(e.target.value) || 0)}
                      min="1"
                      className="bg-gray-700 text-white rounded p-2 border border-gray-600 w-16"
                    />
                    <span className="text-gray-400 text-sm">seconds</span>
                  </div>
                  
                  <button
                    onClick={() => removeAction(index)}
                    className="text-gray-400 hover:text-red-400 p-1 transition-colors"
                  >
                    <X size={16} />
                  </button>
                </div>
              ))}
              
              {actions.length === 0 && (
                <div className="text-center py-4 text-gray-400 bg-gray-800 rounded">
                  No actions defined yet. Add some actions to control your device.
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex justify-end mt-8 pt-4 border-t border-gray-700">
          <div className="flex space-x-4">
            <button
              onClick={onClose}
              className="bg-gray-700 hover:bg-gray-600 text-white px-4 py-2 rounded transition-colors"
            >
              Cancel
            </button>

            <button
              onClick={handleSave}
              className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded flex items-center transition-colors"
            >
              <Save size={18} className="mr-2" />
              {device ? 'Update' : 'Add'} Device
            </button>
          </div>
        </div>
      </div>
    </ModalBackdrop>
  );
}; 