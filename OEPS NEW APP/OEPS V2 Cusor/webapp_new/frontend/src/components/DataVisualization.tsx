import React, { useState } from 'react';
import styled from 'styled-components';
import { Theme } from '../theme';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  ChartData,
  ChartOptions
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import { exportData } from '../utils/exportData';
import { Measurement } from '../types';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

const Container = styled.div<{ theme: Theme }>`
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 1rem;
  padding: 1rem;
  height: calc(100vh - 120px);
  overflow: hidden;
`;

const ChartCard = styled.div<{ theme: Theme }>`
  background-color: ${props => props.theme.background};
  border: 1px solid ${props => props.theme.border};
  border-radius: 4px;
  padding: 1rem;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
`;

const MeasurementsCard = styled.div<{ theme: Theme }>`
  background-color: ${props => props.theme.background};
  border: 1px solid ${props => props.theme.border};
  border-radius: 4px;
  padding: 1rem;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
`;

const CardTitle = styled.h2<{ theme: Theme }>`
  margin: 0 0 1rem 0;
  font-size: 1.25rem;
  color: ${props => props.theme.text};
`;

const SubTitle = styled.h3<{ theme: Theme }>`
  margin: 1rem 0;
  font-size: 1rem;
  color: ${props => props.theme.text};
`;

const Controls = styled.div<{ theme: Theme }>`
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
  margin-bottom: 1rem;
`;

const TopControls = styled.div<{ theme: Theme }>`
  display: flex;
  gap: 1rem;
  margin-bottom: 1rem;
  justify-content: flex-end;
`;

const Button = styled.button<{ active?: boolean; theme: Theme }>`
  padding: 0.5rem 1rem;
  background-color: ${props => props.active ? props.theme.primary : props.theme.background};
  color: ${props => props.active ? 'white' : props.theme.text};
  border: 1px solid ${props => props.theme.border};
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;

  &:hover {
    background-color: ${props => props.theme.hover};
  }
`;

const MeasurementButton = styled(Button)`
  width: 100%;
  height: 100px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 1rem;
  font-size: 0.9rem;
  white-space: normal;
  word-wrap: break-word;
`;

const ExportMenu = styled.div<{ theme: Theme }>`
  position: relative;
  display: inline-block;
`;

const ExportDropdown = styled.div<{ theme: Theme }>`
  position: absolute;
  top: 100%;
  right: 0;
  background-color: ${props => props.theme.background};
  border: 1px solid ${props => props.theme.border};
  border-radius: 4px;
  padding: 0.5rem;
  z-index: 1000;
  min-width: 150px;
`;

const ExportOption = styled.button<{ theme: Theme }>`
  display: block;
  width: 100%;
  padding: 0.5rem;
  text-align: left;
  background: none;
  border: none;
  color: ${props => props.theme.text};
  cursor: pointer;
  border-radius: 4px;

  &:hover {
    background-color: ${props => props.theme.hover};
  }
`;

const SettingsBox = styled.div<{ theme: Theme }>`
  background-color: ${props => props.theme.background};
  border: 1px solid ${props => props.theme.border};
  border-radius: 4px;
  padding: 1rem;
  margin-top: 1rem;
`;

const InputGroup = styled.div<{ theme: Theme }>`
  margin-bottom: 1rem;
`;

const Label = styled.label<{ theme: Theme }>`
  display: block;
  margin-bottom: 0.5rem;
  color: ${props => props.theme.text};
`;

const Input = styled.input<{ theme: Theme }>`
  width: 100%;
  padding: 0.5rem;
  border: 1px solid ${props => props.theme.border};
  border-radius: 4px;
  background-color: ${props => props.theme.background};
  color: ${props => props.theme.text};
`;

const Select = styled.select<{ theme: Theme }>`
  width: 100%;
  padding: 0.5rem;
  border: 1px solid ${props => props.theme.border};
  border-radius: 4px;
  background-color: ${props => props.theme.background};
  color: ${props => props.theme.text};
`;

interface ChartStyle {
  lineColor: string;
  backgroundColor: string;
  lineWidth: number;
  lineStyle: 'solid' | 'dashed' | 'dotted';
  pointStyle: 'circle' | 'square' | 'triangle' | 'cross';
  pointSize: number;
  tension: number;
}

