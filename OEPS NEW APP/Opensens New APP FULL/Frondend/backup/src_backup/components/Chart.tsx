import React, { useState } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
} from 'recharts';
import { DataPoint } from '../types';

interface ChartProps {
  data: DataPoint[];
}

export const Chart: React.FC<ChartProps> = ({ data }) => {
  const [viewMode, setViewMode] = useState<'current' | 'voltage' | 'both'>('both');

  // If no data, show placeholder
  if (data.length === 0) {
    return (
      <div className="bg-gray-800 rounded-lg p-4 h-96 flex flex-col justify-center items-center">
        <p className="text-gray-400 text-lg mb-4">No data to display</p>
        <p className="text-gray-500 text-sm">Start an experiment to see results here</p>
      </div>
    );
  }

  return (
    <div className="bg-gray-800 rounded-lg p-4 h-96">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-lg font-medium">Experiment Data</h2>
        
        <div className="flex space-x-2">
          <button
            onClick={() => setViewMode('current')}
            className={`px-3 py-1 text-sm rounded ${
              viewMode === 'current' ? 'bg-blue-600' : 'bg-gray-700 hover:bg-gray-600'
            }`}
          >
            Current
          </button>
          
          <button
            onClick={() => setViewMode('voltage')}
            className={`px-3 py-1 text-sm rounded ${
              viewMode === 'voltage' ? 'bg-blue-600' : 'bg-gray-700 hover:bg-gray-600'
            }`}
          >
            Voltage
          </button>
          
          <button
            onClick={() => setViewMode('both')}
            className={`px-3 py-1 text-sm rounded ${
              viewMode === 'both' ? 'bg-blue-600' : 'bg-gray-700 hover:bg-gray-600'
            }`}
          >
            Both
          </button>
        </div>
      </div>
      
      <ResponsiveContainer width="100%" height="85%">
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#444" />
          <XAxis 
            dataKey="timestamp" 
            label={{ value: 'Time (s)', position: 'insideBottom', offset: -5 }}
            tick={{ fill: '#aaa' }}
          />
          
          {(viewMode === 'current' || viewMode === 'both') && (
            <YAxis 
              yAxisId="current"
              label={{ value: 'Current (mA)', angle: -90, position: 'insideLeft' }}
              tick={{ fill: '#aaa' }}
            />
          )}
          
          {(viewMode === 'voltage' || viewMode === 'both') && (
            <YAxis 
              yAxisId={viewMode === 'both' ? 'voltage' : 'current'}
              orientation={viewMode === 'both' ? 'right' : 'left'}
              label={{ 
                value: 'Voltage (V)', 
                angle: -90, 
                position: viewMode === 'both' ? 'insideRight' : 'insideLeft' 
              }}
              tick={{ fill: '#aaa' }}
            />
          )}
          
          <Tooltip contentStyle={{ backgroundColor: '#333', border: 'none' }} />
          <Legend />
          
          {(viewMode === 'current' || viewMode === 'both') && (
            <Line 
              type="monotone" 
              dataKey="current" 
              stroke="#3B82F6" 
              yAxisId="current" 
              dot={false}
              activeDot={{ r: 6 }}
            />
          )}
          
          {(viewMode === 'voltage' || viewMode === 'both') && (
            <Line 
              type="monotone" 
              dataKey="voltage" 
              stroke="#EC4899" 
              yAxisId={viewMode === 'both' ? 'voltage' : 'current'} 
              dot={false}
              activeDot={{ r: 6 }}
            />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}; 