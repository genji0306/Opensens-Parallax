import React from 'react';

export const SimpleApp: React.FC = () => {
  return (
    <div style={{ 
      padding: '20px',
      maxWidth: '800px',
      margin: '40px auto',
      backgroundColor: '#2d3748',
      borderRadius: '8px',
      boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)'
    }}>
      <h1 style={{ 
        fontSize: '24px',
        color: 'white',
        marginBottom: '16px'
      }}>
        OpenSens Potentiostat
      </h1>
      
      <p style={{ 
        color: '#e2e8f0',
        marginBottom: '20px'
      }}>
        This is a simplified version of the application for testing purposes.
      </p>

      <div style={{
        background: '#1a202c',
        padding: '16px',
        borderRadius: '4px',
        marginBottom: '16px'
      }}>
        <h2 style={{ 
          fontSize: '18px',
          color: 'white',
          marginBottom: '8px'
        }}>
          Debug Information
        </h2>
        <p style={{ color: '#a0aec0' }}>
          React is running correctly if you can see this component.
        </p>
      </div>

      <button 
        onClick={() => alert('UI interactions are working!')}
        style={{
          backgroundColor: '#4299e1',
          color: 'white',
          border: 'none',
          padding: '8px 16px',
          borderRadius: '4px',
          cursor: 'pointer'
        }}
      >
        Test Button
      </button>
    </div>
  );
}; 