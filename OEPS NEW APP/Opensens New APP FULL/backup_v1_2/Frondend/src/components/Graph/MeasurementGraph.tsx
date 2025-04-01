import React from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts';
import { DataPoint } from '../../types';

interface MeasurementGraphProps {
  data: DataPoint[];
  measurementStatus: string;
  currentValue: number;
  potentialValue: number;
  autoFocus: boolean;
  toggleAutoFocus: () => void;
}

export const MeasurementGraph: React.FC<MeasurementGraphProps> = ({
  data,
  measurementStatus,
  currentValue,
  potentialValue,
  autoFocus,
  toggleAutoFocus
}) => {
  return (
    <div className="bg-gray-800 rounded-lg h-full flex flex-col items-center justify-center">
      <ResponsiveContainer width="100%" height="90%">
        <LineChart data={data.length > 0 ? data : [
          {x: -1.0, y: 0.2},
          {x: -0.8, y: 0.21},
          {x: -0.6, y: 0.22},
          {x: -0.5, y: 0.15},
          {x: -0.4, y: 0.05},
          {x: -0.3, y: 0.02},
          {x: -0.2, y: 0.15},
          {x: 0.0, y: 0.22},
          {x: 0.2, y: 0.25},
          {x: 0.3, y: 0.27},
          {x: 0.4, y: 0.29},
          {x: 0.5, y: 0.35},
          {x: 0.7, y: 0.55},
          {x: 0.8, y: 0.70},
          {x: 0.9, y: 0.45},
          {x: 1.0, y: 0.40},
        ]}>
          <CartesianGrid strokeDasharray="3 3" stroke="#333" />
          <XAxis 
            dataKey={data.length > 0 ? "time" : "x"} 
            label={{ value: 'Current (μA)', position: 'insideBottom', offset: -5 }}
            tick={{ fill: '#aaa' }}
            domain={[-1, 1]}
          />
          <YAxis 
            label={{ value: 'Potential (V)', angle: -90, position: 'insideLeft' }}
            tick={{ fill: '#aaa' }}
            domain={[0, 0.8]}
          />
          <Tooltip contentStyle={{ backgroundColor: '#333', border: 'none' }} />
          <Line 
            type="monotone" 
            dataKey={data.length > 0 ? "current" : "y"} 
            stroke="#3B82F6" 
            dot={false}
          />
          {data.length > 0 && (
            <Line 
              type="monotone" 
              dataKey="potential" 
              stroke="#10B981" 
              dot={false}
            />
          )}
        </LineChart>
      </ResponsiveContainer>
      
      <div className="mt-4 flex justify-between w-full px-6 text-gray-400">
        <div>
          <div className="text-white">
            Status: <span className={`${
              measurementStatus === 'Ready' ? 'text-blue-400' : 
              measurementStatus === 'Running' ? 'text-green-400' : 'text-yellow-400'
            }`}>{measurementStatus}</span>
          </div>
          <div>Voltage: <span className="text-white">{potentialValue.toFixed(3)} V</span></div>
        </div>
        <div>
          <div>Current: <span className="text-white">{currentValue.toFixed(2)} μA</span></div>
          <button 
            onClick={toggleAutoFocus}
            className={`mt-2 text-white px-3 py-1 rounded transition-colors ${
              autoFocus ? 'bg-blue-600' : 'bg-gray-600'
            }`}
          >
            Auto Focus {autoFocus ? 'ON' : 'OFF'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default MeasurementGraph; 