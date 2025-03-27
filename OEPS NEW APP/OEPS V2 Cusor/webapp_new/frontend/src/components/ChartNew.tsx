import React, { useEffect, useRef, useCallback, useState } from 'react';
import styled from 'styled-components';
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
import { Measurement } from '../types';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

const ChartContainer = styled.div`
  width: 100%;
  height: 400px;
  background-color: ${props => props.theme.background};
  border: 1px solid ${props => props.theme.border};
  border-radius: 4px;
  margin-bottom: 1rem;
  position: relative;
`;

const ChartTitle = styled.h3`
  margin: 0;
  padding: 1rem;
  color: ${props => props.theme.text};
  border-bottom: 1px solid ${props => props.theme.border};
  font-size: 1.25rem;
  font-weight: 500;
  display: flex;
  justify-content: space-between;
  align-items: center;
`;

const CustomizeButton = styled.button`
  padding: 0.5rem 1rem;
  background-color: ${props => props.theme.background};
  border: 1px solid ${props => props.theme.border};
  border-radius: 4px;
  color: ${props => props.theme.text};
  cursor: pointer;
  font-size: 0.875rem;
  transition: all 0.2s ease;

  &:hover {
    background-color: ${props => props.theme.hover};
  }
`;

const CustomizationPanel = styled.div<{ isOpen: boolean }>`
  position: absolute;
  top: 100%;
  right: 0;
  width: 300px;
  background-color: ${props => props.theme.background};
  border: 1px solid ${props => props.theme.border};
  border-radius: 4px;
  padding: 1rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  z-index: 100;
  display: ${props => props.isOpen ? 'block' : 'none'};
`;

const CustomizationGroup = styled.div`
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

const ColorInput = styled.input`
  width: 100%;
  padding: 0.25rem;
  border: 1px solid ${props => props.theme.border};
  border-radius: 4px;
`;

const RangeInput = styled.input`
  width: 100%;
  margin: 0.5rem 0;
`;

const Select = styled.select`
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

interface ChartProps {
  data: Measurement[];
  type: 'cv' | 'lsv' | 'ca' | 'cp' | 'eis' | 'dpp' | 'swv' | 'acv' | 'ocp' | 'ms';
}

const useChart = (canvasRef: React.RefObject<HTMLCanvasElement>, data: Measurement[], type: string, style: ChartStyle) => {
  const chartInstanceRef = useRef<ChartJS | null>(null);

  const destroyChart = useCallback(() => {
    if (chartInstanceRef.current) {
      chartInstanceRef.current.destroy();
      chartInstanceRef.current = null;
    }
  }, []);

  const createChart = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    destroyChart();

    const chartData: ChartData = {
      labels: data.map(d => new Date(d.time).toLocaleTimeString()),
      datasets: [{
        label: type.toUpperCase(),
        data: data.map(d => d.value),
        borderColor: style.lineColor,
        backgroundColor: style.backgroundColor,
        borderWidth: style.lineWidth,
        borderDash: style.lineStyle === 'dashed' ? [5, 5] : 
                   style.lineStyle === 'dotted' ? [2, 2] : undefined,
        pointStyle: style.pointStyle,
        pointRadius: style.pointSize,
        tension: style.tension,
        fill: true
      }]
    };

    const chartOptions: ChartOptions = {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      scales: {
        x: {
          display: true,
          title: {
            display: true,
            text: 'Time'
          },
          grid: {
            display: false
          }
        },
        y: {
          display: true,
          title: {
            display: true,
            text: 'Value'
          },
          grid: {
            display: false
          }
        }
      },
      plugins: {
        legend: {
          display: false
        }
      }
    };

    try {
      chartInstanceRef.current = new ChartJS(ctx, {
        type: 'line',
        data: chartData,
        options: chartOptions
      });
    } catch (error) {
      console.error('Error creating chart:', error);
      destroyChart();
    }
  }, [data, type, style, destroyChart]);

  useEffect(() => {
    createChart();
    return destroyChart;
  }, [createChart, destroyChart]);

  return chartInstanceRef.current;
};

const Chart: React.FC<ChartProps> = ({ data, type }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [isCustomizing, setIsCustomizing] = useState(false);
  const [chartStyle, setChartStyle] = useState<ChartStyle>({
    lineColor: '#4dabf7',
    backgroundColor: 'rgba(77, 171, 247, 0.1)',
    lineWidth: 2,
    lineStyle: 'solid',
    pointStyle: 'circle',
    pointSize: 4,
    tension: 0.4
  });

  useChart(canvasRef, data, type, chartStyle);

  return (
    <ChartContainer>
      <ChartTitle>
        {type.toUpperCase()} Measurement
        <CustomizeButton onClick={() => setIsCustomizing(!isCustomizing)}>
          Customize Chart
        </CustomizeButton>
        <CustomizationPanel isOpen={isCustomizing}>
          <CustomizationGroup>
            <Label>Line Color</Label>
            <ColorInput
              type="color"
              value={chartStyle.lineColor}
              onChange={(e) => setChartStyle(prev => ({ ...prev, lineColor: e.target.value }))}
            />
          </CustomizationGroup>
          <CustomizationGroup>
            <Label>Background Color</Label>
            <ColorInput
              type="color"
              value={chartStyle.backgroundColor}
              onChange={(e) => setChartStyle(prev => ({ ...prev, backgroundColor: e.target.value }))}
            />
          </CustomizationGroup>
          <CustomizationGroup>
            <Label>Line Width ({chartStyle.lineWidth}px)</Label>
            <RangeInput
              type="range"
              min="1"
              max="10"
              value={chartStyle.lineWidth}
              onChange={(e) => setChartStyle(prev => ({ ...prev, lineWidth: Number(e.target.value) }))}
            />
          </CustomizationGroup>
          <CustomizationGroup>
            <Label>Line Style</Label>
            <Select
              value={chartStyle.lineStyle}
              onChange={(e) => setChartStyle(prev => ({ ...prev, lineStyle: e.target.value as any }))}
            >
              <option value="solid">Solid</option>
              <option value="dashed">Dashed</option>
              <option value="dotted">Dotted</option>
            </Select>
          </CustomizationGroup>
          <CustomizationGroup>
            <Label>Point Style</Label>
            <Select
              value={chartStyle.pointStyle}
              onChange={(e) => setChartStyle(prev => ({ ...prev, pointStyle: e.target.value as any }))}
            >
              <option value="circle">Circle</option>
              <option value="square">Square</option>
              <option value="triangle">Triangle</option>
              <option value="cross">Cross</option>
            </Select>
          </CustomizationGroup>
          <CustomizationGroup>
            <Label>Point Size ({chartStyle.pointSize}px)</Label>
            <RangeInput
              type="range"
              min="0"
              max="10"
              value={chartStyle.pointSize}
              onChange={(e) => setChartStyle(prev => ({ ...prev, pointSize: Number(e.target.value) }))}
            />
          </CustomizationGroup>
          <CustomizationGroup>
            <Label>Line Tension ({chartStyle.tension})</Label>
            <RangeInput
              type="range"
              min="0"
              max="1"
              step="0.1"
              value={chartStyle.tension}
              onChange={(e) => setChartStyle(prev => ({ ...prev, tension: Number(e.target.value) }))}
            />
          </CustomizationGroup>
        </CustomizationPanel>
      </ChartTitle>
      <div style={{ position: 'relative', height: 'calc(100% - 60px)', width: '100%' }}>
        <canvas ref={canvasRef} style={{ visibility: data.length ? 'visible' : 'hidden' }} />
      </div>
    </ChartContainer>
  );
};

export default Chart; 