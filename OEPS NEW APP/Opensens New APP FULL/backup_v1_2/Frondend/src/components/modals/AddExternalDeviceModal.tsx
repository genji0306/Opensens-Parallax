import React, { useState } from 'react';
import { X, ExternalLink, Save, Clock } from 'lucide-react';
import { ModalBackdrop } from '../ModalBackdrop';

interface AddExternalDeviceModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (device: any) => void;
  device?: any;
}

export const AddExternalDeviceModal: React.FC<AddExternalDeviceModalProps> = ({
  isOpen,
  onClose,
  onSave,
  device
}) => {
  const [deviceData, setDeviceData] = useState({
    name: device?.name || '',
    type: device?.type || 'relay',
    port: device?.port || 'USB',
    actions: device?.actions || [
      { type: 'on', duration: 10 },
      { type: 'off', duration: 10 }
    ]
  });

  const deviceTypes = [
    { id: 'relay', name: 'Relay Control' },
    { id: 'pump', name: 'Peristaltic Pump' },
    { id: 'stirrer', name: 'Magnetic Stirrer' },
    { id: 'heater', name: 'Heater' },
    { id: 'custom', name: 'Custom Device' }
  ];

  const portTypes = [
    { id: 'USB', name: 'USB Port' },
    { id: 'GPIO', name: 'GPIO Pins' },
    { id: 'bluetooth', name: 'Bluetooth' },
    { id: 'wifi', name: 'Wi-Fi' }
  ];

  const addAction = () => {
    setDeviceData(prev => ({
      ...prev,
      actions: [
        ...prev.actions,
        { type: 'on', duration: 10 }
      ]
    }));
  };

  const removeAction = (index: number) => {
    setDeviceData(prev => ({
      ...prev,
      actions: prev.actions.filter((_, i) => i !== index)
    }));
  };

  const updateAction = (index: number, field: string, value: any) => {
    setDeviceData(prev => ({
      ...prev,
      actions: prev.actions.map((action, i) => 
        i === index ? { ...action, [field]: value } : action
      )
    }));
  };

  const handleChange = (field: string, value: any) => {
    setDeviceData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleSubmit = () => {
    onSave(deviceData);
  };

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

        <div className="space-y-6">
          {/* Device Name */}
          <div className="space-y-2">
            <label className="text-md font-medium text-gray-300 block">Device Name</label>
            <input
              type="text"
              value={deviceData.name}
              onChange={(e) => handleChange('name', e.target.value)}
              placeholder="Enter device name"
              className="bg-gray-700 text-white rounded w-full p-2 border border-gray-600"
            />
          </div>

          {/* Device Type */}
          <div className="space-y-2">
            <label className="text-md font-medium text-gray-300 block">Device Type</label>
            <div className="grid grid-cols-2 gap-2">
              {deviceTypes.map(type => (
                <button
                  key={type.id}
                  onClick={() => handleChange('type', type.id)}
                  className={`py-2 px-3 rounded text-center transition-colors ${
                    deviceData.type === type.id 
                      ? 'bg-blue-600 text-white' 
                      : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                  }`}
                >
                  {type.name}
                </button>
              ))}
            </div>
          </div>

          {/* Port Selection */}
          <div className="space-y-2">
            <label className="text-md font-medium text-gray-300 block">Connection</label>
            <select
              value={deviceData.port}
              onChange={(e) => handleChange('port', e.target.value)}
              className="bg-gray-700 text-white rounded w-full p-2 border border-gray-600"
            >
              {portTypes.map(port => (
                <option key={port.id} value={port.id}>{port.name}</option>
              ))}
            </select>
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
              {deviceData.actions.map((action, index) => (
                <div key={index} className="bg-gray-800 p-3 rounded flex items-center space-x-2">
                  <select
                    value={action.type}
                    onChange={(e) => updateAction(index, 'type', e.target.value)}
                    className="bg-gray-700 text-white rounded p-2 border border-gray-600 flex-shrink-0 w-24"
                  >
                    <option value="on">ON</option>
                    <option value="off">OFF</option>
                    <option value="pulse">PULSE</option>
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
              
              {deviceData.actions.length === 0 && (
                <div className="text-center py-4 text-gray-400 bg-gray-800 rounded">
                  No actions defined yet. Add some actions to control your device.
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="flex justify-end mt-6 pt-4 border-t border-gray-700">
          <div className="flex space-x-4">
            <button
              onClick={onClose}
              className="bg-gray-700 hover:bg-gray-600 text-white px-4 py-2 rounded transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSubmit}
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