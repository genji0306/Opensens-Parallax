import React, { useState } from 'react';
import { X } from 'lucide-react';

interface MeasurementLibraryBlockProps {
  type: string;
  color: string;
  onDragStart?: (e: React.DragEvent<HTMLDivElement>, type: string, color: string) => void;
  onDoubleClick?: () => void;
  onRemove?: () => void;
}

export const MeasurementLibraryBlock: React.FC<MeasurementLibraryBlockProps> = ({ 
  type, 
  color, 
  onDragStart, 
  onDoubleClick, 
  onRemove 
}) => {
  const [isDragging, setIsDragging] = useState(false);
  
  const handleDragStart = (e: React.DragEvent<HTMLDivElement>, type: string, color: string) => {
    setIsDragging(true);
    
    // Store data for drop handling
    e.dataTransfer.setData('type', type);
    e.dataTransfer.setData('color', color);
    
    // Execute parent drag handler if provided
    if (onDragStart) onDragStart(e, type, color);
  };

  const handleDragEnd = () => {
    setIsDragging(false);
  };

  return (
    <div className="group relative">
      <div 
        draggable 
        onDragStart={(e) => handleDragStart(e, type, color)}
        onDragEnd={handleDragEnd}
        onDoubleClick={onDoubleClick}
        className={`p-2 m-1 bg-gray-700 text-white rounded-lg shadow-md 
                    ${isDragging ? 'opacity-50' : 'opacity-100'} 
                    cursor-grab hover:bg-gray-600 transition-colors 
                    flex items-center justify-center transform 
                    ${isDragging ? 'scale-105' : 'scale-100'}`}
        style={{ 
          borderLeft: `4px solid ${color}`,
          transition: 'all 0.2s ease-in-out'
        }}
      >
        {type}
      </div>
      {/* Remove button - appears on hover */}
      <button
        onClick={onRemove}
        className="absolute -top-2 -right-2 bg-red-500 hover:bg-red-600 text-white rounded-full 
                  w-6 h-6 flex items-center justify-center shadow-lg opacity-0 
                  group-hover:opacity-100 transition-opacity"
        title="Remove measurement"
      >
        <X size={12} />
      </button>
    </div>
  );
}; 