import { USBDeviceInfo, DeviceResponse, DeviceStatus, DeviceCommand, DeviceConfig, USBDevice } from './types';

class USBService {
  private device: USBDevice | null = null;
  private vendorId: number = 0xa0a0;
  private productId: number = 0x0002;
  private isOperationInProgress: boolean = false;
  private operationLock: Promise<void> = Promise.resolve();
  private status: DeviceStatus = {
    isConnected: false,
    deviceInfo: null,
    firmwareVersion: null,
    lastError: null,
    lastResponse: null,
    ledStatus: 'off'
  };
  private config: DeviceConfig = {
    ranges: [],
    hasCalibration: false,
    hasRTD: false,
    hasPH: false
  };

  // Command constants matching firmware
  private readonly COMMANDS = {
    TURN_CELL_ON: "CELL ON",
    TURN_CELL_OFF: "CELL OFF",
    SET_MODE: "MODE",
    READ_ADC: "ADCREAD",
    READ_LED: "LED",
    READ_CELL_STATE: "CELL",
    READ_MODE: "MODE",
    READ_RANGES: "RANGE",
    READ_CALIBRATION: "CAL",
    READ_RTD: "RTD",
    READ_PH: "PH",
    READ_DAC_CAL: "DACCAL",
    SET_DAC_CAL: "DACCALSET"
  };

  private readonly validCommands = [
    "ADCREAD", "CELL ON", "CELL OFF", "DACSET", "DACCAL", 
    "RANGE 1", "RANGE 2", "DACCALSET", "DACCALGET", "MODE",
    "LED", "CELL", "CAL", "RTD", "PH"
  ];

  private eventListeners: Map<string, Function[]> = new Map();

  constructor() {
    // Check if WebUSB is supported
    if (!navigator.usb) {
      throw new Error('WebUSB is not supported in this browser');
    }
  }

  // Set device IDs
  setDeviceIds(vendorId: number, productId: number): void {
    this.vendorId = vendorId;
    this.productId = productId;
  }

  // List available USB devices
  async listAvailableDevices(): Promise<USBDeviceInfo[]> {
    try {
      const devices = await navigator.usb.getDevices();
      return devices.map(device => ({
        vendorId: device.vendorId,
        productId: device.productId,
        manufacturerName: device.manufacturerName || 'Unknown',
        productName: device.productName || 'Unknown'
      }));
    } catch (error) {
      console.error('Failed to list USB devices:', error);
      this.status.lastError = error instanceof Error ? error.message : 'Failed to list devices';
      this.emit('error', this.status.lastError);
      return [];
    }
  }

  private parseResponse(data: DataView): DeviceResponse {
    // Check if the response is text (ASCII) or binary
    const isText = this.isTextResponse(data);
    
    if (isText) {
      // Convert bytes to text
      const text = new TextDecoder().decode(data);
      return {
        type: 'text',
        data: text.trim(),
        timestamp: Date.now()
      };
    } else {
      // Return binary data
      return {
        type: 'binary',
        data: new Uint8Array(data.buffer),
        timestamp: Date.now()
      };
    }
  }

  private async withLock<T>(operation: () => Promise<T>): Promise<T> {
    if (this.isOperationInProgress) {
      // Instead of throwing, wait for the current operation to complete
      await this.operationLock;
    }

    this.isOperationInProgress = true;
    let resolveLock: (() => void) | undefined;
    
    try {
      // Create a new lock
      this.operationLock = new Promise(resolve => {
        resolveLock = resolve;
      });

      // Execute the operation
      const result = await operation();
      
      return result;
    } finally {
      this.isOperationInProgress = false;
      resolveLock?.();
    }
  }

