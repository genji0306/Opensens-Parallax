from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from typing import Optional, List
import usb.core
import usb.util
import json
import os
from dotenv import load_dotenv
from pydantic import BaseModel

# Load environment variables
load_dotenv()

app = FastAPI(
    title="OEPS WebApp API",
    description="API for OEPS device control and data acquisition",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Device state
class DeviceState:
    def __init__(self):
        self.device = None
        self.vid = None
        self.pid = None
        self.current_theme = "deep_blue"
        self.cell_connected = False
        self.control_mode = "potentiostat"
        self.current_range = "1mA"

device_state = DeviceState()

class DeviceConnection(BaseModel):
    vid: str
    pid: str

class Measurement(BaseModel):
    time: str
    value: float
    type: str

@app.get("/")
async def root():
    return {"message": "Welcome to OEPS WebApp API"}

@app.post("/connect")
async def connect_device(device: DeviceConnection):
    try:
        # Simulate device connection
        # In a real application, this would connect to the actual device
        return {
            "manufacturer": "OpenSens",
            "product": "OEPS Device",
            "vid": device.vid,
            "pid": device.pid,
            "control_mode": "Constant Current",
            "current_range": "1mA",
            "cell_connected": True
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/device-info")
async def get_device_info():
    if device_state.device is None:
        return JSONResponse(
            status_code=404,
            content={"success": False, "message": "No device connected"}
        )
    
    try:
        # Get device information
        manufacturer = usb.util.get_string(device_state.device, device_state.device.iManufacturer)
        product = usb.util.get_string(device_state.device, device_state.device.iProduct)
        
        return {
            "success": True,
            "data": {
                "manufacturer": manufacturer,
                "product": product,
                "vid": hex(device_state.vid),
                "pid": hex(device_state.pid),
                "control_mode": device_state.control_mode,
                "current_range": device_state.current_range,
                "cell_connected": device_state.cell_connected
            }
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": str(e)}
        )

@app.post("/api/disconnect")
async def disconnect_device():
    try:
        if device_state.device is not None:
            usb.util.dispose_resources(device_state.device)
            device_state.device = None
            device_state.vid = None
            device_state.pid = None
            return {"success": True, "message": "Device disconnected successfully"}
        return {"success": True, "message": "No device connected"}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": str(e)}
        )

@app.get("/api/status")
async def get_status():
    return {
        "status": "ok",
        "version": "1.0.0"
    }

@app.post("/api/measurements")
async def create_measurement(measurement: Measurement):
    # Here you would typically save the measurement to a database
    return measurement

@app.get("/api/measurements")
async def get_measurements():
    # Here you would typically fetch measurements from a database
    return []

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 