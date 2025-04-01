import { useState } from 'react';
import { Measurement, ExternalDevice } from '../types';

interface UseDragDropProps {
  setTimelineMeasurements: React.Dispatch<React.SetStateAction<Measurement[]>>;
  setExternalDevices: React.Dispatch<React.SetStateAction<ExternalDevice[]>>;
  timelineZoom?: number;
}

export const useDragDrop = ({
  setTimelineMeasurements,
  setExternalDevices,
  timelineZoom = 100
}: UseDragDropProps) => {
  const [dropHighlight, setDropHighlight] = useState(false);
  const [draggedItem, setDraggedItem] = useState<any>(null);

  const handleDragStart = (e: React.DragEvent<HTMLDivElement>, item: any, type: string) => {
    setDraggedItem({ ...item, type });
    e.dataTransfer.setData('text/plain', JSON.stringify({ ...item, type }));
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDropHighlight(true);
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDropHighlight(false);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDropHighlight(false);

    try {
      const data = JSON.parse(e.dataTransfer.getData('text/plain'));
      const rect = e.currentTarget.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const position = Math.round(x / (2 * (timelineZoom / 100))); // Convert pixels to seconds

      if (data.type === 'library') {
        // Create new measurement from library item
        const newMeasurement: Measurement = {
          id: Date.now(),
          type: data.name,
          name: data.name,
          description: `New ${data.name} measurement`,
          status: 'queued',
          estimatedTime: 120,
          color: data.color,
          parameters: {},
          defaultParameters: {},
          filePath: '',
          position: position
        };
        setTimelineMeasurements(prev => [...prev, newMeasurement]);
      } else if (data.type === 'device') {
        // Create new device instance
        const newDevice: ExternalDevice = {
          ...data,
          id: Date.now(),
          startTime: position,
          duration: 150,
          isConnected: true
        };
        setExternalDevices(prev => [...prev, newDevice]);
      }
    } catch (error) {
      console.error('Error handling drop:', error);
    }
  };

  return {
    dropHighlight,
    draggedItem,
    handleDragStart,
    handleDragOver,
    handleDragLeave,
    handleDrop
  };
};

export default useDragDrop; 