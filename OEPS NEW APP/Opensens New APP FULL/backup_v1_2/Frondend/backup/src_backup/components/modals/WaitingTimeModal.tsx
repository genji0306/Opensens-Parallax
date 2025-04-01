import React, { useState, useEffect } from 'react';
import { Clock, X } from 'lucide-react';
import { ModalBackdrop } from '../ModalBackdrop';

interface WaitingTimeModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (duration: number) => void;
  initialDuration?: number;
}

export const WaitingTimeModal: React.FC<WaitingTimeModalProps> = ({
  isOpen,
  onClose,
  onSave,
  initialDuration = 60
}) => {
  const [duration, setDuration] = useState(initialDuration);

  // Reset duration when modal opens
  useEffect(() => {
    setDuration(initialDuration);
  }, [isOpen, initialDuration]);

  return (
    <ModalBackdrop isOpen={isOpen} onClose={onClose}>
      <div className="w-full max-w-sm p-5">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-xl font-bold text-white flex items-center">
            <Clock size={20} className="mr-2 text-gray-400" />
            <span>Set Waiting Time</span>
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        <div className="space-y-6">
          <div className="space-y-2">
            <label className="text-md font-medium text-gray-300 block">Duration (seconds)</label>
            <input
              type="number"
              value={duration}
              onChange={(e) => setDuration(Math.max(1, parseInt(e.target.value) || 1))}
              className="bg-gray-700 text-white rounded w-full p-2 border border-gray-600"
              min="1"
              step="1"
            />
          </div>

          {/* Slider for easier adjustment */}
          <div className="space-y-2">
            <div className="flex justify-between text-sm text-gray-400">
              <span>1s</span>
              <span>5m</span>
            </div>
            <input
              type="range"
              min="1"
              max="300"
              value={duration}
              onChange={(e) => setDuration(parseInt(e.target.value))}
              className="w-full"
            />
          </div>

          {/* Preset Buttons */}
          <div className="flex flex-wrap gap-2">
            {[10, 30, 60, 120, 300].map(preset => (
              <button
                key={preset}
                onClick={() => setDuration(preset)}
                className={`px-3 py-1.5 rounded ${
                  duration === preset
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                  }`}
              >
                {preset >= 60 ? `${preset / 60}m` : `${preset}s`}
              </button>
            ))}
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
              onClick={() => onSave(duration)}
              className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded"
            >
              Add Wait Time
            </button>
          </div>
        </div>
      </div>
    </ModalBackdrop>
  );
}; 