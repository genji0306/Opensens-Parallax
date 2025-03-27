import React, { useState } from 'react';
import styled from 'styled-components';
import { Theme } from '../theme';

const ConnectionContainer = styled.div<{ theme: Theme }>`
  padding: 1rem;
  margin-bottom: 1rem;
  background-color: ${props => props.theme.background};
  border: 1px solid ${props => props.theme.border};
  border-radius: 4px;
  display: flex;
  flex-direction: column;
  gap: 1rem;
`;

const ConnectionRow = styled.div<{ theme: Theme }>`
  display: flex;
  align-items: center;
  gap: 1rem;
`;

const Status = styled.div<{ connected: boolean; theme: Theme }>`
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: ${props => props.connected ? props.theme.success : props.theme.text};
`;

const StatusDot = styled.div<{ connected: boolean; theme: Theme }>`
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: ${props => props.connected ? props.theme.success : props.theme.error};
`;

const ButtonGroup = styled.div<{ theme: Theme }>`
  display: flex;
  gap: 1rem;
  margin-left: auto;
`;

const Button = styled.button<{ variant?: 'primary' | 'secondary'; theme: Theme }>`
  padding: 0.5rem 1rem;
  background-color: ${props => props.variant === 'secondary' ? props.theme.background : props.theme.primary};
  color: ${props => props.variant === 'secondary' ? props.theme.text : 'white'};
  border: 1px solid ${props => props.variant === 'secondary' ? props.theme.border : 'transparent'};
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;

  &:hover {
    opacity: 0.9;
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`;

const InputGroup = styled.div<{ theme: Theme }>`
  display: flex;
  align-items: center;
  gap: 1rem;
`;

const Label = styled.label<{ theme: Theme }>`
  color: ${props => props.theme.text};
  min-width: 80px;
`;

const Input = styled.input<{ theme: Theme }>`
  padding: 0.5rem;
  border: 1px solid ${props => props.theme.border};
  border-radius: 4px;
  background-color: ${props => props.theme.background};
  color: ${props => props.theme.text};
  width: 120px;
`;

interface DeviceStatus {
  connected: boolean;
  name: string;
  battery: number;
  temperature: number;
}

interface DeviceConnectionProps {
  onConnect: (device: DeviceStatus) => void;
  onCalibrate?: () => Promise<void>;
}

const DeviceConnection: React.FC<DeviceConnectionProps> = ({ onConnect, onCalibrate }) => {
  const [isConnected, setIsConnected] = useState(false);
  const [isCalibrating, setIsCalibrating] = useState(false);
  const [deviceVID, setDeviceVID] = useState('');
  const [devicePID, setDevicePID] = useState('');

  const handleConnect = () => {
    if (!deviceVID || !devicePID) {
      alert('Please enter both VID and PID values');
      return;
    }
    const newConnectionState = !isConnected;
    setIsConnected(newConnectionState);
    onConnect({
      connected: newConnectionState,
      name: 'Test Device',
      battery: 85,
      temperature: 25
    });
  };

  const handleCalibrate = async () => {
    if (!isConnected) return;
    setIsCalibrating(true);
    try {
      await onCalibrate?.();
    } finally {
      setIsCalibrating(false);
    }
  };

  return (
    <ConnectionContainer>
      <ConnectionRow>
        <Status connected={isConnected}>
          <StatusDot connected={isConnected} />
          {isConnected ? 'Connected' : 'Disconnected'}
        </Status>
        <InputGroup>
          <Label>VID:</Label>
          <Input
            type="text"
            value={deviceVID}
            onChange={(e) => setDeviceVID(e.target.value)}
            placeholder="0x0483"
            disabled={isConnected}
          />
        </InputGroup>
        <InputGroup>
          <Label>PID:</Label>
          <Input
            type="text"
            value={devicePID}
            onChange={(e) => setDevicePID(e.target.value)}
            placeholder="0x5740"
            disabled={isConnected}
          />
        </InputGroup>
        <ButtonGroup>
          <Button 
            variant="secondary"
            onClick={handleCalibrate}
            disabled={!isConnected || isCalibrating}
          >
            {isCalibrating ? 'Calibrating...' : 'Calibrate Device'}
          </Button>
          <Button onClick={handleConnect}>
            {isConnected ? 'Disconnect' : 'Connect Device'}
          </Button>
        </ButtonGroup>
      </ConnectionRow>
    </ConnectionContainer>
  );
};

export default DeviceConnection; 