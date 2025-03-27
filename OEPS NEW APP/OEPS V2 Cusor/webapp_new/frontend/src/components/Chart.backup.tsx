import React, { useEffect, useRef, useCallback } from 'react';
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
`;

interface ChartProps {
  data: Measurement[];
  type: 'cv' | 'lsv' | 'ca' | 'cp' | 'eis' | 'dpp' | 'swv' | 'acv' | 'ocp' | 'ms';
}

const useChart = (canvasRef: React.RefObject<HTMLCanvasElement>, data: Measurement[], type: string) => {
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
        borderColor: '#4dabf7',
        backgroundColor: 'rgba(77, 171, 247, 0.1)',
        borderWidth: 2,
        tension: 0.4,
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
  }, [data, type, destroyChart]);

  useEffect(() => {
    createChart();
    return destroyChart;
  }, [createChart, destroyChart]);

  return chartInstanceRef.current;
};

const Chart: React.FC<ChartProps> = ({ data, type }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  useChart(canvasRef, data, type);

  return (
    <ChartContainer>
      <ChartTitle>{type.toUpperCase()} Measurement</ChartTitle>
      <div style={{ position: 'relative', height: 'calc(100% - 60px)', width: '100%' }}>
        <canvas ref={canvasRef} style={{ visibility: data.length ? 'visible' : 'hidden' }} />
      </div>
    </ChartContainer>
  );
};

export default Chart; 