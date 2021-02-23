import collections
import os
import numpy
from PyQt5 import QtGui

'''
    STATIC VARIABLE
'''

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

# path save file result
base_dir = os.path.dirname(os.path.realpath(__file__))
SAVE_PATH = os.path.join(base_dir, 'save')


class AverageBuffer:
    """Collect samples and compute an average as soon as a sufficient number of samples is added."""

    def __init__(self, number_of_samples_to_average):
        self.number_of_samples_to_average = number_of_samples_to_average
        self.samples = []
        self.averagebuffer = []

    def add_sample(self, sample):
        self.samples.append(sample)
        if len(self.samples) >= self.number_of_samples_to_average:
            self.averagebuffer.append(sum(self.samples)/len(self.samples))
            self.samples = []

    def clear(self):
        self.samples = []
        self.averagebuffer = []


class States:
    """Expose a named list of states to be used as a simple state machine."""
    NotConnected, Idle_Init, Idle, Measuring_Offset, Stationary_Graph, Measuring_CV, Measuring_CD, Measuring_Rate, Measuring_start = range(
        9)


def check_state(state_value, desired_states):
    """Check if the current state is in a given list. If so, return True; otherwise, show an error message and return False."""
    if state_value not in desired_states:
        return False
    else:
        return True


def twobytes_to_float(bytes_in):
    """Convert two bytes to a number ranging from -2^15 to 2^15-1."""
    code = 2**8*bytes_in[0]+bytes_in[1]
    return float(code - 2**15)


def decimal_to_dac_bytes(value):
    """Convert a floating-point number, ranging from -2**19 to 2**19-1, to three data bytes in the proper format for the DAC1220."""
    code = 2**19 + \
        int(round(value))  # Convert the (signed) input value to an unsigned 20-bit integer with zero at midway
    # If the input exceeds the boundaries of the 20-bit integer, clip it
    code = numpy.clip(code, 0, 2**20 - 1)
    byte1 = code // 2**12
    byte2 = (code % 2**12) // 2**4
    byte3 = (code - byte1*2**12 - byte2*2**4)*2**4
    return bytes([byte1, byte2, byte3])


def float_to_twobytes(value):
    """Convert a floating-point number ranging from -2^15 to 2^15-1 to a 16-bit representation stored in two bytes."""
    code = 2**15 + int(round(value))
    # If the code exceeds the boundaries of a 16-bit integer, clip it
    code = numpy.clip(code, 0, 2**16 - 1)
    byte1 = code // 2**8
    byte2 = code % 2**8
    return bytes([byte1, byte2])


def twocomplement_to_decimal(msb, middlebyte, lsb):
    """Convert a 22-bit two-complement ADC value consisting of three bytes to a signed integer (see MCP3550 datasheet for details)."""
    ovh = (msb > 63) and (msb < 128)  # Check for overflow high (B22 set)
    ovl = (msb > 127)  # Check for overflow low (B23 set)
    combined_value = (msb % 64)*2**16+middlebyte*2**8 + \
        lsb  # Get rid of overflow bits
    if not ovh and not ovl:
        if msb > 31:  # B21 set -> negative number
            answer = combined_value - 2**22
        else:
            answer = combined_value
    else:  # overflow
        if msb > 127:  # B23 set -> negative number
            answer = combined_value - 2**22
        else:
            answer = combined_value
    return answer


def dac_bytes_to_decimal(dac_bytes):
    """Convert three data bytes in the DAC1220 format to a 20-bit number ranging from -2**19 to 2**19-1."""
    code = 2**12*dac_bytes[0]+2**4*dac_bytes[1]+dac_bytes[2]/2**4
    return code - 2**19


def send_command(dev, main_window, command_string, expected_response, log_msg=None):
    """Send a command string to the USB device and check the response; optionally logs a message to the message log."""
    if dev is not None:  # Make sure it's connected
        dev.write(0x01, command_string)  # 0x01 = write address of EP1
        response = bytes(dev.read(0x81, 64))  # 0x81 = read address of EP1
        if response != expected_response:
            QtGui.QMessageBox.critical(main_window, "Unexpected Response", "<font color=\"White\">The command \"%s\" resulted in an unexpected response. The expected response was \"%s\"; the actual response was \"%s\"" % (
                command_string, expected_response.decode("ascii"), response.decode("ascii")))
            main_window.setStyleSheet("color: black;  background-color: black")
        return True
    else:
        # not_connected_errormessage()
        return False


def set_cell_status(dev, main_window, cell_on_boolean):
    """Switch the cell connection (True = cell on, False = cell off)."""
    if cell_on_boolean:
        if send_command(dev, main_window, b'CELL ON', b'OK'):
            main_window.cell_status_monitor.setText("CELL ON")
            return
    else:
        if send_command(dev, main_window, b'CELL OFF', b'OK'):
            main_window.cell_status_monitor.setText("CELL OFF")
            return


