import React from 'react';
import styled from 'styled-components';
import { DeviceInfo } from '../types';

const StatusContainer = styled.div`
  background-color: ${props => props.theme.background};
  border-top: 1px solid ${props => props.theme.border};
  padding: 1rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
`;

const StatusText = styled.div`
  color: ${props => props.theme.text};
`;

interface StatusBarProps {
  deviceInfo: DeviceInfo | null;
}

const StatusBar: React.FC<StatusBarProps> = ({ deviceInfo }) => {
  return (
    <StatusContainer>
      <StatusText>
        {deviceInfo ? (
          <>
            Connected to: {deviceInfo.manufacturer} {deviceInfo.product}
            <br />
            VID: {deviceInfo.vid} | PID: {deviceInfo.pid}
          </>
        ) : (
          'No device connected'
        )}
      </StatusText>
      <StatusText>
        Mode: {deviceInfo?.control_mode || 'N/A'} | 
        Range: {deviceInfo?.current_range || 'N/A'} | 
        Cell: {deviceInfo?.cell_connected ? 'Connected' : 'Disconnected'}
      </StatusText>
    </StatusContainer>
  );
};

export default StatusBar; 