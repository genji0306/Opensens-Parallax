import React, { useEffect } from 'react';
import { Routes, Route } from 'react-router-dom';
import PotentiostatApp from './components/PotentiostatApp';

function App() {
  useEffect(() => {
    console.log('App component mounted');
    document.title = 'OpenSens Potentiostat';
  }, []);

  return (
    <div className="app">
      <Routes>
        <Route path="/" element={<PotentiostatApp />} />
      </Routes>
    </div>
  );
}

export default App; 