# OpenSens Potentiostat Web Application

A modern web interface for controlling and visualizing data from OpenSens potentiostat devices.

## Features

- Real-time data visualization
- Protocol creation and management
- Device settings configuration
- Data export (CSV, JSON)
- Dark mode interface
- Responsive design

## Getting Started

### Prerequisites

- Node.js 16+ and npm

### Installation

1. Clone the repository
2. Install dependencies:

```bash
cd Frondend
npm install
```

3. Start the development server:

```bash
npm run dev
```

4. Open [http://localhost:3000](http://localhost:3000) to view the app in your browser.

## Technology Stack

- React 18
- TypeScript
- Tailwind CSS
- Vite
- Recharts for data visualization
- Lucide React for icons

## Project Structure

```
src/
├── components/           # UI components
│   ├── modals/           # Modal components
│   └── ...
├── types.ts              # TypeScript type definitions
├── main.tsx              # Entry point
└── App.tsx               # Main application component
```

## Development

### Building for Production

```bash
npm run build
```

The build artifacts will be stored in the `dist/` directory.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- OpenSens Team
- All contributors to this project 