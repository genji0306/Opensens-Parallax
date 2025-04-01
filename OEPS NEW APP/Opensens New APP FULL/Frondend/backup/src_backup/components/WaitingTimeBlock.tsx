import React, { useState, useEffect, useRef } from 'react';
import { Clock, X } from 'lucide-react';
import { Input } from './ui/input';

interface WaitingTimeBlockProps {
  duration?: number;
  onRemove?: () => void;
  onEdit?: (duration: number) => void;
}

export const WaitingTimeBlock: React.FC<WaitingTimeBlockProps> = ({ 
  duration = 60, 
  onRemove, 
  onEdit 
}) => {
  const [isEditingDuration, setIsEditingDuration] = useState(false);
  const [localDuration, setLocalDuration] = useState(duration);
  const inputRef = useRef<HTMLInputElement>(null);

  // Focus input when editing starts
  useEffect(() => {
    if (isEditingDuration && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isEditingDuration]);

  const handleDurationChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = parseInt(e.target.value, 10);
    setLocalDuration(isNaN(value) ? 0 : value);
  };

  const handleDurationBlur = () => {
    setIsEditingDuration(false);
    if (localDuration !== duration && onEdit) {
      onEdit(localDuration);
    }
  };

  const handleDurationKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleDurationBlur();
    } else if (e.key === 'Escape') {
      setIsEditingDuration(false);
      setLocalDuration(duration);
    }
  };

  const blockWidth = Math.max(60, duration); // Scale: 1px per second

  return (
    <div className="group relative p-1 m-1">
      <div
        className="flex flex-col items-center bg-gray-700 text-white rounded-lg p-2 shadow-md justify-center"
        style={{ width: `${blockWidth}px`, height: '64px' }}
      >
        <Clock size={18} className="text-gray-400 mb-1" />
        <div className="text-xs">
          {isEditingDuration ? (
            <Input
              ref={inputRef}
              type="number"
              value={localDuration}
              onChange={handleDurationChange}
              onBlur={handleDurationBlur}
              onKeyDown={handleDurationKeyDown}
              className="w-16 h-8 text-center bg-gray-800 text-white border-gray-600 p-0"
              min="1"
              style={{ padding: '0.25rem' }}
            />
          ) : (
            <span
              onClick={() => setIsEditingDuration(true)}
              className="cursor-pointer select-none"
            >
              {duration}s
            </span>
          )}
        </div>
      </div>
      {/* Remove button - appears on hover */}
      <button
        onClick={onRemove}
        className="absolute -top-2 -right-2 bg-red-500 hover:bg-red-600 text-white rounded-full w-5 h-5 flex items-center justify-center shadow-md opacity-0 group-hover:opacity-100 transition-opacity"
        title="Remove wait time"
      >
        <X size={10} />
      </button>
    </div>
  );
}; 