import collections
import os
from pathlib import Path

'''
    STATIC VARIABLE
'''

# path save file result
base_dir = os.path.dirname(os.path.realpath(__file__))
SAVE_PATH = os.path.join(base_dir, 'save')
# Create save path for each technique
Path(SAVE_PATH).mkdir(parents=True, exist_ok=True)


ADD_TABLE_SIZE = [4, 3]  # Size of album table
COLOR_TABLE = [
    '#b18484',
    '#eababa',
    '#c4c7ff',
    '#d67676',
    '#86a9dc',
    '#feff57',
    '#5700ff',
]
INDEX_TECHNIQUES = [1, 1, 1]
LIST_TECHNIQUES = [
    "Charge/disch",
    "Rate testing",
    "Cyclic voltammetry"
]

usb_vid_ = "0xa0a0"  # Default USB vendor ID, can also be adjusted in the GUI
usb_pid_ = "0x0002"  # Default USB product ID, can also be adjusted in the GUI
current_range_list = ["20 mA", u"200 µA", u"2 µA"]

# Fine adjustment for shunt resistors, containing values of R1/10ohm, R2/1kohm, R3/100kohm (can also be adjusted in the GUI)
shunt_calibration = [1., 1., 1.]

# Default current range (expressed as index in current_range_list)
currentrange = 0
units_list = ["Potential (V)", "Current (mA)", "DAC Code"]
dev = None  # Global object which is reserved for the USB device
current_offset = 0.  # Current offset in DAC counts
potential_offset = 0.  # Potential offset in DAC counts
potential = 0.  # Measured potential in V
current = 0.  # Measured current in mA
last_potential_values = collections.deque(maxlen=200)
last_current_values = collections.deque(maxlen=200)
raw_potential = 0  # Measured potential in ADC counts
raw_current = 0  # Measured current in ADC counts
last_raw_potential_values = collections.deque(maxlen=200)
last_raw_current_values = collections.deque(maxlen=200)

# Global counters used for automatic current ranging
overcounter, undercounter, skipcounter = 0, 0, 0
time_of_last_adcread = 0.
adcread_interval = 0.09  # ADC sampling interval (in seconds)

# Enable logging of potential and current in idle mode (can be adjusted in the GUI)
logging_enabled = False

# usb_connected = False
start_stop = 1
stop = 0

queue_measure = []
id_ = 0
para_run = {}
