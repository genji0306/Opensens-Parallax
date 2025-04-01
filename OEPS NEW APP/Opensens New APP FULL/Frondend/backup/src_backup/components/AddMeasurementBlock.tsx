import React from 'react';
import { Plus } from 'lucide-react';

interface AddMeasurementBlockProps {
  onClick: () => void;
}

export const AddMeasurementBlock: React.FC<AddMeasurementBlockProps> = ({ onClick }) => {
  return (
    <div
      onClick={onClick}
      className="p-2 m-1 bg-gray-700 text-white rounded-lg shadow-md cursor-pointer hover:bg-gray-600 transition-colors flex items-center justify-center"
    >
      <Plus size={20} />
    </div>
  );
}; 