const ChartStylePanel = styled.div<{ theme: Theme }>`
  position: absolute;
  top: 100%;
  right: 0;
  background-color: ${props => props.theme.background};
  border: 1px solid ${props => props.theme.border};
  border-radius: 4px;
  padding: 1rem;
  z-index: 1000;
  min-width: 250px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
`;

interface DataVisualizationProps {
  data: Measurement[];
}

const DataVisualization: React.FC<DataVisualizationProps> = ({ data }) => {
  const [activeCharts, setActiveCharts] = useState<string[]>(['cv']);
  const [showExportMenu, setShowExportMenu] = useState(false);
  const [showChartStyle, setShowChartStyle] = useState(false);
  const [activeType, setActiveType] = useState<'cv' | 'lsv' | 'ca' | 'cp' | 'eis' | 'dpp' | 'swv' | 'acv' | 'ocp' | 'ms' | null>(null);
  const [settings, setSettings] = useState({
    startPotential: 0,
    endPotential: 1,
    scanRate: 0.1,
    currentRange: '1mA',
    duration: 60,
    interval: 0.1
  });
  const [chartStyle, setChartStyle] = useState<ChartStyle>({
    lineColor: '#4dabf7',
    backgroundColor: 'rgba(77, 171, 247, 0.1)',
    lineWidth: 2,
    lineStyle: 'solid',
    pointStyle: 'circle',
    pointSize: 4,
    tension: 0.4
  });

  const chartTypes = [
    { id: 'cv', label: 'Cyclic Voltammetry' },
    { id: 'lsv', label: 'Linear Sweep' },
    { id: 'ca', label: 'Chronoamperometry' },
    { id: 'cp', label: 'Chronopotentiometry' },
    { id: 'eis', label: 'EIS' },
    { id: 'dpp', label: 'Differential Pulse' },
    { id: 'swv', label: 'Square Wave' },
    { id: 'acv', label: 'AC Voltammetry' },
    { id: 'ocp', label: 'Open Circuit' },
    { id: 'ms', label: 'Multi-Step' }
  ];

  const handleSettingChange = (key: string, value: string | number) => {
    setSettings(prev => ({
      ...prev,
      [key]: value
    }));
  };

  const handleStyleChange = (key: keyof ChartStyle, value: string | number) => {
    setChartStyle(prev => ({
      ...prev,
      [key]: value
    }));
  };

  const renderSettings = () => {
    switch (activeType) {
      case 'cv':
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
      case 'cp':
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
      default:
        return null;
    }
  };

  const handleExport = async (format: 'csv' | 'json' | 'excel') => {
    try {
      await exportData(data, {
        format,
        includeMetadata: true,
        filename: `measurement_data_${new Date().toISOString()}`
      });
    } catch (error) {
      console.error('Export failed:', error);
    }
    setShowExportMenu(false);
  };

  const filteredData = data.filter(d => activeCharts.includes(d.type));

  const chartData: ChartData<'line'> = {
    labels: data.map(d => new Date(d.time).toLocaleTimeString()),
    datasets: [
      {
        label: 'Measurement',
        data: data.map(d => d.value),
        borderColor: '#4dabf7',
        backgroundColor: 'rgba(77, 171, 247, 0.1)',
        tension: 0.4,
        fill: true
      }
    ]
  };

  const options: ChartOptions<'line'> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top' as const,
        labels: {
          color: '#333333'
        }
      },
      title: {
        display: true,
        text: 'Measurement Data',
        color: '#333333'
      }
    },
    scales: {
      x: {
        grid: {
          color: '#e0e0e0'
        },
        ticks: {
          color: '#333333'
        }
      },
      y: {
        grid: {
          color: '#e0e0e0'
        },
        ticks: {
          color: '#333333'
        }
      }
    }
  };

  return (
    <Container>
      <ChartCard>
        <CardTitle>Data Visualization</CardTitle>
        <TopControls>
          <div style={{ position: 'relative' }}>
            <Button onClick={() => setShowChartStyle(!showChartStyle)}>
              Chart Style
            </Button>
            {showChartStyle && (
              <ChartStylePanel>
                <InputGroup>
                  <Label>Line Color</Label>
                  <Input
                    type="color"
                    value={chartStyle.lineColor}
                    onChange={(e) => handleStyleChange('lineColor', e.target.value)}
                  />
                </InputGroup>
                <InputGroup>
                  <Label>Background Color</Label>
                  <Input
                    type="color"
                    value={chartStyle.backgroundColor}
                    onChange={(e) => handleStyleChange('backgroundColor', e.target.value)}
                  />
                </InputGroup>
                <InputGroup>
                  <Label>Line Width</Label>
                  <Input
                    type="range"
                    min="1"
                    max="10"
                    value={chartStyle.lineWidth}
                    onChange={(e) => handleStyleChange('lineWidth', parseInt(e.target.value))}
                  />
                </InputGroup>
                <InputGroup>
                  <Label>Line Style</Label>
                  <Select
                    value={chartStyle.lineStyle}
                    onChange={(e) => handleStyleChange('lineStyle', e.target.value as 'solid' | 'dashed' | 'dotted')}
                  >
                    <option value="solid">Solid</option>
                    <option value="dashed">Dashed</option>
                    <option value="dotted">Dotted</option>
                  </Select>
                </InputGroup>
                <InputGroup>
                  <Label>Point Style</Label>
                  <Select
                    value={chartStyle.pointStyle}
                    onChange={(e) => handleStyleChange('pointStyle', e.target.value as 'circle' | 'square' | 'triangle' | 'cross')}
                  >
                    <option value="circle">Circle</option>
                    <option value="square">Square</option>
                    <option value="triangle">Triangle</option>
                    <option value="cross">Cross</option>
                  </Select>
                </InputGroup>
                <InputGroup>
                  <Label>Point Size</Label>
                  <Input
                    type="range"
                    min="1"
                    max="10"
                    value={chartStyle.pointSize}
                    onChange={(e) => handleStyleChange('pointSize', parseInt(e.target.value))}
                  />
                </InputGroup>
                <InputGroup>
                  <Label>Line Tension</Label>
                  <Input
                    type="range"
                    min="0"
                    max="1"
                    step="0.1"
                    value={chartStyle.tension}
                    onChange={(e) => handleStyleChange('tension', parseFloat(e.target.value))}
                  />
                </InputGroup>
              </ChartStylePanel>
            )}
          </div>
          <ExportMenu>
            <Button onClick={() => setShowExportMenu(!showExportMenu)}>
              Export
            </Button>
            {showExportMenu && (
              <ExportDropdown>
                <ExportOption onClick={() => handleExport('csv')}>
                  Export as CSV
                </ExportOption>
                <ExportOption onClick={() => handleExport('json')}>
                  Export as JSON
                </ExportOption>
                <ExportOption onClick={() => handleExport('excel')}>
                  Export as Excel
                </ExportOption>
              </ExportDropdown>
            )}
          </ExportMenu>
        </TopControls>
        <Line data={chartData} options={options} />
      </ChartCard>
      <MeasurementsCard>
        <CardTitle>Measurement Types</CardTitle>
        <Controls>
          {chartTypes.map(({ id, label }) => (
            <MeasurementButton
              key={id}
              active={activeType === id}
              onClick={() => {
                setActiveType(id as 'cv' | 'lsv' | 'ca' | 'cp' | 'eis' | 'dpp' | 'swv' | 'acv' | 'ocp' | 'ms');
                if (!activeCharts.includes(id)) {
                  setActiveCharts([...activeCharts, id]);
                }
              }}
            >
              {label}
            </MeasurementButton>
          ))}
        </Controls>
        {activeType && (
          <SettingsBox>
            <SubTitle>Measurement Settings</SubTitle>
            {renderSettings()}
            <InputGroup>
              <Label>Current Range</Label>
              <Select
                value={settings.currentRange}
                onChange={(e) => handleSettingChange('currentRange', e.target.value)}
              >
                <option value="1mA">1 mA</option>
                <option value="100uA">100 µA</option>
                <option value="10uA">10 µA</option>
                <option value="1uA">1 µA</option>
              </Select>
            </InputGroup>
            <Button 
              style={{ 
                width: '100%',
                marginTop: '1rem',
                backgroundColor: '#4dabf7',
                color: 'white'
              }}
            >
              Start Measurement
            </Button>
          </SettingsBox>
        )}
      </MeasurementsCard>
    </Container>
  );
};

export default DataVisualization; 