  async checkDeviceConnection(): Promise<boolean> {
    return this.withLock(async () => {
      try {
        // Look for available devices
        const devices = await navigator.usb.getDevices();
        const opensensDevice = devices.find(device => 
          device.vendorId === this.vendorId && device.productId === this.productId
        );

        // If we found our device
        if (opensensDevice) {
          // If it's the same device we already have and it's connected
          if (this.device && 
              this.device.vendorId === opensensDevice.vendorId && 
              this.device.productId === opensensDevice.productId && 
              this.status.isConnected) {
            return true;
          }

          // Store device reference before initialization
          const previousDevice = this.device;
          this.device = opensensDevice;

          try {
            await this.initializeDevice();
            return true;
          } catch (error) {
            console.error('Failed to initialize device:', error);
            // Restore previous device state if initialization fails
            this.device = previousDevice;
            this.status.isConnected = false;
            return false;
          }
        }

        // No matching device found
        return false;
      } catch (error) {
        console.error('Failed to check device connection:', error);
        this.status.lastError = error instanceof Error ? error.message : 'Failed to check connection';
        this.emit('error', this.status.lastError);
        return false;
      }
    });
  }

  private async initializeDevice(): Promise<void> {
    try {
      if (!this.device) {
        throw new Error('No device selected');
      }

      // First open the device
      console.log('Opening device...');
      await this.device.open();
      console.log('Device opened successfully');

      // Add a delay after opening
      await new Promise(resolve => setTimeout(resolve, 500));

      // Select configuration first
      console.log('Selecting configuration 1...');
      await this.device.selectConfiguration(1);
      console.log('Configuration 1 selected successfully');

      // Add a delay after configuration
      await new Promise(resolve => setTimeout(resolve, 500));

      // Try to claim the interface with retries
      let retryCount = 0;
      const maxRetries = 3;
      let lastError: Error | null = null;

      while (retryCount < maxRetries) {
        try {
          console.log(`Attempting to claim interface 0 (attempt ${retryCount + 1}/${maxRetries})...`);
          await this.device.claimInterface(0);
          console.log('Successfully claimed interface 0');
          break;
        } catch (error) {
          lastError = error as Error;
          console.log(`Failed to claim interface (attempt ${retryCount + 1}):`, error);
          retryCount++;
          
          if (retryCount < maxRetries) {
            // Wait before retrying
            await new Promise(resolve => setTimeout(resolve, 1000));
          }
        }
      }

      if (retryCount === maxRetries) {
        throw new Error(`Failed to claim interface after ${maxRetries} attempts: ${lastError?.message}`);
      }

      // Test ADC read with retries
      let adcRetryCount = 0;
      const maxAdcRetries = 3;
      let adcSuccess = false;

      while (adcRetryCount < maxAdcRetries && !adcSuccess) {
        try {
          console.log(`Testing ADC read (attempt ${adcRetryCount + 1}/${maxAdcRetries})...`);
          const response = await this.sendCommand('ADCREAD');
          console.log('ADC response:', response);
          
          if (response && response.type === 'binary') {
            adcSuccess = true;
            console.log('ADC read successful');
          } else {
            console.log('Invalid ADC response, retrying...');
            adcRetryCount++;
            await new Promise(resolve => setTimeout(resolve, 500));
          }
        } catch (error) {
          console.error('ADC read error:', error);
          adcRetryCount++;
          if (adcRetryCount < maxAdcRetries) {
            await new Promise(resolve => setTimeout(resolve, 500));
          }
        }
      }

      if (!adcSuccess) {
        throw new Error('Failed to get valid ADC response after multiple attempts');
      }

      // Add a delay before emitting connect event
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      this.status.isConnected = true;
      this.emit('connect');
      console.log('Device initialized successfully');
    } catch (error) {
      console.error('Failed to initialize device:', error);
      // Clean up on failure
      try {
        if (this.device) {
          await this.device.close();
          await new Promise(resolve => setTimeout(resolve, 100));
        }
      } catch (e) {
        console.error('Error during cleanup:', e);
      }
      this.status.isConnected = false;
      throw error;
    }
  }

