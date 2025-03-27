import { useState, useEffect } from 'react';
import styled from 'styled-components';
import { ThemeProvider } from 'styled-components';
import { lightTheme, darkTheme, Theme } from './theme';
import MenuBar from './components/MenuBar';
import DeviceConnection from './components/DeviceConnection';
import DataVisualization from './components/DataVisualization';
import DataLakeManager from './components/DataLakeManager';
import Settings from './components/Settings';
import { Measurement } from './types';

const AppContainer = styled.div<{ theme: Theme }>`
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: ${props => props.theme.background};
  color: ${props => props.theme.text};
`;

const MainContent = styled.main<{ theme: Theme }>`
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 1rem;
  overflow: auto;
`;

const StatusBarContainer = styled.div<{ theme: Theme }>`
  padding: 10px;
  background-color: ${props => props.theme.background};
  border-top: 1px solid ${props => props.theme.border};
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.875rem;
  color: ${props => props.theme.text};
`;

const StatusItem = styled.span<{ theme: Theme }>`
  display: flex;
  align-items: center;
  gap: 0.5rem;
`;

const StatusIndicator = styled.span<{ active: boolean; theme: Theme }>`
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: ${props => props.active ? props.theme.success : props.theme.error};
`;

interface DeviceStatus {
  connected: boolean;
  name: string;
  battery: number;
  temperature: number;
}

const App: React.FC = () => {
  const [isDarkMode, setIsDarkMode] = useState(false);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [deviceStatus, setDeviceStatus] = useState<DeviceStatus>({
    connected: false,
    name: '',
    battery: 0,
    temperature: 0
  });
  const [measurementData, setMeasurementData] = useState<Measurement[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    console.log('App component mounted');
    // Simulate initial loading
    const timer = setTimeout(() => {
      setIsLoading(false);
    }, 1000);
    return () => clearTimeout(timer);
  }, []);

  const toggleTheme = () => {
    setIsDarkMode(!isDarkMode);
  };

  const handleDeviceConnect = async (device: DeviceStatus) => {
    console.log('Device connection attempt:', device);
    setDeviceStatus(device);
    // Simulate data collection
    const startTime = new Date().toISOString();
    const interval = setInterval(() => {
      setMeasurementData(prev => [
        ...prev,
        {
          time: new Date().toISOString(),
          value: Math.random() * 10 - 5,
          type: 'cv' as const
        }
      ]);
    }, 1000);

    // Cleanup interval on disconnect
    if (!device.connected) {
      clearInterval(interval);
    }
  };

  const renderContent = () => {
    console.log('Rendering content for tab:', activeTab);
    switch (activeTab) {
      case 'dashboard':
        return (
          <>
            <DeviceConnection
              onConnect={handleDeviceConnect}
            />
            <DataVisualization 
              data={measurementData}
            />
          </>
        );
      case 'data':
        return <DataLakeManager />;
      case 'settings':
        return <Settings />;
      default:
        return null;
    }
  };

  if (isLoading) {
    return (
      <div style={{ 
        display: 'flex', 
        justifyContent: 'center', 
        alignItems: 'center', 
        height: '100vh',
        backgroundColor: isDarkMode ? '#121212' : '#ffffff',
        color: isDarkMode ? '#ffffff' : '#000000'
      }}>
        Loading...
      </div>
    );
  }

  return (
    <ThemeProvider theme={isDarkMode ? darkTheme : lightTheme}>
      <AppContainer>
        <MenuBar
          activeTab={activeTab}
          onTabChange={setActiveTab}
          onThemeToggle={toggleTheme}
        />
        <MainContent>
          {renderContent()}
        </MainContent>
        <StatusBarContainer>
          <StatusItem>
            <StatusIndicator active={deviceStatus.connected} />
            {deviceStatus.connected ? 'Connected' : 'Disconnected'}
            {deviceStatus.name && ` - ${deviceStatus.name}`}
          </StatusItem>
          <StatusItem>
            Battery: {deviceStatus.battery}%
          </StatusItem>
          <StatusItem>
            Temperature: {deviceStatus.temperature}°C
          </StatusItem>
        </StatusBarContainer>
      </AppContainer>
    </ThemeProvider>
  );
};

export default App; 