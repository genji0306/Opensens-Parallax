import React, { useState } from 'react';
import styled from 'styled-components';

const MeasurementsContainer = styled.div`
  padding: 1rem;
  background-color: ${props => props.theme.background};
  border-radius: 8px;
  margin-bottom: 1rem;
`;

const MeasurementType = styled.div<{ active: boolean }>`
  padding: 1rem;
  border: 1px solid ${props => props.active ? props.theme.primary : props.theme.border};
  border-radius: 4px;
  margin-bottom: 1rem;
  cursor: pointer;
  background-color: ${props => props.active ? props.theme.hover : props.theme.background};
  transition: all 0.2s;

  &:hover {
    background-color: ${props => props.theme.hover};
  }
`;

const MeasurementSettings = styled.div`
  padding: 1rem;
  background-color: ${props => props.theme.background};
  border: 1px solid ${props => props.theme.border};
  border-radius: 4px;
  margin-top: 1rem;
`;

const InputGroup = styled.div`
  margin-bottom: 1rem;
`;

const Label = styled.label`
  display: block;
  margin-bottom: 0.5rem;
  color: ${props => props.theme.text};
`;

const Input = styled.input`
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

interface MeasurementSettings {
  startPotential: number;
  endPotential: number;
  scanRate: number;
  currentRange: string;
  duration: number;
  interval: number;
}

const Measurements: React.FC = () => {
  const [activeType, setActiveType] = useState<string | null>(null);
  const [settings, setSettings] = useState<MeasurementSettings>({
    startPotential: 0,
    endPotential: 1,
    scanRate: 0.1,
    currentRange: '1mA',
    duration: 60,
    interval: 0.1
  });

  const measurementTypes = [
    { id: 'cv', name: 'Cyclic Voltammetry (CV)' },
    { id: 'lsv', name: 'Linear Sweep Voltammetry (LSV)' },
    { id: 'ca', name: 'Chronoamperometry (CA)' },
    { id: 'cp', name: 'Chronopotentiometry (CP)' },
    { id: 'eis', name: 'Electrochemical Impedance Spectroscopy (EIS)' },
    { id: 'dpp', name: 'Differential Pulse Polarography (DPP)' },
    { id: 'swv', name: 'Square Wave Voltammetry (SWV)' },
    { id: 'acv', name: 'Alternating Current Voltammetry (ACV)' },
    { id: 'ocp', name: 'Open Circuit Potential (OCP)' },
    { id: 'ms', name: 'Multi-Step (MS)' }
  ];

  const handleSettingChange = (field: keyof MeasurementSettings, value: string | number) => {
    setSettings(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const renderSettings = () => {
    switch (activeType) {
      case 'cv':
        return (
          <>
            <InputGroup>
              <Label>Start Potential (V)</Label>
              <Input
                type="number"
                value={settings.startPotential}
                onChange={(e) => handleSettingChange('startPotential', parseFloat(e.target.value))}
              />
            </InputGroup>
            <InputGroup>
              <Label>End Potential (V)</Label>
              <Input
                type="number"
                value={settings.endPotential}
                onChange={(e) => handleSettingChange('endPotential', parseFloat(e.target.value))}
              />
            </InputGroup>
            <InputGroup>
              <Label>Scan Rate (V/s)</Label>
              <Input
                type="number"
                value={settings.scanRate}
                onChange={(e) => handleSettingChange('scanRate', parseFloat(e.target.value))}
              />
            </InputGroup>
          </>
        );
      case 'lsv':
        return (
          <>
            <InputGroup>
              <Label>Start Potential (V)</Label>
              <Input
                type="number"
                value={settings.startPotential}
                onChange={(e) => handleSettingChange('startPotential', parseFloat(e.target.value))}
              />
            </InputGroup>
            <InputGroup>
              <Label>End Potential (V)</Label>
              <Input
                type="number"
                value={settings.endPotential}
                onChange={(e) => handleSettingChange('endPotential', parseFloat(e.target.value))}
              />
            </InputGroup>
            <InputGroup>
              <Label>Scan Rate (V/s)</Label>
              <Input
                type="number"
                value={settings.scanRate}
                onChange={(e) => handleSettingChange('scanRate', parseFloat(e.target.value))}
              />
            </InputGroup>
          </>
        );
      case 'ca':
        return (
          <>
            <InputGroup>
              <Label>Potential (V)</Label>
              <Input
                type="number"
                value={settings.startPotential}
                onChange={(e) => handleSettingChange('startPotential', parseFloat(e.target.value))}
              />
            </InputGroup>
            <InputGroup>
              <Label>Duration (s)</Label>
              <Input
                type="number"
                value={settings.duration}
                onChange={(e) => handleSettingChange('duration', parseFloat(e.target.value))}
              />
            </InputGroup>
            <InputGroup>
              <Label>Interval (s)</Label>
              <Input
                type="number"
                value={settings.interval}
                onChange={(e) => handleSettingChange('interval', parseFloat(e.target.value))}
              />
            </InputGroup>
          </>
        );
      case 'cp':
        return (
          <>
            <InputGroup>
              <Label>Current (mA)</Label>
              <Input
                type="number"
                value={settings.startPotential}
                onChange={(e) => handleSettingChange('startPotential', parseFloat(e.target.value))}
              />
            </InputGroup>
            <InputGroup>
              <Label>Duration (s)</Label>
              <Input
                type="number"
                value={settings.duration}
                onChange={(e) => handleSettingChange('duration', parseFloat(e.target.value))}
              />
            </InputGroup>
            <InputGroup>
              <Label>Interval (s)</Label>
              <Input
                type="number"
                value={settings.interval}
                onChange={(e) => handleSettingChange('interval', parseFloat(e.target.value))}
              />
            </InputGroup>
          </>
        );
      case 'eis':
        return (
          <>
            <InputGroup>
              <Label>Start Frequency (Hz)</Label>
              <Input
                type="number"
                value={settings.startPotential}
                onChange={(e) => handleSettingChange('startPotential', parseFloat(e.target.value))}
              />
            </InputGroup>
            <InputGroup>
              <Label>End Frequency (Hz)</Label>
              <Input
                type="number"
                value={settings.endPotential}
                onChange={(e) => handleSettingChange('endPotential', parseFloat(e.target.value))}
              />
            </InputGroup>
            <InputGroup>
              <Label>AC Amplitude (mV)</Label>
              <Input
                type="number"
                value={settings.scanRate}
                onChange={(e) => handleSettingChange('scanRate', parseFloat(e.target.value))}
              />
            </InputGroup>
          </>
        );
      case 'dpp':
        return (
          <>
            <InputGroup>
              <Label>Start Potential (V)</Label>
              <Input
                type="number"
                value={settings.startPotential}
                onChange={(e) => handleSettingChange('startPotential', parseFloat(e.target.value))}
              />
            </InputGroup>
            <InputGroup>
              <Label>End Potential (V)</Label>
              <Input
                type="number"
                value={settings.endPotential}
                onChange={(e) => handleSettingChange('endPotential', parseFloat(e.target.value))}
              />
            </InputGroup>
            <InputGroup>
              <Label>Pulse Amplitude (V)</Label>
              <Input
                type="number"
                value={settings.scanRate}
                onChange={(e) => handleSettingChange('scanRate', parseFloat(e.target.value))}
              />
            </InputGroup>
            <InputGroup>
              <Label>Pulse Duration (ms)</Label>
              <Input
                type="number"
                value={settings.interval}
                onChange={(e) => handleSettingChange('interval', parseFloat(e.target.value))}
              />
            </InputGroup>
          </>
        );
      case 'swv':
        return (
          <>
            <InputGroup>
              <Label>Start Potential (V)</Label>
              <Input
                type="number"
                value={settings.startPotential}
                onChange={(e) => handleSettingChange('startPotential', parseFloat(e.target.value))}
              />
            </InputGroup>
            <InputGroup>
              <Label>End Potential (V)</Label>
              <Input
                type="number"
                value={settings.endPotential}
                onChange={(e) => handleSettingChange('endPotential', parseFloat(e.target.value))}
              />
            </InputGroup>
            <InputGroup>
              <Label>Square Wave Amplitude (V)</Label>
              <Input
                type="number"
                value={settings.scanRate}
                onChange={(e) => handleSettingChange('scanRate', parseFloat(e.target.value))}
              />
            </InputGroup>
            <InputGroup>
              <Label>Frequency (Hz)</Label>
              <Input
                type="number"
                value={settings.interval}
                onChange={(e) => handleSettingChange('interval', parseFloat(e.target.value))}
              />
            </InputGroup>
          </>
        );
      case 'acv':
        return (
          <>
            <InputGroup>
              <Label>Start Potential (V)</Label>
              <Input
                type="number"
                value={settings.startPotential}
                onChange={(e) => handleSettingChange('startPotential', parseFloat(e.target.value))}
              />
            </InputGroup>
            <InputGroup>
              <Label>End Potential (V)</Label>
              <Input
                type="number"
                value={settings.endPotential}
                onChange={(e) => handleSettingChange('endPotential', parseFloat(e.target.value))}
              />
            </InputGroup>
            <InputGroup>
              <Label>AC Amplitude (V)</Label>
              <Input
                type="number"
                value={settings.scanRate}
                onChange={(e) => handleSettingChange('scanRate', parseFloat(e.target.value))}
              />
            </InputGroup>
            <InputGroup>
              <Label>AC Frequency (Hz)</Label>
              <Input
                type="number"
                value={settings.interval}
                onChange={(e) => handleSettingChange('interval', parseFloat(e.target.value))}
              />
            </InputGroup>
          </>
        );
      case 'ocp':
        return (
          <>
            <InputGroup>
              <Label>Duration (s)</Label>
              <Input
                type="number"
                value={settings.duration}
                onChange={(e) => handleSettingChange('duration', parseFloat(e.target.value))}
              />
            </InputGroup>
            <InputGroup>
              <Label>Interval (s)</Label>
              <Input
                type="number"
                value={settings.interval}
                onChange={(e) => handleSettingChange('interval', parseFloat(e.target.value))}
              />
            </InputGroup>
          </>
        );
      case 'ms':
        return (
          <>
            <InputGroup>
              <Label>Number of Steps</Label>
              <Input
                type="number"
                value={settings.duration}
                onChange={(e) => handleSettingChange('duration', parseInt(e.target.value))}
              />
            </InputGroup>
            <InputGroup>
              <Label>Step Duration (s)</Label>
              <Input
                type="number"
                value={settings.interval}
                onChange={(e) => handleSettingChange('interval', parseFloat(e.target.value))}
              />
            </InputGroup>
            <InputGroup>
              <Label>Step Potential (V)</Label>
              <Input
                type="number"
                value={settings.scanRate}
                onChange={(e) => handleSettingChange('scanRate', parseFloat(e.target.value))}
              />
            </InputGroup>
          </>
        );
      default:
        return null;
    }
  };

  return (
    <MeasurementsContainer>
      <h2>Measurements</h2>
      {measurementTypes.map(type => (
        <MeasurementType
          key={type.id}
          active={activeType === type.id}
          onClick={() => setActiveType(type.id)}
        >
          <h3>{type.name}</h3>
          {activeType === type.id && (
            <MeasurementSettings>
              {renderSettings()}
              <InputGroup>
                <Label>Current Range</Label>
                <select
                  value={settings.currentRange}
                  onChange={(e) => handleSettingChange('currentRange', e.target.value)}
                >
                  <option value="1mA">1 mA</option>
                  <option value="100uA">100 µA</option>
                  <option value="10uA">10 µA</option>
                  <option value="1uA">1 µA</option>
                </select>
              </InputGroup>
              <Button>Start Measurement</Button>
            </MeasurementSettings>
          )}
        </MeasurementType>
      ))}
    </MeasurementsContainer>
  );
};

export default Measurements; 