def set_control_mode(dev, main_window, galvanostatic_boolean):
    """Switch the control mode (True = galvanostatic, False = potentiostatic)."""
    if galvanostatic_boolean:
        if send_command(dev, main_window, b'GALVANOSTATIC', b'OK'):
            main_window.control_mode_monitor.setText("GALVANOSTATIC")
            return
    else:
        if send_command(dev, main_window, b'POTENTIOSTATIC', b'OK'):
            main_window.control_mode_monitor.setText("POTENTIOSTATIC")
            return


def set_offset(dev, main_window, current_offset, potential_offset):
    """Save offset values to the device's flash memory."""
    send_command(dev, main_window, b'OFFSETSAVE '+decimal_to_dac_bytes(potential_offset) +
                 decimal_to_dac_bytes(current_offset), b'OK', "Offset values saved to flash memory.")


def not_connected_errormessage(main_window):
    """Generate an error message stating that the device is not connected."""
    main_window.setStyleSheet("color: white;  background-color: black")
    QtGui.QMessageBox.critical(main_window, "Not connected",
                               "This command cannot be executed because the USB device is not connected. Press the \"Connect\" button and try again.")
    main_window.setStyleSheet("color: black;  background-color: black")


def get_dac_calibration(dev, main_window):
    """Retrieve DAC calibration values from the device's flash memory."""
    if dev is not None:  # Make sure it's connected
        dev.write(0x01, b'DACCALGET')  # 0x01 = write address of EP1
        response = bytes(dev.read(0x81, 64))  # 0x81 = write address of EP1
        # If no calibration value has been stored, all bits are set
        if response != bytes([255, 255, 255, 255, 255, 255]):
            dac_offset = dac_bytes_to_decimal(response[0:3])
            dac_gain = dac_bytes_to_decimal(response[3:6])+2**19
            main_window.calibration_window.dac_offset_input.setText(
                "%d" % dac_offset)
            main_window.calibration_window.dac_gain_input.setText(
                "%d" % dac_gain)
        else:
            print("ERROR get offset")
    else:
        print("Not connected")
        not_connected_errormessage(main_window)


def get_shunt_calibration(dev, main_window, shunt_calibration):
    """Retrieve shunt calibration values from the device's flash memory."""
    if dev is not None:  # Make sure it's connected
        dev.write(0x01, b'SHUNTCALREAD')  # 0x01 = write address of EP1
        response = bytes(dev.read(0x81, 64))  # 0x81 = read address of EP1
        # If no calibration value has been stored, all bits are set
        if response != bytes([255, 255, 255, 255, 255, 255]):
            for i in range(0, 3):
                # Yields an adjustment range from 0.967 to 1.033 in steps of 1 ppm
                shunt_calibration[i] = 1. + \
                    twobytes_to_float(response[2*i:2*i+2])/1e6
                main_window.calibration_window.R[i].setText(
                    "%.4f" % shunt_calibration[i])
    else:
        # not_connected_errormessage(main_window)
        pass


def set_dac_calibration(dev, main_window):
    """Save DAC calibration values to the DAC and the device's flash memory."""
    try:
        dac_offset = int(
            main_window.calibration_window.dac_offset_input.text())
        # hardware_calibration_dac_offset.setStyleSheet("")
    except ValueError:  # If the input field cannot be interpreted as a number, color it red
        main_window.calibration_window.dac_offset_input.setStyleSheet(
            "QLineEdit { background: red; }")
        return
    try:
        dac_gain = int(main_window.calibration_window.dac_gain_input.text())
        # hardware_calibration_dac_gain.setStyleSheet("")
    except ValueError:  # If the input field cannot be interpreted as a number, color it red
        main_window.calibration_window.dac_gain_input.setStyleSheet(
            "")
        return
    send_command(dev, main_window, b'DACCALSET '+decimal_to_dac_bytes(dac_offset)+decimal_to_dac_bytes(
        dac_gain-2**19), b'OK', "DAC calibration saved to flash memory.")


def set_shunt_calibration(dev, main_window, shunt_calibration):
    """Save shunt calibration values to the device's flash memory."""
    send_command(dev, main_window, b'SHUNTCALSAVE '+float_to_twobytes((shunt_calibration[0]-1.)*1e6)+float_to_twobytes(
        (shunt_calibration[1]-1.)*1e6)+float_to_twobytes((shunt_calibration[2]-1.)*1e6), b'OK', "Shunt calibration values saved to flash memory.")
