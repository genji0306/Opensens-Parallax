export interface ADCData {
  current: number;
  potential: number;
  timestamp: number;
  rawCurrent: number;
  rawPotential: number;
}

export interface CalibrationData {
  dacOffset: number;
  dacGain: number;
}

// Convert 24-bit signed integer to number
function convert24BitSigned(byte1: number, byte2: number, byte3: number): number {
  let value = (byte1 << 16) | (byte2 << 8) | byte3;
  // If the number is negative (MSB is 1)
  if (value & 0x800000) {
    value = value - 0x1000000;
  }
  return value;
}

export function parseADC(data: DataView, calibration?: CalibrationData): ADCData {
  // First 3 bytes are potential, next 3 are current
  const rawPotential = convert24BitSigned(
    data.getUint8(0),
    data.getUint8(1),
    data.getUint8(2)
  );
  
  const rawCurrent = convert24BitSigned(
    data.getUint8(3),
    data.getUint8(4),
    data.getUint8(5)
  );

  // Convert to voltage/current using calibration if available
  let potential = rawPotential;
  let current = rawCurrent;

  if (calibration) {
    potential = (rawPotential - calibration.dacOffset) / calibration.dacGain;
    current = (rawCurrent - calibration.dacOffset) / calibration.dacGain;
  } else {
    // Default scaling if no calibration available
    potential = (rawPotential / 0x7FFFFF) * 8.0;  // Scale to ±8V range
    current = (rawCurrent / 0x7FFFFF) * 25.0;     // Scale to ±25mA range
  }

  return {
    potential,
    current,
    rawPotential,
    rawCurrent,
    timestamp: Date.now()
  };
} 