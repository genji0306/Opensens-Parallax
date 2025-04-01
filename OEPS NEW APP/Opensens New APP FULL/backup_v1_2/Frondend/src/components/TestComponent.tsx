import React from 'react';

export const TestComponent: React.FC = () => {
  return (
    <div className="p-8 bg-red-500 text-white m-4 rounded-lg">
      <h1 className="text-2xl font-bold">Test Component</h1>
      <p className="mt-2">If you can see this, the React rendering is working!</p>
      <button 
        className="mt-4 bg-blue-500 hover:bg-blue-600 px-4 py-2 rounded"
        onClick={() => alert('Button clicked!')}
      >
        Click Me
      </button>
    </div>
  );
}; 