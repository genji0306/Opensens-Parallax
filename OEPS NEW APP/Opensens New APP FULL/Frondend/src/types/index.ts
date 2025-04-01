export interface Measurement {
  id: number;
  type: string;
  name: string;
  description: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  estimatedTime: number;
  color: string;
  parameters: Record<string, any>;
  defaultParameters: Record<string, any>;
  filePath: string;
  position: number;  // Position in the timeline (in seconds)
  duration?: number;
}

export interface MeasurementType {
  type: string;
  color: string;
  fullName: string;
  parameters: {
    name: string;
    label: string;
    type: string;
    default: any;
    step: number;
  }[];
  group: string;
}

export interface ExternalDevice {
  id: number;
  name: string;
  type: string;
  action: string;
  startTime: number;
  duration: number;
  color: string;
  isConnected: boolean;
  position?: number;
}

export interface DataPoint {
  time: number;
  potential: number;
  current: number;
  [key: string]: any;
}

export interface ProtocolStep {
  type: string;
  [key: string]: any;
}

export interface ExperimentSettings {
  baudRate: number;
  comPort: string;
  sampleRate: number;
  bufferSize?: number;
  [key: string]: any;
} 