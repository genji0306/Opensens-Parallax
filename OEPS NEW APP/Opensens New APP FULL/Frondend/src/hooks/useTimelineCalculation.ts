import { useCallback, useMemo } from 'react';
import { Measurement } from '../types';

export const useTimelineCalculation = (
  timelineMeasurements: Measurement[],
  setTimelineMeasurements: React.Dispatch<React.SetStateAction<Measurement[]>>,
  setTotalDuration: React.Dispatch<React.SetStateAction<number>>
) => {
  // Memoize the sorted measurements to prevent unnecessary recalculations
  const sortedMeasurements = useMemo(() => {
    return [...timelineMeasurements].sort((a, b) => 
      (a.position || 0) - (b.position || 0)
    );
  }, [timelineMeasurements]);

  // Calculate timeline positions based on start times and durations
  const calculateTimelinePositions = useCallback(() => {
    let currentPosition = 0;
    const updatedMeasurements = sortedMeasurements.map(measurement => {
      const updatedMeasurement = { 
        ...measurement, 
        position: currentPosition 
      };
      // Move the position forward by the measurement's duration
      currentPosition += measurement.estimatedTime || 120;
      return updatedMeasurement;
    });
    
    // Only update if there are actual changes
    const hasChanges = updatedMeasurements.some((measurement, index) => 
      measurement.position !== timelineMeasurements[index]?.position
    );

    if (hasChanges) {
      setTimelineMeasurements(updatedMeasurements);
      
      // Update total duration for timeline scaling
      const totalTime = updatedMeasurements.reduce(
        (total, measurement) => total + (measurement.estimatedTime || 120), 
        0
      );
      setTotalDuration(Math.max(600, totalTime)); // Minimum 600s to prevent empty timeline
    }
  }, [sortedMeasurements, timelineMeasurements, setTimelineMeasurements, setTotalDuration]);

  // Add a waiting time block between measurements
  const addWaitingTime = useCallback((duration: number, waitingAfterIndex: number) => {
    if (waitingAfterIndex < 0 || waitingAfterIndex >= timelineMeasurements.length) {
      return;
    }
    
    const newWaitBlock: Measurement = {
      id: Date.now(),
      type: 'wait',
      name: 'Wait',
      description: 'Waiting period',
      status: 'queued',
      estimatedTime: duration,
      color: '#6B7280',
      parameters: {},
      defaultParameters: {},
      filePath: '',
      position: (timelineMeasurements[waitingAfterIndex].position || 0) + 
                (timelineMeasurements[waitingAfterIndex].estimatedTime || 120)
    };
    
    // Insert the wait block after the specified index
    const updatedMeasurements = [
      ...timelineMeasurements.slice(0, waitingAfterIndex + 1),
      newWaitBlock,
      ...timelineMeasurements.slice(waitingAfterIndex + 1)
    ];
    
    setTimelineMeasurements(updatedMeasurements);
    
    return true;
  }, [timelineMeasurements, setTimelineMeasurements]);

  return {
    calculateTimelinePositions,
    addWaitingTime
  };
};

export default useTimelineCalculation; 