  private parseRanges(data: Uint8Array): number[] {
    const ranges: number[] = [];
    for (let i = 0; i < data.length; i += 2) {
      ranges.push((data[i] << 8) | data[i + 1]);
    }
    return ranges;
  }

  async connectDevice(): Promise<void> {
    return this.withLock(async () => {
      try {
        // If we already have a connected device, disconnect it first
        if (this.device) {
          await this.disconnectDevice();
          await new Promise(resolve => setTimeout(resolve, 500)); // Wait after disconnecting
        }

        const device = await navigator.usb.requestDevice({
          filters: [
            { vendorId: this.vendorId, productId: this.productId }
          ]
        });

        // Store device info before initialization
        const deviceInfo = {
          vendorId: device.vendorId,
          productId: device.productId,
          manufacturerName: device.manufacturerName || 'Unknown',
          productName: device.productName || 'Unknown'
        };

        this.device = device;
        this.status.deviceInfo = deviceInfo;

        await this.initializeDevice();
      } catch (error) {
        this.status.lastError = error instanceof Error ? error.message : 'Unknown error';
        this.emit('error', this.status.lastError);
        throw error;
      }
    });
  }

  async disconnectDevice(): Promise<void> {
    return this.withLock(async () => {
      if (this.device) {
        try {
          if (this.status.isConnected) {
            try {
              await this.device.close();
              await new Promise(resolve => setTimeout(resolve, 100)); // Wait after closing
            } catch (e) {
              // Ignore close errors
            }
          }
        } finally {
          // Always clean up state even if close fails
          this.status.isConnected = false;
          this.status.ledStatus = 'off';
          this.status.deviceInfo = null;
          this.status.firmwareVersion = null;
          this.device = null;
          this.emit('disconnect');
        }
      }
    });
  }

  private async sendCommand(command: string, params: string = ''): Promise<DeviceResponse> {
    if (!this.device) {
      throw new Error('No device selected');
    }

    // Normalize command to uppercase and trim whitespace
    command = command.toUpperCase().trim();
    
    // Combine command and parameters
    const fullCommand = `${command}${params}`;
    
    console.log('Sending command:', fullCommand);
    
    // Convert command to bytes
    const encoder = new TextEncoder();
    const commandBytes = encoder.encode(fullCommand);
    
    console.log('Command bytes:', Array.from(commandBytes).map(b => b.toString(16).padStart(2, '0')).join(' '));
    
    // Add a delay before sending the command
    await new Promise(resolve => setTimeout(resolve, 100));
    
    try {
      // Send command to endpoint 1
      await this.device.transferOut(1, commandBytes);
      console.log('Command sent successfully');
      
      // Add a delay before reading the response
      await new Promise(resolve => setTimeout(resolve, 200));
      
      // Try to read from both endpoints
      let response: DeviceResponse | null = null;
      
      // Try endpoint 1 first
      try {
        const result = await this.device.transferIn(1, 64);
        if (result.data && result.data.byteLength > 0) {
          response = this.parseResponse(result.data);
          console.log('Response from endpoint 1:', response);
        }
      } catch (error) {
        console.log('Failed to read from endpoint 1:', error);
      }
      
      // If no response from endpoint 1, try endpoint 2
      if (!response) {
        try {
          const result = await this.device.transferIn(2, 64);
          if (result.data && result.data.byteLength > 0) {
            response = this.parseResponse(result.data);
            console.log('Response from endpoint 2:', response);
          }
        } catch (error) {
          console.log('Failed to read from endpoint 2:', error);
        }
      }
      
      if (!response) {
        throw new Error('No response received from device');
      }
      
      return response;
    } catch (error) {
      console.error('Error sending command:', error);
      throw error;
    }
  }

  private isTextResponse(data: DataView): boolean {
    // Check if the response is text (ASCII) or binary
    for (let i = 0; i < data.byteLength; i++) {
      const byte = data.getUint8(i);
      // Allow common control characters and printable ASCII
      if (byte !== 0x0A && byte !== 0x0D && byte !== 0x20 && (byte < 32 || byte > 126)) {
        return false;
      }
    }
    return true;
  }

