import React from 'react';
import { DragDropContext, Droppable, Draggable } from 'react-beautiful-dnd';
import { Clock, Trash2, ChevronUp, ChevronDown } from 'lucide-react';
import { ProtocolStep } from '../types';

interface ExperimentControlsProps {
  protocol: ProtocolStep[];
  setProtocol: React.Dispatch<React.SetStateAction<ProtocolStep[]>>;
  currentStepIndex: number | null;
}

export const ExperimentControls: React.FC<ExperimentControlsProps> = ({
  protocol,
  setProtocol,
  currentStepIndex,
}) => {
  const handleDragEnd = (result: any) => {
    if (!result.destination) return;
    
    const items = Array.from(protocol);
    const [reorderedItem] = items.splice(result.source.index, 1);
    items.splice(result.destination.index, 0, reorderedItem);
    
    setProtocol(items);
  };

  const removeStep = (index: number) => {
    setProtocol(protocol.filter((_, i) => i !== index));
  };

  const moveStep = (index: number, direction: 'up' | 'down') => {
    if (
      (direction === 'up' && index === 0) ||
      (direction === 'down' && index === protocol.length - 1)
    ) {
      return;
    }

    const newProtocol = [...protocol];
    const targetIndex = direction === 'up' ? index - 1 : index + 1;
    
    [newProtocol[index], newProtocol[targetIndex]] = [newProtocol[targetIndex], newProtocol[index]];
    
    setProtocol(newProtocol);
  };

  // Render step card based on step type
  const renderStepCard = (step: ProtocolStep, index: number) => {
    const isActive = currentStepIndex === index;
    
    let content;
    let bgColor = isActive ? 'bg-blue-900' : 'bg-gray-700';
    let icon;
    let title;
    
    switch (step.type) {
      case 'wait':
        icon = <Clock size={16} className="text-gray-400" />;
        title = "Wait";
        content = (
          <p className="text-gray-300">{step.duration} seconds</p>
        );
        break;
        
      case 'measurement':
        icon = <div className="w-4 h-4 rounded-full bg-green-500"></div>;
        title = "Measurement";
        content = (
          <div>
            <p className="text-gray-300">{step.measurementType}</p>
            <p className="text-gray-400 text-xs">Duration: {step.duration}s</p>
          </div>
        );
        break;
        
      case 'cv':
        icon = <div className="w-4 h-4 rounded-full bg-purple-500"></div>;
        title = "Cyclic Voltammetry";
        content = (
          <div>
            <p className="text-gray-300">{step.startVoltage}V to {step.endVoltage}V</p>
            <p className="text-gray-400 text-xs">Scan rate: {step.scanRate}mV/s, Cycles: {step.cycles}</p>
          </div>
        );
        break;
        
      case 'externalDevice':
        icon = <div className="w-4 h-4 rounded-full bg-yellow-500"></div>;
        title = "External Device";
        content = (
          <p className="text-gray-300">Command: {step.command}</p>
        );
        break;
        
      default:
        icon = <div className="w-4 h-4 rounded-full bg-gray-500"></div>;
        title = "Unknown Step";
        content = (
          <p className="text-gray-300">Unknown step type</p>
        );
    }

    return (
      <Draggable key={index} draggableId={`step-${index}`} index={index}>
        {(provided) => (
          <div
            ref={provided.innerRef}
            {...provided.draggableProps}
            {...provided.dragHandleProps}
            className={`${bgColor} rounded-lg p-3 mb-2 transition-colors duration-200`}
          >
            <div className="flex justify-between items-start">
              <div className="flex items-center">
                {icon}
                <h3 className="ml-2 font-medium">{title}</h3>
              </div>
              
              <div className="flex space-x-1">
                <button 
                  onClick={() => moveStep(index, 'up')}
                  disabled={index === 0}
                  className={`p-1 rounded hover:bg-gray-600 ${index === 0 ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  <ChevronUp size={16} />
                </button>
                
                <button 
                  onClick={() => moveStep(index, 'down')}
                  disabled={index === protocol.length - 1}
                  className={`p-1 rounded hover:bg-gray-600 ${index === protocol.length - 1 ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  <ChevronDown size={16} />
                </button>
                
                <button 
                  onClick={() => removeStep(index)}
                  className="p-1 rounded hover:bg-red-700 text-gray-300 hover:text-white"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            </div>
            
            <div className="mt-2">
              {content}
            </div>
          </div>
        )}
      </Draggable>
    );
  };

  return (
    <div className="bg-gray-800 rounded-lg p-4 h-full">
      <h2 className="text-lg font-medium mb-4">Protocol Steps</h2>
      
      {protocol.length === 0 ? (
        <div className="text-center py-10 text-gray-400">
          <p>No steps in protocol</p>
          <p className="text-sm mt-2">Add steps to get started</p>
        </div>
      ) : (
        <DragDropContext onDragEnd={handleDragEnd}>
          <Droppable droppableId="protocol-steps">
            {(provided) => (
              <div
                ref={provided.innerRef}
                {...provided.droppableProps}
                className="space-y-2 max-h-[500px] overflow-y-auto pr-1"
              >
                {protocol.map((step, index) => renderStepCard(step, index))}
                {provided.placeholder}
              </div>
            )}
          </Droppable>
        </DragDropContext>
      )}
    </div>
  );
}; 