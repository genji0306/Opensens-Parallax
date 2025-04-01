import React from 'react';
import { useDevice } from '../../hooks/useDevice';
import { Button } from '../ui/button';
import { Settings, Power } from 'lucide-react';

interface DeviceControlsProps {
  onCalibrationClick: () => void;
  onManualClick: () => void;
}

export const DeviceControls: React.FC<DeviceControlsProps> = ({
  onCalibrationClick,
  onManualClick,
}) => {
  const { isConnected } = useDevice();

  return (
    <div className="space-y-4">
      <div className="flex flex-col space-y-2">
        <Button
          onClick={onCalibrationClick}
          className="w-full bg-blue-600 hover:bg-blue-700 text-white"
        >
          <Settings className="w-4 h-4 mr-2" />
          Calibration
        </Button>
        <Button
          onClick={onManualClick}
          className="w-full bg-purple-600 hover:bg-purple-700 text-white"
        >
          <Power className="w-4 h-4 mr-2" />
          Manual
        </Button>
      </div>
    </div>
  );
};

export default DeviceControls; 