  async readADC(): Promise<DeviceResponse> {
    return this.sendCommand(this.COMMANDS.READ_ADC);
  }

  async readLED(): Promise<DeviceResponse> {
    return this.sendCommand(this.COMMANDS.READ_LED);
  }

  async readCellState(): Promise<DeviceResponse> {
    return this.sendCommand(this.COMMANDS.READ_CELL_STATE);
  }

  async readMode(): Promise<DeviceResponse> {
    return this.sendCommand(this.COMMANDS.READ_MODE);
  }

  async readRanges(): Promise<DeviceResponse> {
    return this.sendCommand(this.COMMANDS.READ_RANGES);
  }

  async turnCellOn(): Promise<DeviceResponse> {
    return this.sendCommand(this.COMMANDS.TURN_CELL_ON);
  }

  async turnCellOff(): Promise<DeviceResponse> {
    return this.sendCommand(this.COMMANDS.TURN_CELL_OFF);
  }

  async setMode(mode: number): Promise<DeviceResponse> {
    return this.sendCommand(this.COMMANDS.SET_MODE, mode.toString());
  }

  getStatus(): DeviceStatus {
    return { ...this.status };
  }

  getConfig(): DeviceConfig {
    return { ...this.config };
  }

  on(event: string, callback: Function): void {
    if (!this.eventListeners.has(event)) {
      this.eventListeners.set(event, []);
    }
    this.eventListeners.get(event)?.push(callback);
  }

  off(event: string, callback: Function): void {
    const listeners = this.eventListeners.get(event);
    if (listeners) {
      const index = listeners.indexOf(callback);
      if (index !== -1) {
        listeners.splice(index, 1);
      }
    }
  }

  private emit(event: string, ...args: any[]): void {
    const listeners = this.eventListeners.get(event);
    if (listeners) {
      listeners.forEach(callback => callback(...args));
    }
  }

  // Convert decimal to DAC bytes (3 bytes)
  private decimalToDACBytes(value: number): Uint8Array {
    const bytes = new Uint8Array(3);
    bytes[0] = (value >> 16) & 0xFF;
    bytes[1] = (value >> 8) & 0xFF;
    bytes[2] = value & 0xFF;
    return bytes;
  }

  // Convert DAC bytes to decimal
  private dacBytesToDecimal(bytes: Uint8Array, startIndex: number = 0): number {
    return (bytes[startIndex] << 16) | (bytes[startIndex + 1] << 8) | bytes[startIndex + 2];
  }

  // Read DAC calibration values
  async readDACCalibration(): Promise<{ offset: number; gain: number }> {
    let offset = 0;
    let gain = 0;

    try {
      const response = await this.sendCommand(this.COMMANDS.READ_DAC_CAL);
      
      // Log the raw response for debugging
      console.log('Raw DAC calibration response:', {
        type: response.type,
        data: response.data
      });

      if (response.type === 'text') {
        const text = response.data as string;
        
        // Handle special case where device returns "?"
        if (text === '?') {
          console.warn('Device returned "?" for DAC calibration, using default values');
          return {
            offset: 0,
            gain: 524288 // 2^19 default
          };
        }

        // Try different text formats that might be returned
        const formats = [
          /offset:(\d+),gain:(\d+)/,
          /offset=(\d+),gain=(\d+)/,
          /offset:(\d+)\s*gain:(\d+)/,
          /offset=(\d+)\s*gain=(\d+)/
        ];

        for (const format of formats) {
          const match = text.match(format);
          if (match) {
            offset = parseInt(match[1], 10);
            gain = parseInt(match[2], 10);
            break;
          }
        }

        if (gain === 0) {
          console.warn(`Invalid text format: ${text}, using default values`);
          return {
            offset: 0,
            gain: 524288 // 2^19 default
          };
        }
      } else if (response.type === 'binary' && response.data instanceof Uint8Array) {
        const data = response.data;
        
        if (data.length < 6) {
          console.warn(`Invalid DAC calibration data length: ${data.length} bytes (expected 6), using default values`);
          return {
            offset: 0,
            gain: 524288 // 2^19 default
          };
        }

        offset = this.dacBytesToDecimal(data, 0);
        gain = this.dacBytesToDecimal(data, 3);
      } else {
        console.warn(`Unsupported response type: ${response.type}, using default values`);
        return {
          offset: 0,
          gain: 524288 // 2^19 default
        };
      }

      // Validate the values
      if (gain === 0) {
        console.warn('Invalid gain value: cannot be zero, using default values');
        return {
          offset: 0,
          gain: 524288 // 2^19 default
        };
      }

      // Log the parsed values for debugging
      console.log('Parsed DAC calibration:', {
        offset,
        gain
      });

      return { offset, gain };
    } catch (error) {
      console.error('DAC calibration read error:', error);
      // Return default values instead of throwing
      return {
        offset: 0,
        gain: 524288 // 2^19 default
      };
    }
  }

