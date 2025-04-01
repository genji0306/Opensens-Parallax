import React, { useState, useEffect } from 'react';
import { X } from 'lucide-react';
import { ModalBackdrop } from '../ModalBackdrop';
import { Measurement } from '../../types';
import { MEASUREMENT_TYPES } from '../../constants/measurementTypes';

interface MeasurementModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (data: Measurement) => void;
  initialData?: Measurement | null;
  mode?: 'add' | 'edit';
}

export const MeasurementModal: React.FC<MeasurementModalProps> = ({
  isOpen,
  onClose,
  onSave,
  initialData = null,
  mode = 'add'
}) => {
  const [technique, setTechnique] = useState(initialData?.type || 'CV');
  const [parameters, setParameters] = useState({});
  const [filePath, setFilePath] = useState(initialData?.filePath || '');
  const [activeSection, setActiveSection] = useState('parameters');

  // Find the technique definition
  const selectedTechnique = MEASUREMENT_TYPES.find(t => t.type === technique);

  // Initialize parameters based on selected technique
  useEffect(() => {
    if (selectedTechnique) {
      // If we have initialData, use those values
      if (initialData && initialData.type === technique) {
        setParameters(initialData.parameters || {});
      } else {
        // Otherwise use default values
        const defaultParams = {};
        selectedTechnique.parameters.forEach(param => {
          defaultParams[param.name] = param.default;
        });
        setParameters(defaultParams);
      }
    }
  }, [technique, initialData, selectedTechnique]);

  // Handle parameter changes
  const handleParameterChange = (paramName: string, value: number) => {
    setParameters(prev => ({
      ...prev,
      [paramName]: value
    }));
  };

  // Handle file path browse
  const handleBrowse = () => {
    const simulatedPath = `/data/${technique.toLowerCase()}_${Date.now()}.csv`;
    setFilePath(simulatedPath);
  };

  // Handle save
  const handleSave = () => {
    onSave({
      type: technique,
      color: selectedTechnique?.color || '#888',
      parameters,
      filePath,
      id: initialData?.id || Date.now(),
      estimatedTime: 120, // Default value
      status: 'queued' // Default status
    });
  };

  // Group parameters by their position in the list (for two columns)
  const getParameterGroups = () => {
    if (!selectedTechnique) return [[], []];

    const params = selectedTechnique.parameters;
    const midpoint = Math.ceil(params.length / 2);

    return [
      params.slice(0, midpoint),
      params.slice(midpoint)
    ];
  };

  const parameterGroups = getParameterGroups();

  if (!isOpen) return null;

  return (
    <ModalBackdrop isOpen={isOpen} onClose={onClose}>
      <div className="w-full max-w-2xl p-5">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-xl font-bold text-white flex items-center">
            <span className="pr-2" style={{ color: selectedTechnique?.color || '#fff' }}>
              {mode === 'add' ? 'Add Measurement' : 'Edit Measurement'}
            </span>
            {selectedTechnique && <span className="text-gray-400 text-sm">({selectedTechnique.type})</span>}
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors focus:outline-none hover:rotate-90 transform duration-300"
          >
            <X size={20} />
          </button>
        </div>

        <div className="space-y-6">
          {/* Technique Selection */}
          <div className="space-y-2">
            <label className="text-md font-medium text-gray-300 block">Technique</label>
            <select
              value={technique}
              onChange={(e) => setTechnique(e.target.value)}
              className="bg-gray-700 text-white rounded w-full p-2 border border-gray-600
                        transition-all hover:bg-gray-600"
              style={{
                borderLeftColor: selectedTechnique?.color,
                borderLeftWidth: '4px'
              }}
            >
              {MEASUREMENT_TYPES.map(tech => (
                <option key={tech.type} value={tech.type}>
                  {tech.fullName} ({tech.type})
                </option>
              ))}
            </select>
          </div>

          {/* Section Tabs */}
          <div className="border-b border-gray-700 relative">
            <div className="flex -mb-px">
              <button
                className={`mr-2 py-2 px-4 font-medium relative
                                ${activeSection === 'parameters'
                  ? 'text-white border-b-2 border-blue-500'
                  : 'text-gray-400 hover:text-gray-300'}`}
                onClick={() => setActiveSection('parameters')}
              >
                Parameters
              </button>
              <button
                className={`mr-2 py-2 px-4 font-medium relative
                                ${activeSection === 'storage'
                  ? 'text-white border-b-2 border-blue-500'
                  : 'text-gray-400 hover:text-gray-300'}`}
                onClick={() => setActiveSection('storage')}
              >
                Data Storage
              </button>
            </div>
          </div>

          {/* Parameters Section */}
          <div
            className="space-y-4 min-h-64"
            style={{ display: activeSection === 'parameters' ? 'block' : 'none' }}
          >
            <h3 className="text-md font-medium text-gray-300 pb-2">
              {selectedTechnique?.fullName} Parameters
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-4 max-h-64 overflow-y-auto pr-2">
              {/* First column of parameters */}
              <div className="space-y-4">
                {parameterGroups[0]?.map(param => (
                  <div key={param.name} className="space-y-1">
                    <label className="text-sm text-gray-300">
                      {param.label}
                    </label>
                    <div className="relative">
                      <input
                        type={param.type}
                        value={parameters[param.name] !== undefined ? parameters[param.name] : param.default}
                        onChange={(e) => handleParameterChange(param.name, parseFloat(e.target.value) || 0)}
                        step={param.step}
                        className="bg-gray-700 text-white rounded px-3 py-2 w-full border border-gray-600"
                      />
                    </div>
                  </div>
                ))}
              </div>

              {/* Second column of parameters */}
              <div className="space-y-4">
                {parameterGroups[1]?.map(param => (
                  <div key={param.name} className="space-y-1">
                    <label className="text-sm text-gray-300">
                      {param.label}
                    </label>
                    <div className="relative">
                      <input
                        type={param.type}
                        value={parameters[param.name] !== undefined ? parameters[param.name] : param.default}
                        onChange={(e) => handleParameterChange(param.name, parseFloat(e.target.value) || 0)}
                        step={param.step}
                        className="bg-gray-700 text-white rounded px-3 py-2 w-full border border-gray-600"
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Data Storage Section */}
          <div
            className="space-y-2 min-h-64"
            style={{ display: activeSection === 'storage' ? 'block' : 'none' }}
          >
            <h3 className="text-md font-medium text-gray-300 pb-2">
              Data Storage Settings
            </h3>
            <div className="mt-4">
              <label className="text-sm text-gray-300 block mb-1">
                Save path
              </label>
              <div className="flex">
                <input
                  type="text"
                  value={filePath}
                  onChange={(e) => setFilePath(e.target.value)}
                  className="bg-gray-700 text-white rounded-l px-3 py-2 flex-grow border border-gray-600 border-r-0"
                  placeholder="Enter file path or click browse..."
                />
                <button
                  onClick={handleBrowse}
                  className="bg-gray-600 hover:bg-gray-500 rounded-r px-3 py-2 border border-gray-600 border-l-0"
                >
                  ...
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex justify-between mt-8 border-t border-gray-700 pt-4">
          <div>
            {activeSection === 'parameters' && (
              <button
                onClick={() => setActiveSection('storage')}
                className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded"
              >
                Next: Data Storage
              </button>
            )}
            {activeSection === 'storage' && (
              <button
                onClick={() => setActiveSection('parameters')}
                className="bg-gray-700 hover:bg-gray-600 text-white px-4 py-2 rounded"
              >
                Back to Parameters
              </button>
            )}
          </div>
          <div className="flex space-x-4">
            <button
              onClick={onClose}
              className="bg-gray-700 hover:bg-gray-600 text-white px-4 py-2 rounded"
            >
              Cancel
            </button>

            <button
              onClick={handleSave}
              className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded"
            >
              {mode === 'add' ? 'Add' : 'Save'}
            </button>
          </div>
        </div>
      </div>
    </ModalBackdrop>
  );
}; 