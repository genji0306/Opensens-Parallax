// Measurement Status Types
export type MeasurementStatus = 'queued' | 'in-progress' | 'completed';

// Action Types
export type DeviceActionType = 'ON' | 'OFF' | 'TOGGLE' | 'READ' | 'WRITE' | 'PULSE';

// Device Action Interface
export interface DeviceAction {
  type: DeviceActionType;
  duration: number;
}

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
  position?: number;
  name?: string;
  description?: string;
  defaultParameters?: Record<string, any>;
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
  vid?: string;
  pid?: string;
  actions?: DeviceAction[];
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

interface USBInTransferResult {
  data: DataView;
  status: "ok" | "stall" | "babble";
}

interface USBOutTransferResult {
  status: "ok" | "stall";
  bytesWritten: number;
}

interface USBDevice {
  open(): Promise<void>;
  close(): Promise<void>;
  selectConfiguration(configurationValue: number): Promise<void>;
  claimInterface(interfaceNumber: number): Promise<void>;
  releaseInterface(interfaceNumber: number): Promise<void>;
  transferIn(endpointNumber: number, length: number): Promise<USBInTransferResult>;
  transferOut(endpointNumber: number, data: BufferSource): Promise<USBOutTransferResult>;
  productName: string | null;
  manufacturerName: string | null;
  serialNumber: string | null;
} 