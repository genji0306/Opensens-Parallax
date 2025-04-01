import React, { useState } from 'react';
import { X, Plus, Save } from 'lucide-react';
import { ModalBackdrop } from '../ModalBackdrop';

interface AddMeasurementModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (measurement: any) => void;
}

export const AddMeasurementModal: React.FC<AddMeasurementModalProps> = ({
  isOpen,
  onClose,
  onSave
}) => {
  const measurementTypes = [
    { id: 'cv', name: 'Cyclic Voltammetry (CV)', color: 'blue' },
    { id: 'dpv', name: 'Differential Pulse Voltammetry (DPV)', color: 'green' },
    { id: 'ca', name: 'Chronoamperometry (CA)', color: 'purple' },
    { id: 'eis', name: 'Electrochemical Impedance Spectroscopy (EIS)', color: 'yellow' },
    { id: 'swv', name: 'Square Wave Voltammetry (SWV)', color: 'red' },
    { id: 'npv', name: 'Normal Pulse Voltammetry (NPV)', color: 'orange' },
    { id: 'gitt', name: 'Galvanostatic Intermittent Titration Technique (GITT)', color: 'pink' }
  ];

  const [selectedType, setSelectedType] = useState(measurementTypes[0]);
  
  // Different parameters based on measurement type
  const [cvParams, setCvParams] = useState({
    startPotential: -0.5,
    endPotential: 0.5,
    scanRate: 100,
    cycles: 3
  });
  
  const [dpvParams, setDpvParams] = useState({
    startPotential: -0.5,
    endPotential: 0.5,
    pulseHeight: 0.05,
    pulseWidth: 0.05,
    stepIncrement: 0.005,
    scanRate: 20
  });
  
  const [caParams, setCaParams] = useState({
    potential: 0.5,
    duration: 30
  });
  
  const [eisParams, setEisParams] = useState({
    frequency: 1000,
    amplitude: 0.01,
    dcBias: 0,
    frequencyRange: [0.1, 100000]
  });

  const handleParamChange = (type: string, name: string, value: any) => {
    switch (type) {
      case 'cv':
        setCvParams(prev => ({ ...prev, [name]: value }));
        break;
      case 'dpv':
        setDpvParams(prev => ({ ...prev, [name]: value }));
        break;
      case 'ca':
        setCaParams(prev => ({ ...prev, [name]: value }));
        break;
      case 'eis':
        setEisParams(prev => ({ ...prev, [name]: value }));
        break;
    }
  };

  const getParamsForType = () => {
    switch (selectedType.id) {
      case 'cv':
        return cvParams;
      case 'dpv':
        return dpvParams;
      case 'ca':
        return caParams;
      case 'eis':
        return eisParams;
      default:
        return {}; // Default fallback
    }
  };

  const handleSave = () => {
    const newMeasurement = {
      id: Date.now().toString(),
      name: selectedType.name,
      type: selectedType.id,
      color: selectedType.color,
      parameters: getParamsForType()
    };
    onSave(newMeasurement);
  };

  const renderParameters = () => {
    switch (selectedType.id) {
      case 'cv':
        return (
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className="text-sm text-gray-300">Start Potential (V)</label>
              <input 
                type="number" 
                value={cvParams.startPotential}
                onChange={(e) => handleParamChange('cv', 'startPotential', parseFloat(e.target.value))}
                step="0.1"
                className="bg-gray-700 text-white rounded w-full p-2 border border-gray-600"
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm text-gray-300">End Potential (V)</label>
              <input 
                type="number" 
                value={cvParams.endPotential}
                onChange={(e) => handleParamChange('cv', 'endPotential', parseFloat(e.target.value))}
                step="0.1"
                className="bg-gray-700 text-white rounded w-full p-2 border border-gray-600"
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm text-gray-300">Scan Rate (mV/s)</label>
              <input 
                type="number" 
                value={cvParams.scanRate}
                onChange={(e) => handleParamChange('cv', 'scanRate', parseInt(e.target.value))}
                className="bg-gray-700 text-white rounded w-full p-2 border border-gray-600"
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm text-gray-300">Cycles</label>
              <input 
                type="number" 
                value={cvParams.cycles}
                onChange={(e) => handleParamChange('cv', 'cycles', parseInt(e.target.value))}
                min="1"
                className="bg-gray-700 text-white rounded w-full p-2 border border-gray-600"
              />
            </div>
          </div>
        );
        
      case 'dpv':
        return (
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className="text-sm text-gray-300">Start Potential (V)</label>
              <input 
                type="number" 
                value={dpvParams.startPotential}
                onChange={(e) => handleParamChange('dpv', 'startPotential', parseFloat(e.target.value))}
                step="0.1"
                className="bg-gray-700 text-white rounded w-full p-2 border border-gray-600"
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm text-gray-300">End Potential (V)</label>
              <input 
                type="number" 
                value={dpvParams.endPotential}
                onChange={(e) => handleParamChange('dpv', 'endPotential', parseFloat(e.target.value))}
                step="0.1"
                className="bg-gray-700 text-white rounded w-full p-2 border border-gray-600"
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm text-gray-300">Pulse Height (V)</label>
              <input 
                type="number" 
                value={dpvParams.pulseHeight}
                onChange={(e) => handleParamChange('dpv', 'pulseHeight', parseFloat(e.target.value))}
                step="0.01"
                className="bg-gray-700 text-white rounded w-full p-2 border border-gray-600"
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm text-gray-300">Pulse Width (s)</label>
              <input 
                type="number" 
                value={dpvParams.pulseWidth}
                onChange={(e) => handleParamChange('dpv', 'pulseWidth', parseFloat(e.target.value))}
                step="0.01"
                className="bg-gray-700 text-white rounded w-full p-2 border border-gray-600"
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm text-gray-300">Step Increment (V)</label>
              <input 
                type="number" 
                value={dpvParams.stepIncrement}
                onChange={(e) => handleParamChange('dpv', 'stepIncrement', parseFloat(e.target.value))}
                step="0.001"
                className="bg-gray-700 text-white rounded w-full p-2 border border-gray-600"
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm text-gray-300">Scan Rate (mV/s)</label>
              <input 
                type="number" 
                value={dpvParams.scanRate}
                onChange={(e) => handleParamChange('dpv', 'scanRate', parseInt(e.target.value))}
                className="bg-gray-700 text-white rounded w-full p-2 border border-gray-600"
              />
            </div>
          </div>
        );
        
      case 'ca':
        return (
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className="text-sm text-gray-300">Potential (V)</label>
              <input 
                type="number" 
                value={caParams.potential}
                onChange={(e) => handleParamChange('ca', 'potential', parseFloat(e.target.value))}
                step="0.1"
                className="bg-gray-700 text-white rounded w-full p-2 border border-gray-600"
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm text-gray-300">Duration (s)</label>
              <input 
                type="number" 
                value={caParams.duration}
                onChange={(e) => handleParamChange('ca', 'duration', parseInt(e.target.value))}
                className="bg-gray-700 text-white rounded w-full p-2 border border-gray-600"
              />
            </div>
          </div>
        );
        
      case 'eis':
        return (
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className="text-sm text-gray-300">Frequency (Hz)</label>
              <input 
                type="number" 
                value={eisParams.frequency}
                onChange={(e) => handleParamChange('eis', 'frequency', parseFloat(e.target.value))}
                className="bg-gray-700 text-white rounded w-full p-2 border border-gray-600"
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm text-gray-300">Amplitude (V)</label>
              <input 
                type="number" 
                value={eisParams.amplitude}
                onChange={(e) => handleParamChange('eis', 'amplitude', parseFloat(e.target.value))}
                step="0.001"
                className="bg-gray-700 text-white rounded w-full p-2 border border-gray-600"
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm text-gray-300">DC Bias (V)</label>
              <input 
                type="number" 
                value={eisParams.dcBias}
                onChange={(e) => handleParamChange('eis', 'dcBias', parseFloat(e.target.value))}
                step="0.1"
                className="bg-gray-700 text-white rounded w-full p-2 border border-gray-600"
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm text-gray-300">Frequency Range (Hz)</label>
              <div className="flex space-x-2">
                <input 
                  type="number" 
                  value={eisParams.frequencyRange[0]}
                  onChange={(e) => handleParamChange('eis', 'frequencyRange', [parseFloat(e.target.value), eisParams.frequencyRange[1]])}
                  className="bg-gray-700 text-white rounded w-full p-2 border border-gray-600"
                  placeholder="Min"
                />
                <span className="text-white self-center">-</span>
                <input 
                  type="number" 
                  value={eisParams.frequencyRange[1]}
                  onChange={(e) => handleParamChange('eis', 'frequencyRange', [eisParams.frequencyRange[0], parseFloat(e.target.value)])}
                  className="bg-gray-700 text-white rounded w-full p-2 border border-gray-600"
                  placeholder="Max"
                />
              </div>
            </div>
          </div>
        );
        
      default:
        return (
          <div className="text-center py-4 text-gray-400">
            Select a measurement type to configure parameters
          </div>
        );
    }
  };

  return (
    <ModalBackdrop isOpen={isOpen} onClose={onClose}>
      <div className="w-full max-w-lg p-5">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-xl font-bold text-white flex items-center">
            <Plus size={20} className="mr-2 text-gray-400" />
            <span>Add Measurement</span>
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        <div className="space-y-6">
          {/* Measurement Type Selection */}
          <div className="space-y-2">
            <label className="text-md font-medium text-gray-300 block">Measurement Type</label>
            <div className="grid grid-cols-2 gap-2 max-h-40 overflow-y-auto pr-2">
              {measurementTypes.map(type => (
                <button
                  key={type.id}
                  onClick={() => setSelectedType(type)}
                  className={`p-3 rounded text-left transition-colors relative overflow-hidden ${
                    selectedType.id === type.id 
                      ? 'bg-gray-600 text-white' 
                      : 'bg-gray-700 text-gray-300 hover:bg-gray-650'
                  }`}
                >
                  <div className={`absolute left-0 top-0 bottom-0 w-1 bg-${type.color}-500`}></div>
                  <span className="ml-2">{type.name}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Parameters Section */}
          <div className="space-y-2">
            <div className="flex justify-between items-center">
              <label className="text-md font-medium text-gray-300 block">Parameters</label>
              <span className={`px-2 py-1 rounded-full text-xs bg-${selectedType.color}-500 bg-opacity-20 text-${selectedType.color}-300`}>
                {selectedType.id.toUpperCase()}
              </span>
            </div>
            <div className="bg-gray-800 p-4 rounded">
              {renderParameters()}
            </div>
          </div>
        </div>

        <div className="flex justify-end mt-6 pt-4 border-t border-gray-700">
          <div className="flex space-x-4">
            <button
              onClick={onClose}
              className="bg-gray-700 hover:bg-gray-600 text-white px-4 py-2 rounded transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded flex items-center transition-colors"
            >
              <Save size={18} className="mr-2" />
              Add to Library
            </button>
          </div>
        </div>
      </div>
    </ModalBackdrop>
  );
}; 