  // Set DAC calibration values
  async setDACCalibration(offset: number, gain: number): Promise<void> {
    // Format the command with parameters
    const params = `${offset} ${gain}`;
    await this.sendCommand(this.COMMANDS.SET_DAC_CAL, params);
  }

  // Convert raw ADC value to voltage using calibration
  convertToVoltage(raw: number, gain: number, offset: number): number {
    return (raw - offset) / gain;
  }

  async readPotentialCurrent(): Promise<DeviceResponse> {
    return this.withLock(async () => {
      try {
        // Check device state first
        if (!this.device || !this.status.isConnected) {
          console.warn('Device not connected, attempting to reconnect...');
          const isConnected = await this.checkDeviceConnection();
          if (!isConnected) {
            throw new Error('Device not connected');
          }
        }

        // Try to read cell state first to verify device is responsive
        const cellState = await this.readCellState();
        console.log('Cell state:', cellState);

        // Try to read mode to verify device is ready
        const modeResponse = await this.readMode();
        console.log('Mode:', modeResponse);

        // Now read ADC with uppercase command
        const response = await this.sendCommand("ADCREAD");
        console.log('ADC Response:', response); // Debug log
        
        if (response.type === 'text' && response.data === '?') {
          console.warn('Device returned "?" for ADC read, retrying once...');
          // Wait a bit and try again
          await new Promise(resolve => setTimeout(resolve, 100));
          const retryResponse = await this.sendCommand("ADCREAD");
          console.log('Retry ADC Response:', retryResponse);
          
          if (retryResponse.type === 'text' && retryResponse.data === '?') {
            console.warn('Device still returning "?" for ADC read, using default values');
            return {
              type: 'binary',
              data: new Float32Array([0, 0]), // Return zero values
              timestamp: Date.now()
            };
          }
          return retryResponse;
        }
        
        if (response.type === 'binary') {
          const data = response.data as Uint8Array;
          
          // Log raw data for debugging
          console.log('Raw ADC data:', Array.from(data).map(b => b.toString(16).padStart(2, '0')).join(' '));
          
          // First 3 bytes are potential (22-bit ADC)
          const potential = this.twocomplementToDecimal(data[0], data[1], data[2]);
          // Next 3 bytes are current (22-bit ADC)
          const current = this.twocomplementToDecimal(data[3], data[4], data[5]);
          
          console.log('Raw ADC values:', { potential, current }); // Debug log
          
          // Convert to actual values
          const dacCal = await this.readDACCalibration();
          const voltage = this.convertToVoltage(potential, dacCal.gain, dacCal.offset);
          const currentInmA = this.convertToVoltage(current, dacCal.gain, dacCal.offset) * 1000; // Convert to mA
          
          console.log('Converted values:', { voltage, currentInmA });
          
          // Create a Float32Array to properly store the floating-point values
          const resultData = new Float32Array([voltage, currentInmA]);
          
          return {
            type: 'binary',
            data: resultData,
            timestamp: Date.now()
          };
        }
        
        console.warn('Unexpected response type:', response.type);
        return {
          type: 'binary',
          data: new Float32Array([0, 0]), // Return zero values
          timestamp: Date.now()
        };
      } catch (error) {
        console.error('Failed to read potential and current:', error);
        this.status.lastError = error instanceof Error ? error.message : 'Failed to read potential and current';
        this.emit('error', this.status.lastError);
        throw error;
      }
    });
  }

