import React, { useState, useEffect } from 'react';
import { Edit2, X, Clock, Plus } from 'lucide-react';
import { Measurement } from '../types';
import { MEASUREMENT_TYPES } from '../constants/measurementTypes';

interface TimelineMeasurementBlockProps {
  type: string;
  index: number;
  status?: 'queued' | 'in-progress' | 'completed';
  estimatedTime?: number;
  color: string;
  onRemove?: (id: number) => void;
  onEdit?: (measurement: Measurement) => void;
  onAddAfter?: (index: number) => void;
  measurement: Measurement;
  onDragStart?: (e: React.DragEvent<HTMLDivElement>, id: number) => void;
}

export const TimelineMeasurementBlock: React.FC<TimelineMeasurementBlockProps> = ({
  type,
  index,
  status = 'queued',
  estimatedTime = 200,
  color,
  onRemove,
  onEdit,
  onAddAfter,
  measurement,
  onDragStart
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const [blockWidth, setBlockWidth] = useState(200);

  const getStatusColor = () => {
    switch(status) {
      case 'completed': return 'border-blue-500';
      case 'in-progress': return 'border-green-500';
      case 'queued': return 'border-red-500';
      default: return 'border-gray-500';
    }
  };

  // Find the measurement type definition
  const measurementType = MEASUREMENT_TYPES.find(m => m.type === type);

  // Calculate duration based on settings
  useEffect(() => {
    // For CV, calculate based on scan rate, potential range, and cycles
    if (type === 'CV' && measurement?.parameters) {
      const scanRate = (measurement.parameters.scanRate || 100) / 1000; // mV/s to V/s
      const initialPotential = measurement.parameters.initialPotential || 0;
      const finalPotential = measurement.parameters.finalPotential || 0.8;
      const cycles = measurement.parameters.cycles || 1;

      // Duration = (|Vfinal - Vinitial| × 2 × cycles) ÷ scan rate
      const duration = Math.round((Math.abs(finalPotential - initialPotential) * 2 * cycles) / scanRate);

      // Set block width based on duration (scaled)
      setBlockWidth(Math.max(150, duration / 2));
    } else {
      setBlockWidth(Math.max(150, estimatedTime / 2));
    }
  }, [type, measurement, estimatedTime]);

  // Handle drag operations
  const handleDragStart = (e: React.DragEvent<HTMLDivElement>) => {
    setIsDragging(true);
    e.dataTransfer.setData('moveItem', 'true');
    e.dataTransfer.setData('itemId', measurement.id.toString());

    // Call parent handler if provided
    if (onDragStart) onDragStart(e, measurement.id);
  };

  const handleDragEnd = () => {
    setIsDragging(false);
  };

  return (
    <div className="relative group">
      <div
        className={`relative flex items-center bg-gray-800 text-white rounded-lg p-2 m-1 shadow-md
                          border-l-4 ${getStatusColor()} ${isDragging ? 'opacity-50' : 'opacity-100'}
                          cursor-grab transform ${isDragging ? 'scale-105' : 'scale-100'}`}
        style={{
          borderLeftColor: color,
          width: `${blockWidth}px`,
          transition: 'all 0.2s',
          height: '64px'
        }}
        draggable={true}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
      >
        <div className="flex-grow overflow-hidden">
          <span className="font-semibold block">{type} {index + 1}</span>
          <div className="flex items-center text-xs text-gray-400 mt-1">
            <Clock size={12} className="mr-1 flex-shrink-0" />
            <span>{Math.round(blockWidth / 5 * 10)}s</span>
          </div>

          {/* Show key parameter if available */}
          {measurement?.parameters && measurementType?.parameters?.[0] && (
            <div className="text-xs text-gray-400 mt-1 truncate">
              {measurementType.parameters[0].label.split(' ')[0]}: {measurement.parameters[measurementType.parameters[0].name]}
            </div>
          )}
        </div>
        <div className="flex space-x-1 ml-1">
          <button
            onClick={() => onEdit && onEdit(measurement)}
            className="hover:bg-gray-700 rounded p-1 transition-colors"
            title="Edit Measurement"
          >
            <Edit2 size={14} />
          </button>
          <button
            onClick={() => onRemove && onRemove(measurement.id)}
            className="hover:bg-red-600 rounded p-1 transition-colors"
            title="Remove Measurement"
          >
            <X size={14} />
          </button>
        </div>
      </div>
      {/* Add button that appears on hover */}
      <div className="absolute -right-4 top-1/2 transform -translate-y-1/2 z-10 opacity-0
                        group-hover:opacity-100 transition-opacity">
        <button
          onClick={() => onAddAfter && onAddAfter(index)}
          className="bg-blue-500 hover:bg-blue-600 rounded-full w-8 h-8 flex items-center
                        justify-center shadow-lg transition-transform hover:scale-110"
          title="Add waiting time or measurement"
        >
          <Plus size={16} className="text-white" />
        </button>
      </div>
    </div>
  );
}; 