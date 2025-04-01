import React, { useState } from 'react';
import { Sun, Moon, Menu, ChevronsRight, Terminal } from 'lucide-react';

export const Navbar: React.FC = () => {
  const [isDarkMode, setIsDarkMode] = useState(true);
  const [isConsoleOpen, setIsConsoleOpen] = useState(false);

  return (
    <div className="bg-gray-900 px-4 py-3 flex justify-between items-center border-b border-gray-700">
      <div className="flex items-center space-x-3">
        <button className="lg:hidden p-1 text-gray-400 hover:text-white">
          <Menu size={20} />
        </button>
        
        <div className="flex items-center space-x-2">
          <img src="/logo.svg" alt="Logo" className="h-8 w-8" />
          <h1 className="text-lg font-bold hidden sm:block">OpenSens Potentiostat</h1>
        </div>
      </div>
      
      <div className="flex items-center space-x-3">
        <button 
          onClick={() => setIsConsoleOpen(!isConsoleOpen)}
          className={`p-1.5 rounded-md text-gray-400 hover:text-white ${isConsoleOpen ? 'bg-gray-700' : ''}`}
        >
          <Terminal size={18} />
        </button>
        
        <button 
          onClick={() => setIsDarkMode(!isDarkMode)}
          className="p-1.5 rounded-md text-gray-400 hover:text-white"
        >
          {isDarkMode ? <Sun size={18} /> : <Moon size={18} />}
        </button>
        
        <div className="h-6 w-px bg-gray-700 mx-1"></div>
        
        <div className="flex items-center space-x-2">
          <div className="w-2 h-2 rounded-full bg-green-500"></div>
          <span className="text-sm text-gray-300">Connected</span>
        </div>
      </div>
      
      {isConsoleOpen && (
        <div className="absolute bottom-0 left-0 right-0 bg-black p-2 z-20 h-32 overflow-y-auto">
          <div className="flex justify-between items-center mb-2">
            <h3 className="text-sm text-gray-300 font-mono">Console Output</h3>
            <button 
              onClick={() => setIsConsoleOpen(false)}
              className="text-gray-500 hover:text-white"
            >
              <ChevronsRight size={16} />
            </button>
          </div>
          
          <div className="font-mono text-xs text-green-400">
            <p>Connected to device on COM3</p>
            <p>Firmware v2.1.0</p>
            <p>Ready for commands...</p>
          </div>
        </div>
      )}
    </div>
  );
}; 