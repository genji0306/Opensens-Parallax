// Measurement Status Types
export type MeasurementStatus = 'queued' | 'in-progress' | 'completed';

// Measurement Interface
export interface Measurement {
  id: number;
  type: string;
  status?: MeasurementStatus;
  estimatedTime: number;
  color: string;
  parameters: Record<string, number>;
  filePath: string;
  isWaiting?: boolean;
  duration?: number;
}

// External Device Interface
export interface ExternalDevice {
  id: number;
  name: string;
  type: string;
  action: string;
  startTime: number;
  duration: number;
  color: string;
}

// Measurement Parameter Interface
export interface MeasurementParameter {
  name: string;
  label: string;
  type: string;
  default: number;
  step: number;
}

// Measurement Type Interface
export interface MeasurementType {
  type: string;
  color: string;
  fullName: string;
  parameters: MeasurementParameter[];
  group: string;
}

// Units type
export type DisplayUnits = 'SI' | 'engineering';

// Data Structures
export interface DataPoint {
  timestamp: number;
  current: number;
  voltage: number;
}

// Protocol Steps
export type StepType = 'wait' | 'measurement' | 'cv' | 'externalDevice';

export interface BaseStep {
  type: StepType;
  id?: number;
}

export interface WaitStep extends BaseStep {
  type: 'wait';
  duration: number; // in seconds
}

export interface MeasurementStep extends BaseStep {
  type: 'measurement';
  measurementType: string;
  duration: number;
  interval: number;
  parameters: Record<string, any>;
}

export interface CyclicVoltammetryStep extends BaseStep {
  type: 'cv';
  startVoltage: number;
  endVoltage: number;
  scanRate: number;
  cycles: number;
}

export interface ExternalDeviceStep extends BaseStep {
  type: 'externalDevice';
  deviceId: number;
  command: string;
  parameters: Record<string, any>;
}

export type ProtocolStep = 
  | WaitStep
  | MeasurementStep
  | CyclicVoltammetryStep
  | ExternalDeviceStep;

// Settings
export interface ExperimentSettings {
  baudRate: number;
  comPort: string;
  sampleRate: number;
}

// Devices
export interface ExternalDevice {
  id: number;
  name: string;
  type: string;
  isConnected: boolean;
  serialPort?: string;
}

// Measurement Library
export interface Measurement {
  id: number;
  name: string;
  type: string;
  description: string;
  defaultParameters: Record<string, any>;
} 