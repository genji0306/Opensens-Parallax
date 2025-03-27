export const lightTheme = {
  background: '#ffffff',
  text: '#000000',
  primary: '#1976d2',
  secondary: '#dc004e',
  border: '#e0e0e0',
  hover: '#f5f5f5',
  active: '#e0e0e0',
  error: '#f44336',
  success: '#4caf50',
  warning: '#ff9800',
  info: '#2196f3',
  chart: {
    grid: '#e0e0e0',
    line: '#4dabf7',
    background: 'rgba(77, 171, 247, 0.1)',
    text: '#333333'
  }
};

export const darkTheme = {
  background: '#121212',
  text: '#ffffff',
  primary: '#90caf9',
  secondary: '#f48fb1',
  border: '#333333',
  hover: '#2d2d2d',
  active: '#404040',
  error: '#f44336',
  success: '#4caf50',
  warning: '#ff9800',
  info: '#2196f3',
  chart: {
    grid: '#404040',
    line: '#4dabf7',
    background: 'rgba(77, 171, 247, 0.1)',
    text: '#ffffff'
  }
};

export type Theme = typeof lightTheme; 