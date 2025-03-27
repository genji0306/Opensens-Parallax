export interface DeviceInfo {
  manufacturer: string;
  product: string;
  vid: string;
  pid: string;
  control_mode: string;
  current_range: string;
  cell_connected: boolean;
}

export interface Measurement {
  time: string;
  value: number;
  type: 'cv' | 'lsv' | 'ca' | 'cp' | 'eis' | 'dpp' | 'swv' | 'acv' | 'ocp' | 'ms';
}

export interface Theme {
  background: string;
  text: string;
  primary: string;
  border: string;
  hover: string;
  active: string;
  error: string;
}

export interface ChartStyle {
  lineColor: string;
  backgroundColor: string;
  lineWidth: number;
  lineStyle: 'solid' | 'dashed' | 'dotted';
  pointStyle: 'circle' | 'square' | 'triangle' | 'cross';
  pointSize: number;
  tension: number;
} 