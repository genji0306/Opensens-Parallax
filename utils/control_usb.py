import collections
from PyQt5 import QtGui
from .calculate import *


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
