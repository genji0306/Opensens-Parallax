import React, { useState } from 'react';
import { Download, X, FileText, FileJson } from 'lucide-react';
import { ModalBackdrop } from '../ModalBackdrop';
import { DataPoint } from '../../types';

interface ExportDataModalProps {
  isOpen: boolean;
  onClose: () => void;
  onExport: (format: 'csv' | 'json') => void;
  data: DataPoint[];
}

export const ExportDataModal: React.FC<ExportDataModalProps> = ({
  isOpen,
  onClose,
  onExport,
  data
}) => {
  const [format, setFormat] = useState<'csv' | 'json'>('csv');
  const [fileName, setFileName] = useState('potentiostat_data');
  const [includeTimestamp, setIncludeTimestamp] = useState(true);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onExport(format);
  };

  const getFormattedDate = () => {
    const now = new Date();
    return `${now.getFullYear()}-${(now.getMonth() + 1).toString().padStart(2, '0')}-${now.getDate().toString().padStart(2, '0')}`;
  };

  const getPreview = () => {
    if (data.length === 0) return 'No data to export';

    if (format === 'csv') {
      const headers = ['timestamp', 'current', 'voltage'].join(',');
      const rows = data.slice(0, 3).map(d => 
        [d.timestamp, d.current, d.voltage].join(',')
      ).join('\n');
      return `${headers}\n${rows}\n...`;
    } else {
      return JSON.stringify(data.slice(0, 2), null, 2) + '\n...';
    }
  };

  return (
    <ModalBackdrop isOpen={isOpen} onClose={onClose}>
      <div className="w-full max-w-md p-5">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-xl font-bold text-white flex items-center">
            <Download size={20} className="mr-2 text-gray-400" />
            <span>Export Data</span>
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* File Name */}
          <div className="space-y-2">
            <label className="text-md font-medium text-gray-300 block">File Name</label>
            <div className="flex items-center">
              <input
                type="text"
                value={fileName}
                onChange={(e) => setFileName(e.target.value)}
                className="bg-gray-700 text-white rounded-l w-full p-2 border border-gray-600"
                placeholder="potentiostat_data"
              />
              <div className="bg-gray-800 text-gray-400 p-2 rounded-r border border-l-0 border-gray-600">
                {includeTimestamp ? `_${getFormattedDate()}` : ''}.{format}
              </div>
            </div>
            <div className="flex items-center mt-2">
              <input
                type="checkbox"
                id="include-timestamp"
                checked={includeTimestamp}
                onChange={() => setIncludeTimestamp(!includeTimestamp)}
                className="mr-2"
              />
              <label htmlFor="include-timestamp" className="text-sm text-gray-400">Include date in filename</label>
            </div>
          </div>

          {/* Format Selection */}
          <div className="space-y-3">
            <label className="text-md font-medium text-gray-300 block">Export Format</label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setFormat('csv')}
                className={`p-3 rounded border flex items-center justify-center ${
                  format === 'csv'
                    ? 'bg-blue-600 border-blue-500 text-white'
                    : 'bg-gray-700 border-gray-600 text-gray-300 hover:bg-gray-600'
                }`}
              >
                <FileText size={18} className="mr-2" />
                <span>CSV</span>
              </button>
              
              <button
                type="button"
                onClick={() => setFormat('json')}
                className={`p-3 rounded border flex items-center justify-center ${
                  format === 'json'
                    ? 'bg-blue-600 border-blue-500 text-white'
                    : 'bg-gray-700 border-gray-600 text-gray-300 hover:bg-gray-600'
                }`}
              >
                <FileJson size={18} className="mr-2" />
                <span>JSON</span>
              </button>
            </div>
          </div>

          {/* Preview */}
          <div className="space-y-2">
            <label className="text-md font-medium text-gray-300 block">Preview</label>
            <pre className="bg-gray-800 p-3 rounded text-gray-300 text-xs font-mono overflow-x-auto">
              {getPreview()}
            </pre>
          </div>

          {/* Action Buttons */}
          <div className="flex justify-end pt-4 border-t border-gray-700">
            <div className="flex space-x-4">
              <button
                type="button"
                onClick={onClose}
                className="bg-gray-700 hover:bg-gray-600 text-white px-4 py-2 rounded"
              >
                Cancel
              </button>

              <button
                type="submit"
                className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded flex items-center"
              >
                <Download size={18} className="mr-2" />
                Export
              </button>
            </div>
          </div>
        </form>
      </div>
    </ModalBackdrop>
  );
}; 