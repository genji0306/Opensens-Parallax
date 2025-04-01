import React, { useState, useEffect } from 'react';
import ModalBase from './ModalBase';
import { ExperimentSettings } from '../../types';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (settings: ExperimentSettings) => void;
  initialSettings: ExperimentSettings;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  onSave,
  initialSettings
}) => {
  const [settings, setSettings] = useState<ExperimentSettings>(initialSettings);
  const [portOptions, setPortOptions] = useState<string[]>(['COM1', 'COM2', 'COM3', '/dev/ttyUSB0', '/dev/ttyUSB1']);
  const [firmwareVersion, setFirmwareVersion] = useState('v1.2.3');
  const [serialNumber, setSerialNumber] = useState('OSP12345678');

  useEffect(() => {
    setSettings(initialSettings);
  }, [initialSettings, isOpen]);

  const handleSave = () => {
    onSave(settings);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value, type } = e.target;
    const newValue = type === 'number' ? Number(value) : value;
    
    setSettings(prev => ({
      ...prev,
      [name]: newValue
    }));
  };

  return (
    <ModalBase isOpen={isOpen} onClose={onClose} title="Device Settings" maxWidth="max-w-xl">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="space-y-4">
          <h3 className="text-white font-medium border-b border-gray-700 pb-2">Communication</h3>
          
          <div className="space-y-2">
            <label className="block text-sm font-medium text-gray-300">
              COM Port
            </label>
            <select
              name="comPort"
              value={settings.comPort}
              onChange={handleChange}
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Select a port</option>
              {portOptions.map(port => (
                <option key={port} value={port}>{port}</option>
              ))}
            </select>
          </div>
          
          <div className="space-y-2">
            <label className="block text-sm font-medium text-gray-300">
              Baud Rate
            </label>
            <select
              name="baudRate"
              value={settings.baudRate}
              onChange={handleChange}
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value={9600}>9600</option>
              <option value={19200}>19200</option>
              <option value={38400}>38400</option>
              <option value={57600}>57600</option>
              <option value={115200}>115200</option>
            </select>
          </div>
        </div>
        
        <div className="space-y-4">
          <h3 className="text-white font-medium border-b border-gray-700 pb-2">Data Acquisition</h3>
          
          <div className="space-y-2">
            <label className="block text-sm font-medium text-gray-300">
              Sample Rate (Hz)
            </label>
            <input
              type="number"
              name="sampleRate"
              value={settings.sampleRate}
              onChange={handleChange}
              min="1"
              max="100"
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <p className="text-xs text-gray-400">Higher values may impact performance</p>
          </div>
          
          <div className="space-y-2">
            <label className="block text-sm font-medium text-gray-300">
              Buffer Size
            </label>
            <input
              type="number"
              name="bufferSize"
              value={settings.bufferSize || 1024}
              onChange={handleChange}
              min="512"
              max="8192"
              step="512"
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
        
        <div className="space-y-4 col-span-1 md:col-span-2">
          <h3 className="text-white font-medium border-b border-gray-700 pb-2">Device Information</h3>
          
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-sm text-gray-400">Firmware Version</p>
              <p className="text-white">{firmwareVersion}</p>
            </div>
            <div>
              <p className="text-sm text-gray-400">Serial Number</p>
              <p className="text-white">{serialNumber}</p>
            </div>
          </div>
        </div>
      </div>

      <div className="pt-6 mt-4 flex justify-end space-x-3 border-t border-gray-700">
        <button
          onClick={onClose}
          className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-md transition-colors"
        >
          Cancel
        </button>
        <button
          onClick={handleSave}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-md transition-colors"
        >
          Save Settings
        </button>
      </div>
    </ModalBase>
  );
};

export default SettingsModal; 