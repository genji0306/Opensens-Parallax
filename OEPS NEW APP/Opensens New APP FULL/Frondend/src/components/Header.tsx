import React from 'react';
import { Settings, Sun } from 'lucide-react';
import { useDevice } from '../hooks/useDevice';

interface HeaderProps {
  openSettingsModal: () => void;
  toggleDarkMode: () => void;
}

export const Header: React.FC<HeaderProps> = ({ 
  openSettingsModal, 
  toggleDarkMode 
}) => {
  const { isConnected } = useDevice();

  return (
    <div className="p-4 flex items-center justify-between border-b border-gray-700">
      <div className="flex items-center space-x-4">
        <div className="flex items-center space-x-2">
          <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}></div>
          <span className="text-sm text-gray-300">{isConnected ? 'Connected' : 'Disconnected'}</span>
        </div>
        
        <div className="flex space-x-2">
          <button 
            onClick={openSettingsModal}
            className="p-1.5 bg-gray-700 hover:bg-gray-600 rounded transition-colors"
          >
            <Settings size={18} />
          </button>
          <button 
            onClick={toggleDarkMode}
            className="p-1.5 bg-gray-700 hover:bg-gray-600 rounded transition-colors"
          >
            <Sun size={18} />
          </button>
        </div>
      </div>
    </div>
  );
};

export default Header; 