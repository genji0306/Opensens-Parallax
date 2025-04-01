import React from 'react';
import { Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { theme } from './theme';
import PotentiostatApp from './components/PotentiostatApp';
import { DeviceProvider } from './contexts/DeviceContext';

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <DeviceProvider>
        <Routes>
          <Route path="/" element={<PotentiostatApp />} />
        </Routes>
      </DeviceProvider>
    </ThemeProvider>
  );
}

export default App; 