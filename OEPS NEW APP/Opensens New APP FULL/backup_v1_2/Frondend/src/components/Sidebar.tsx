import React from 'react';
import { 
  Home, 
  Settings, 
  Clock, 
  Save, 
  Layers, 
  Database, 
  Activity,
  HelpCircle
} from 'lucide-react';

export const Sidebar: React.FC = () => {
  return (
    <div className="hidden lg:flex flex-col w-16 bg-gray-900 border-r border-gray-700">
      <div className="flex flex-col items-center py-4">
        <a 
          href="/" 
          className="p-2 mb-6"
        >
          <img src="/logo.svg" alt="Logo" className="h-8 w-8" />
        </a>
        
        <div className="flex flex-col items-center space-y-4 flex-1">
          <SidebarButton icon={<Home size={20} />} label="Home" isActive={true} />
          <SidebarButton icon={<Clock size={20} />} label="History" />
          <SidebarButton icon={<Layers size={20} />} label="Templates" />
          <SidebarButton icon={<Database size={20} />} label="Data" />
          <SidebarButton icon={<Activity size={20} />} label="Analysis" />
          <SidebarButton icon={<Save size={20} />} label="Export" />
        </div>
        
        <div className="mt-auto flex flex-col items-center space-y-4 mb-4">
          <SidebarButton icon={<Settings size={20} />} label="Settings" />
          <SidebarButton icon={<HelpCircle size={20} />} label="Help" />
        </div>
      </div>
    </div>
  );
};

interface SidebarButtonProps {
  icon: React.ReactNode;
  label: string;
  isActive?: boolean;
  onClick?: () => void;
}

const SidebarButton: React.FC<SidebarButtonProps> = ({ 
  icon, 
  label, 
  isActive = false,
  onClick 
}) => {
  return (
    <button
      className={`relative w-10 h-10 rounded-md flex items-center justify-center group ${
        isActive ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white hover:bg-gray-800'
      }`}
      onClick={onClick}
      title={label}
    >
      {isActive && (
        <div className="absolute left-0 top-1/2 transform -translate-y-1/2 w-1 h-5 bg-blue-400 rounded-r-full" />
      )}
      
      {icon}
      
      <span className="absolute left-full ml-2 px-2 py-1 rounded bg-gray-800 text-white text-xs whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity duration-200">
        {label}
      </span>
    </button>
  );
}; 