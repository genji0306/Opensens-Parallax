import React, { useState } from 'react';
import ModalBase from './ModalBase';

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
  initialDuration = 30
}) => {
  const [duration, setDuration] = useState(initialDuration);

  const handleSave = () => {
    onSave(duration);
  };

  return (
    <ModalBase isOpen={isOpen} onClose={onClose} title="Add Waiting Time">
      <div className="space-y-4">
        <div className="space-y-2">
          <label className="block text-sm font-medium text-gray-300">
            Duration (seconds)
          </label>
          <input
            type="number"
            value={duration}
            onChange={(e) => setDuration(Number(e.target.value))}
            min="1"
            className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div className="pt-4 flex justify-end space-x-3">
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
            Add
          </button>
        </div>
      </div>
    </ModalBase>
  );
};

export default WaitingTimeModal; 