import React, { useState, useEffect } from 'react';
import { X } from 'lucide-react';
import { useRealtimeADC } from '../../hooks/useRealtimeADC';

interface CalibrationModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const CalibrationModal: React.FC<CalibrationModalProps> = ({
  isOpen,
  onClose
}) => {
  const { calibration, updateCalibration } = useRealtimeADC();
  const [offset, setOffset] = useState<string>('0');
  const [gain, setGain] = useState<string>('524288'); // 2^19 default
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Update form when calibration data is loaded
  useEffect(() => {
    if (calibration) {
      setOffset(calibration.dacOffset.toString());
      setGain(calibration.dacGain.toString());
    }
  }, [calibration]);

  const handleSave = async () => {
    try {
      setError(null);
      setIsSaving(true);
      
      // Validate input values
      const offsetValue = parseInt(offset);
      const gainValue = parseInt(gain);
      
      if (isNaN(offsetValue) || isNaN(gainValue)) {
        throw new Error('Invalid offset or gain values');
      }
      
      // Validate ranges
      if (offsetValue < -8388608 || offsetValue > 8388607) { // 24-bit signed range
        throw new Error('Offset must be between -8388608 and 8388607');
      }
      
      if (gainValue < 1 || gainValue > 16777215) { // 24-bit unsigned range
        throw new Error('Gain must be between 1 and 16777215');
      }

      await updateCalibration(offsetValue, gainValue);
      onClose();
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to save calibration');
    } finally {
      setIsSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-gray-800 rounded-lg p-6 w-96 relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-gray-400 hover:text-white"
        >
          <X size={20} />
        </button>

        <h2 className="text-xl font-semibold text-white mb-6">DAC Calibration</h2>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              DAC Offset
            </label>
            <input
              type="number"
              value={offset}
              onChange={(e) => setOffset(e.target.value)}
              className="w-full bg-gray-700 text-white px-3 py-2 rounded border border-gray-600 focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              placeholder="Enter offset value"
            />
            <p className="text-xs text-gray-400 mt-1">
              Range: -8,388,608 to 8,388,607 (24-bit signed)
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              DAC Gain
            </label>
            <input
              type="number"
              value={gain}
              onChange={(e) => setGain(e.target.value)}
              className="w-full bg-gray-700 text-white px-3 py-2 rounded border border-gray-600 focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              placeholder="Enter gain value"
            />
            <p className="text-xs text-gray-400 mt-1">
              Range: 1 to 16,777,215 (24-bit unsigned)
            </p>
          </div>

          {error && (
            <div className="text-red-400 text-sm mt-2">
              {error}
            </div>
          )}

          <div className="flex justify-end space-x-3 mt-6">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm bg-gray-700 text-gray-300 rounded hover:bg-gray-600"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={isSaving}
              className={`px-4 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed ${
                isSaving ? 'opacity-50 cursor-not-allowed' : ''
              }`}
            >
              {isSaving ? 'Saving...' : 'Save Calibration'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}; 