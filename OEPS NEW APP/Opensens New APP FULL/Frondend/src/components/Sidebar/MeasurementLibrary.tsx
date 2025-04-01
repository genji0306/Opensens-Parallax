import React from 'react';
import { Plus, X, Edit } from 'lucide-react';

export interface MeasurementItem {
  id: string;
  name: string;
  color: string;
}

interface MeasurementLibraryProps {
  measurementLibrary: MeasurementItem[];
  setMeasurementLibrary: React.Dispatch<React.SetStateAction<MeasurementItem[]>>;
  handleDragStart: (e: React.DragEvent<HTMLDivElement>, item: any, type: string) => void;
  handleAddMeasurementClick: () => void;
  handleEditMeasurement: (measurement: MeasurementItem) => void;
}

export const MeasurementLibrary: React.FC<MeasurementLibraryProps> = ({
  measurementLibrary,
  setMeasurementLibrary,
  handleDragStart,
  handleAddMeasurementClick,
  handleEditMeasurement
}) => {
  return (
    <div className="p-4 border-b border-gray-700">
      <h2 className="text-white font-medium mb-3">Measurement Library</h2>
      <div className="space-y-2 max-h-[calc(100vh-480px)] overflow-y-auto pr-1 scrollbar-thin scrollbar-track-gray-800 scrollbar-thumb-gray-600">
        {measurementLibrary.map(measurement => (
          <div 
            key={measurement.id}
            draggable
            onDragStart={(e) => handleDragStart(e, measurement, 'library')}
            onDoubleClick={() => handleEditMeasurement(measurement)}
            className="w-full py-2 px-3 bg-gray-700 hover:bg-gray-600 text-white text-left rounded flex items-center justify-between cursor-move transition-all duration-200 relative group"
          >
            <div className="flex items-center">
              <div className={`w-2 h-full bg-${measurement.color}-500 rounded-l absolute left-0`}></div>
              <span className="ml-1">{measurement.name}</span>
            </div>
            <div className="flex items-center space-x-2 opacity-0 group-hover:opacity-100 transition-opacity">
              <button 
                onClick={() => handleEditMeasurement(measurement)}
                className="text-gray-400 hover:text-white hover:bg-blue-500 p-1 rounded transition-colors"
              >
                <Edit size={12} />
              </button>
              <button 
                onClick={() => {
                  // Remove measurement from library
                  setMeasurementLibrary(prev => prev.filter(m => m.id !== measurement.id));
                }}
                className="text-gray-400 hover:text-white hover:bg-red-500 p-1 rounded transition-colors"
              >
                <X size={12} />
              </button>
            </div>
          </div>
        ))}
        <button 
          onClick={handleAddMeasurementClick}
          className="w-full py-2 px-3 bg-gray-700 hover:bg-gray-600 text-white text-left rounded flex items-center justify-center transition-all duration-200 hover:shadow-md"
        >
          <Plus size={16} className="mr-1" />
          <span>Add Measurement</span>
        </button>
      </div>
    </div>
  );
};

export default MeasurementLibrary; 