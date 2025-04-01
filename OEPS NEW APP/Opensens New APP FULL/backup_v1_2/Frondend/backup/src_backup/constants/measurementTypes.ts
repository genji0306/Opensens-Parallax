import { MeasurementType } from '../types';

// Measurement Types Constants
export const MEASUREMENT_TYPES: MeasurementType[] = [
  {
    type: 'CV',
    color: '#4A90E2',
    fullName: 'Cyclic Voltammetry',
    parameters: [
      { name: 'initialPotential', label: 'Initial Potential (V)', type: 'number', default: 0.0, step: 0.1 },
      { name: 'finalPotential', label: 'Final Potential (V)', type: 'number', default: 0.8, step: 0.1 },
      { name: 'scanRate', label: 'Scan Rate (mV/s)', type: 'number', default: 100, step: 10 },
      { name: 'cycles', label: 'Number of Cycles', type: 'number', default: 3, step: 1 }
    ],
    group: 'Voltammetry Techniques'
  },
  {
    type: 'DPV',
    color: '#50E3C2',
    fullName: 'Differential Pulse Voltammetry',
    parameters: [
      { name: 'initialPotential', label: 'Initial Potential (V)', type: 'number', default: -0.5, step: 0.1 },
      { name: 'finalPotential', label: 'Final Potential (V)', type: 'number', default: 0.5, step: 0.1 },
      { name: 'pulseAmplitude', label: 'Pulse Amplitude (mV)', type: 'number', default: 50, step: 5 },
      { name: 'pulseWidth', label: 'Pulse Width (ms)', type: 'number', default: 50, step: 5 }
    ],
    group: 'Voltammetry Techniques'
  },
  {
    type: 'CA',
    color: '#BD10E0',
    fullName: 'Chronoamperometry',
    parameters: [
      { name: 'potential', label: 'Potential (V)', type: 'number', default: 0.5, step: 0.1 },
      { name: 'duration', label: 'Duration (s)', type: 'number', default: 60, step: 1 }
    ],
    group: 'Chrono Techniques'
  },
  {
    type: 'EIS',
    color: '#7ED321',
    fullName: 'Electrochemical Impedance Spectroscopy',
    parameters: [
      { name: 'initialFrequency', label: 'Initial Frequency (Hz)', type: 'number', default: 100000, step: 1000 },
      { name: 'finalFrequency', label: 'Final Frequency (Hz)', type: 'number', default: 0.1, step: 0.1 },
      { name: 'amplitude', label: 'Amplitude (mV)', type: 'number', default: 10, step: 1 }
    ],
    group: 'Spectroscopy Techniques'
  }
]; 