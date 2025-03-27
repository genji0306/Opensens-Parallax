# OEPS WebApp

A modern web application for the OEPS device, built with FastAPI and React.

## Project Structure

```
webapp_new/
├── backend/           # FastAPI backend
│   ├── app.py        # Main FastAPI application
│   └── requirements.txt
└── frontend/         # React frontend
    ├── src/         # Source files
    ├── index.html   # HTML entry point
    ├── package.json # Frontend dependencies
    └── tsconfig.json # TypeScript configuration
```

## Setup Instructions

### Backend Setup

1. Create and activate a virtual environment:
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the backend server:
```bash
uvicorn app:app --reload
```

The backend will be available at http://localhost:8000

### Frontend Setup

1. Install Node.js dependencies:
```bash
cd frontend
npm install
```

2. Start the development server:
```bash
npm run dev
```

The frontend will be available at http://localhost:5173

## API Documentation

Once the backend is running, you can access the API documentation at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Development

- Backend API endpoints are defined in `backend/app.py`
- Frontend components are in `frontend/src/components/`
- Frontend styles are in `frontend/src/index.css`

## Building for Production

1. Build the frontend:
```bash
cd frontend
npm run build
```

2. The production build will be in `frontend/dist/`

## License

Proprietary - All rights reserved 