// WebUSB type definitions
declare global {
  interface Navigator {
    usb: {
      getDevices(): Promise<USBDevice[]>;
      requestDevice(options: { filters: USBDeviceFilter[] }): Promise<USBDevice>;
    };
  }
}

// USB Device Types
export interface USBDevice {
  vendorId: number;
  productId: number;
  manufacturerName?: string;
  productName?: string;
  configuration: USBConfiguration | null;
  serialNumber?: string;
  open(): Promise<void>;
  close(): Promise<void>;
  selectConfiguration(configurationValue: number): Promise<void>;
  claimInterface(interfaceNumber: number): Promise<void>;
  transferOut(endpointNumber: number, data: BufferSource): Promise<USBOutTransferResult>;
  transferIn(endpointNumber: number, length: number): Promise<USBInTransferResult>;
  getInfo(): Promise<USBDeviceInfo>;
}

export interface USBConfiguration {
  configurationValue: number;
  interfaces: USBInterface[];
}

export interface USBInterface {
  interfaceNumber: number;
  alternate: USBAlternateInterface | null;
  alternates: USBAlternateInterface[];
  claimed: boolean;
}

export interface USBAlternateInterface {
  alternateSetting: number;
  interfaceClass: number;
  interfaceSubclass: number;
  interfaceProtocol: number;
  interfaceName?: string;
  endpoints: USBEndpoint[];
}

export interface USBEndpoint {
  endpointNumber: number;
  direction: 'in' | 'out';
  type: 'bulk' | 'interrupt' | 'isochronous';
  packetSize: number;
}

export interface USBOutTransferResult {
  status: 'ok' | 'stall' | 'babble';
  bytesWritten: number;
}

export interface USBInTransferResult {
  status: 'ok' | 'stall' | 'babble';
  data?: DataView;
}

export interface USBDeviceInfo {
  vendorId: number;
  productId: number;
  manufacturerName?: string;
  productName?: string;
}

export interface USBDeviceFilter {
  vendorId: number;
  productId?: number;
}

// Device Response Types
export interface DeviceResponse {
  type: 'text' | 'binary';
  data: string | Uint8Array | Float32Array;
  timestamp: number;
}

// Device Status Types
export interface DeviceStatus {
  isConnected: boolean;
  deviceInfo: USBDeviceInfo | null;
  firmwareVersion: string | null;
  lastError: string | null;
  lastResponse: DeviceResponse | null;
  ledStatus: 'on' | 'off';
}

// Device Command Types
export interface DeviceCommand {
  command: Uint8Array;
  params?: Uint8Array;
}

// Device Configuration Types
export interface DeviceConfig {
  ranges: number[];
  hasCalibration: boolean;
  hasRTD: boolean;
  hasPH: boolean;
}

export type DeviceMode = 'potentiostatic' | 'galvanostatic';
export type CellState = 'on' | 'off'; 