import React, { useState } from 'react';
import styled from 'styled-components';

const SettingsContainer = styled.div`
  padding: 1rem;
  background-color: ${props => props.theme.background};
  border: 1px solid ${props => props.theme.border};
  border-radius: 4px;
`;

const SettingsGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1rem;
`;

const SettingsCard = styled.div`
  padding: 1rem;
  background-color: ${props => props.theme.background};
  border: 1px solid ${props => props.theme.border};
  border-radius: 4px;
`;

const CardTitle = styled.h3`
  margin-bottom: 1rem;
  color: ${props => props.theme.text};
`;

const InputGroup = styled.div`
  margin-bottom: 1rem;

  &:last-child {
    margin-bottom: 0;
  }
`;

const Label = styled.label`
  display: block;
  margin-bottom: 0.5rem;
  color: ${props => props.theme.text};
  font-size: 0.875rem;
`;

const Input = styled.input`
  width: 100%;
  padding: 0.5rem;
  border: 1px solid ${props => props.theme.border};
  border-radius: 4px;
  background-color: ${props => props.theme.background};
  color: ${props => props.theme.text};
`;

const Select = styled.select`
  width: 100%;
  padding: 0.5rem;
  border: 1px solid ${props => props.theme.border};
  border-radius: 4px;
  background-color: ${props => props.theme.background};
  color: ${props => props.theme.text};
`;

const Button = styled.button`
  padding: 0.5rem 1rem;
  background-color: ${props => props.theme.primary};
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  margin-top: 1rem;

  &:hover {
    opacity: 0.9;
  }
`;

const Settings: React.FC = () => {
  const [deviceSettings, setDeviceSettings] = useState({
    voltageOffset: 0,
    currentOffset: 0,
    voltageGain: 1,
    currentGain: 1,
    overCurrentProtection: true,
    overVoltageProtection: true,
    maxCurrent: 1,
    maxVoltage: 5,
    dataLogging: true,
    logInterval: 1,
    electrodeType: 'standard',
    temperature: 25,
    humidity: 50
  });

  const handleSettingChange = (key: string, value: any) => {
    setDeviceSettings(prev => ({
      ...prev,
      [key]: value
    }));
  };

  const handleSave = () => {
    // TODO: Implement settings save
    console.log('Saving settings:', deviceSettings);
  };

  return (
    <SettingsContainer>
      <SettingsGrid>
        <SettingsCard>
          <CardTitle>Power Settings</CardTitle>
          <InputGroup>
            <Label>Voltage Offset (V):</Label>
            <Input
              type="number"
              value={deviceSettings.voltageOffset}
              onChange={(e) => handleSettingChange('voltageOffset', parseFloat(e.target.value))}
              step="0.001"
            />
          </InputGroup>
          <InputGroup>
            <Label>Current Offset (A):</Label>
            <Input
              type="number"
              value={deviceSettings.currentOffset}
              onChange={(e) => handleSettingChange('currentOffset', parseFloat(e.target.value))}
              step="0.000001"
            />
          </InputGroup>
          <InputGroup>
            <Label>Voltage Gain:</Label>
            <Input
              type="number"
              value={deviceSettings.voltageGain}
              onChange={(e) => handleSettingChange('voltageGain', parseFloat(e.target.value))}
              step="0.001"
            />
          </InputGroup>
          <InputGroup>
            <Label>Current Gain:</Label>
            <Input
              type="number"
              value={deviceSettings.currentGain}
              onChange={(e) => handleSettingChange('currentGain', parseFloat(e.target.value))}
              step="0.001"
            />
          </InputGroup>
        </SettingsCard>

        <SettingsCard>
          <CardTitle>Protection Settings</CardTitle>
          <InputGroup>
            <Label>Over Current Protection:</Label>
            <Select
              value={deviceSettings.overCurrentProtection ? 'enabled' : 'disabled'}
              onChange={(e) => handleSettingChange('overCurrentProtection', e.target.value === 'enabled')}
            >
              <option value="enabled">Enabled</option>
              <option value="disabled">Disabled</option>
            </Select>
          </InputGroup>
          <InputGroup>
            <Label>Over Voltage Protection:</Label>
            <Select
              value={deviceSettings.overVoltageProtection ? 'enabled' : 'disabled'}
              onChange={(e) => handleSettingChange('overVoltageProtection', e.target.value === 'enabled')}
            >
              <option value="enabled">Enabled</option>
              <option value="disabled">Disabled</option>
            </Select>
          </InputGroup>
          <InputGroup>
            <Label>Max Current (A):</Label>
            <Input
              type="number"
              value={deviceSettings.maxCurrent}
              onChange={(e) => handleSettingChange('maxCurrent', parseFloat(e.target.value))}
              step="0.1"
            />
          </InputGroup>
          <InputGroup>
            <Label>Max Voltage (V):</Label>
            <Input
              type="number"
              value={deviceSettings.maxVoltage}
              onChange={(e) => handleSettingChange('maxVoltage', parseFloat(e.target.value))}
              step="0.1"
            />
          </InputGroup>
        </SettingsCard>

        <SettingsCard>
          <CardTitle>Data Settings</CardTitle>
          <InputGroup>
            <Label>Data Logging:</Label>
            <Select
              value={deviceSettings.dataLogging ? 'enabled' : 'disabled'}
              onChange={(e) => handleSettingChange('dataLogging', e.target.value === 'enabled')}
            >
              <option value="enabled">Enabled</option>
              <option value="disabled">Disabled</option>
            </Select>
          </InputGroup>
          <InputGroup>
            <Label>Log Interval (s):</Label>
            <Input
              type="number"
              value={deviceSettings.logInterval}
              onChange={(e) => handleSettingChange('logInterval', parseFloat(e.target.value))}
              step="0.1"
            />
          </InputGroup>
        </SettingsCard>

        <SettingsCard>
          <CardTitle>Environmental Settings</CardTitle>
          <InputGroup>
            <Label>Electrode Type:</Label>
            <Select
              value={deviceSettings.electrodeType}
              onChange={(e) => handleSettingChange('electrodeType', e.target.value)}
            >
              <option value="standard">Standard</option>
              <option value="reference">Reference</option>
              <option value="working">Working</option>
            </Select>
          </InputGroup>
          <InputGroup>
            <Label>Temperature (°C):</Label>
            <Input
              type="number"
              value={deviceSettings.temperature}
              onChange={(e) => handleSettingChange('temperature', parseFloat(e.target.value))}
              step="0.1"
            />
          </InputGroup>
          <InputGroup>
            <Label>Humidity (%):</Label>
            <Input
              type="number"
              value={deviceSettings.humidity}
              onChange={(e) => handleSettingChange('humidity', parseFloat(e.target.value))}
              step="0.1"
            />
          </InputGroup>
        </SettingsCard>
      </SettingsGrid>
      <Button onClick={handleSave}>Save Settings</Button>
    </SettingsContainer>
  );
};

export default Settings; 