  private twocomplementToDecimal(msb: number, middlebyte: number, lsb: number): number {
    const ovh = (msb > 63) && (msb < 128); // Check for overflow high (B22 set)
    const ovl = (msb > 127); // Check for overflow low (B23 set)
    const combinedValue = (msb % 64) * 2**16 + middlebyte * 2**8 + lsb; // Get rid of overflow bits
    
    if (!ovh && !ovl) {
      if (msb > 31) { // B21 set -> negative number
        return combinedValue - 2**22;
      }
      return combinedValue;
    } else { // overflow
      if (msb > 127) { // B23 set -> negative number
        return combinedValue - 2**22;
      }
      return combinedValue;
    }
  }

  private async resetDevice(): Promise<void> {
    if (this.device) {
      try {
        // Try to release any claimed interfaces
        try {
          await this.device.releaseInterface(0);
          console.log('Released interface 0');
        } catch (e) {
          console.log('No interface to release or release failed');
        }

        // Close the device
        try {
          await this.device.close();
          console.log('Device closed');
        } catch (e) {
          console.log('Device close failed');
        }

        // Wait a bit before reopening
        await new Promise(resolve => setTimeout(resolve, 1000));
      } catch (e) {
        console.error('Error during device reset:', e);
      }
    }
  }

  async disconnect(): Promise<void> {
    if (this.device) {
      await this.resetDevice();
      this.device = null;
      this.status.isConnected = false;
      this.emit('disconnect');
    }
  }

  async connect(device: USBDevice): Promise<void> {
    // If we already have a device, disconnect it first
    if (this.device) {
      await this.disconnect();
    }

    try {
      this.device = device;
      console.log('Attempting to connect to device:', {
        productName: device.productName,
        manufacturerName: device.manufacturerName,
        serialNumber: device.serialNumber
      });

      // Reset the device first
      await this.resetDevice();

      // Open the device
      await this.device.open();
      console.log('Device opened successfully');

      // Select configuration #1
      await this.device.selectConfiguration(1);
      console.log('Configuration 1 selected successfully');

      // Try to claim interface with retries
      let claimed = false;
      let attempts = 0;
      const maxAttempts = 3;

      while (!claimed && attempts < maxAttempts) {
        try {
          console.log(`Claiming interface 0 (attempt ${attempts + 1}/${maxAttempts})...`);
          await this.device.claimInterface(0);
          claimed = true;
          console.log('Interface claimed successfully');
        } catch (e) {
          attempts++;
          if (attempts < maxAttempts) {
            console.log(`Claim attempt failed, waiting before retry...`);
            await new Promise(resolve => setTimeout(resolve, 1000));
            // Try resetting before next attempt
            await this.resetDevice();
          } else {
            throw e;
          }
        }
      }

      this.status.isConnected = true;
      this.emit('connect', this.device);

      // Initialize the device
      await this.initializeDevice();
    } catch (error) {
      this.status.lastError = error instanceof Error ? error.message : 'Unknown error';
      console.error('Connection error:', this.status.lastError);
      this.emit('error', this.status.lastError);
      
      // Clean up if connection fails
      await this.disconnect();
      throw error;
    }
  }
}

export const usbService = new USBService(); 