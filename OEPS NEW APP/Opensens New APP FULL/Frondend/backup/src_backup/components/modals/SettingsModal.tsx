import React, { useState, useEffect } from 'react';
import { Settings, X } from 'lucide-react';
import { ModalBackdrop } from '../ModalBackdrop';
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
  const [baudRate, setBaudRate] = useState(initialSettings.baudRate);
  const [comPort, setComPort] = useState(initialSettings.comPort);
  const [sampleRate, setSampleRate] = useState(initialSettings.sampleRate);
  const [availablePorts, setAvailablePorts] = useState<string[]>([]);

  // Reset form when modal opens
  useEffect(() => {
    if (isOpen) {
      setBaudRate(initialSettings.baudRate);
      setComPort(initialSettings.comPort);
      setSampleRate(initialSettings.sampleRate);
      // In a real app, we would fetch available ports
      setAvailablePorts(['COM1', 'COM2', 'COM3', 'COM4', '/dev/ttyUSB0', '/dev/ttyUSB1']);
    }
  }, [isOpen, initialSettings]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSave({
      baudRate,
      comPort,
      sampleRate
    });
  };

  return (
    <ModalBackdrop isOpen={isOpen} onClose={onClose}>
      <div className="w-full max-w-md p-5">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-xl font-bold text-white flex items-center">
            <Settings size={20} className="mr-2 text-gray-400" />
            <span>Device Settings</span>
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* COM Port Selection */}
          <div className="space-y-2">
            <label className="text-md font-medium text-gray-300 block">COM Port</label>
            <select
              value={comPort}
              onChange={(e) => setComPort(e.target.value)}
              className="bg-gray-700 text-white rounded w-full p-2 border border-gray-600"
            >
              <option value="">Select Port</option>
              {availablePorts.map((port) => (
                <option key={port} value={port}>
                  {port}
                </option>
              ))}
            </select>
            <p className="text-xs text-gray-400">Select the port your device is connected to</p>
          </div>

          {/* Baud Rate */}
          <div className="space-y-2">
            <label className="text-md font-medium text-gray-300 block">Baud Rate</label>
            <select
              value={baudRate}
              onChange={(e) => setBaudRate(Number(e.target.value))}
              className="bg-gray-700 text-white rounded w-full p-2 border border-gray-600"
            >
              {[1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200].map((rate) => (
                <option key={rate} value={rate}>
                  {rate}
                </option>
              ))}
            </select>
            <p className="text-xs text-gray-400">Communication speed with the device</p>
          </div>

          {/* Sample Rate */}
          <div className="space-y-2">
            <label className="text-md font-medium text-gray-300 block">
              Sample Rate (samples/second)
            </label>
            <input
              type="number"
              value={sampleRate}
              onChange={(e) => setSampleRate(Number(e.target.value))}
              min="1"
              max="1000"
              className="bg-gray-700 text-white rounded w-full p-2 border border-gray-600"
            />
            <p className="text-xs text-gray-400">Higher rates provide more detail but use more memory</p>
          </div>

          {/* Action Buttons */}
          <div className="flex justify-end pt-4 border-t border-gray-700">
            <div className="flex space-x-4">
              <button
                type="button"
                onClick={onClose}
                className="bg-gray-700 hover:bg-gray-600 text-white px-4 py-2 rounded"
              >
                Cancel
              </button>

              <button
                type="submit"
                className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded"
              >
                Save Settings
              </button>
            </div>
          </div>
        </form>
      </div>
    </ModalBackdrop>
  );
}; 