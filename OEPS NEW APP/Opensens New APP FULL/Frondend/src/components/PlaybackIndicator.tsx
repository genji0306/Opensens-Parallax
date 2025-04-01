import React, { useState, useEffect, useRef } from 'react';
import { getTimeString } from '../lib/utils';

interface PlaybackIndicatorProps {
  position: number;
  isPlaying: boolean;
  totalDuration: number;
  onPositionChange: (pos: number) => void;
}

export const PlaybackIndicator: React.FC<PlaybackIndicatorProps> = ({
  position,
  isPlaying,
  totalDuration,
  onPositionChange
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const handleMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    setIsDragging(true);
    handleMouseMove(e); // Update position immediately on mousedown
    document.addEventListener('mousemove', handleMouseMove as any);
    document.addEventListener('mouseup', handleMouseUp);
  };

  const handleMouseMove = (e: MouseEvent | React.MouseEvent) => {
    if (!isDragging || !containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    let newPosition = e.clientX - rect.left;
    // Keep within bounds
    newPosition = Math.max(0, Math.min(newPosition, rect.width));
    onPositionChange(newPosition);
  };

  const handleMouseUp = () => {
    setIsDragging(false);
    document.removeEventListener('mousemove', handleMouseMove as any);
    document.removeEventListener('mouseup', handleMouseUp);
  };

  useEffect(() => {
    return () => {
      document.removeEventListener('mousemove', handleMouseMove as any);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging]);

  return (
    <div className="absolute top-0 bottom-0 left-0 right-0 cursor-pointer" ref={containerRef} onMouseDown={handleMouseDown}>
      {/* Playhead indicator */}
      <div
        className="absolute top-0 bottom-0 w-0.5 bg-white z-30 cursor-col-resize"
        style={{
          left: `${position}px`,
          boxShadow: '0 0 4px rgba(255, 255, 255, 0.7)',
          transition: isDragging ? 'none' : 'left 0.1s linear'
        }}
      >
        {/* Draggable handle */}
        <div className="absolute -top-1 left-1/2 transform -translate-x-1/2 w-4 h-4
                        bg-white rounded-full z-10 cursor-col-resize"></div>

        {/* Current time indicator */}
        <div className="absolute -top-7 left-1/2 transform -translate-x-1/2 bg-gray-800
                        text-white text-xs py-1 px-2 rounded shadow-lg opacity-0
                        group-hover:opacity-100 transition-opacity">
          {getTimeString(position)}
        </div>
      </div>

      {/* Played area indicator */}
      <div
        className="absolute top-0 bottom-0 bg-blue-500 opacity-10 pointer-events-none"
        style={{
          left: '0',
          width: `${position}px`
        }}
      ></div>
    </div>
  );
}; 