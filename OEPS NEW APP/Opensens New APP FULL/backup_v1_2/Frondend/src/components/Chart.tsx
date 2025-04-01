import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer
} from 'recharts';
import { Play, Pause, RefreshCw } from 'lucide-react';
import { useRealtimeADC } from '../hooks/useRealtimeADC';

export const Chart: React.FC = () => {
  const { chartData, isStreaming, latency, toggleStreaming, clearData } = useRealtimeADC();

  const formatTime = (timestamp: number) => {
    const date = new Date(timestamp);
    const timeStr = date.toLocaleTimeString('en-US', { 
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
    const ms = date.getMilliseconds().toString().padStart(3, '0');
    return `${timeStr}.${ms}`;
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between p-4 border-b border-gray-700">
        <div className="flex items-center space-x-4">
          <button
            onClick={toggleStreaming}
            className="px-4 py-2 text-sm bg-gray-700 text-gray-200 rounded hover:bg-gray-600 flex items-center space-x-2"
          >
            {isStreaming ? (
              <>
                <Pause className="w-4 h-4" />
                <span>Stop</span>
              </>
            ) : (
              <>
                <Play className="w-4 h-4" />
                <span>Start</span>
              </>
            )}
          </button>
          <button
            onClick={clearData}
            className="px-4 py-2 text-sm bg-gray-700 text-gray-200 rounded hover:bg-gray-600 flex items-center space-x-2"
          >
            <RefreshCw className="w-4 h-4" />
            <span>Clear</span>
          </button>
        </div>
        {isStreaming && (
          <div className="text-sm text-gray-400">
            <span>Latency: {latency.current.toFixed(1)}ms </span>
            <span className="text-gray-500">(avg: {latency.average.toFixed(1)}ms)</span>
          </div>
        )}
      </div>

      <div className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis
              dataKey="timestamp"
              tickFormatter={formatTime}
              stroke="#9CA3AF"
              tick={{ fill: '#9CA3AF' }}
            />
            <YAxis
              yAxisId="potential"
              domain={[-8, 8]}
              label={{ 
                value: 'Potential (V)',
                angle: -90,
                position: 'insideLeft',
                style: { fill: '#60A5FA' }
              }}
              stroke="#60A5FA"
              tick={{ fill: '#9CA3AF' }}
            />
            <YAxis
              yAxisId="current"
              orientation="right"
              domain={[-25, 25]}
              label={{
                value: 'Current (mA)',
                angle: 90,
                position: 'insideRight',
                style: { fill: '#34D399' }
              }}
              stroke="#34D399"
              tick={{ fill: '#9CA3AF' }}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#1F2937',
                border: 'none',
                borderRadius: '0.375rem',
                color: '#F3F4F6'
              }}
              labelFormatter={formatTime}
            />
            <Line
              yAxisId="potential"
              type="monotone"
              dataKey="potential"
              stroke="#60A5FA"
              dot={false}
              isAnimationActive={false}
            />
            <Line
              yAxisId="current"
              type="monotone"
              dataKey="current"
              stroke="#34D399"
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}; 