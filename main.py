import os
import sys

from PyQt5.QtWidgets import *
# from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5 import uic, QtOpenGL, QtGui
import numpy
import pyqtgraph as pg
import random
import copy
import usb
import time
import platform
import timeit
import collections
import scipy.integrate

# pg.setConfigOption('background', 'w')
pg.setConfigOptions(foreground="#e5e5e5", background="#00304f")

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

LIST_TECHNIQUES = [
    "Charge/disch",
    "Rate testing",
    "Cyclic voltammetry"
]
usb_vid = "0xa0a0"  # Default USB vendor ID, can also be adjusted in the GUI
usb_pid = "0x0002"  # Default USB product ID, can also be adjusted in the GUI
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
# cv_parameters = {}  # Dictionary to hold the CV parameters
# cd_parameters = {}  # Dictionary to hold the charge/discharge parameters
# rate_parameters = {}  # Dictionary to hold the rate testing parameters
# Global counters used for automatic current ranging
overcounter, undercounter, skipcounter = 0, 0, 0
time_of_last_adcread = 0.
adcread_interval = 0.09  # ADC sampling interval (in seconds)
# Enable logging of potential and current in idle mode (can be adjusted in the GUI)
logging_enabled = False
# usb_connected = False
start_stop = 1
stop = 0

if platform.system() != "Windows":
    # On Linux/OSX, use the Qt timer
    busyloop_interval = 0
    qt_timer_period = 1e3*adcread_interval  # convert to ms
else:
    # On MS Windows, system timing is inaccurate, so use a busy loop instead
    busyloop_interval = adcread_interval
    qt_timer_period = 0


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


def check_state(desired_states):
    """Check if the current state is in a given list. If so, return True; otherwise, show an error message and return False."""
    if state not in desired_states:
        return False
    else:
        return True


state = States.NotConnected  # Initial state


def set_cell_status(cell_on_boolean):
    """Switch the cell connection (True = cell on, False = cell off)."""
    if cell_on_boolean:
        if send_command(b'CELL ON', b'OK'):
            return
            # cell_status_monitor.setText("CELL ON")
    else:
        if send_command(b'CELL OFF', b'OK'):
            return
            # cell_status_monitor.setText("CELL OFF")


def set_control_mode(galvanostatic_boolean):
    """Switch the control mode (True = galvanostatic, False = potentiostatic)."""
    if galvanostatic_boolean:
        if send_command(b'GALVANOSTATIC', b'OK'):
            return
            # control_mode_monitor.setText("GALVANOSTATIC")
    else:
        if send_command(b'POTENTIOSTATIC', b'OK'):
            return
            # control_mode_monitor.setText("POTENTIOSTATIC")


def connect_disconnect_usb():
    """Toggle the USB device between connected and disconnected states."""
    global dev, state
    if dev is not None:  # If the device is already connected, then this function should disconnect it
        usb.util.dispose_resources(dev)
        dev = None
        state = States.NotConnected
        main_window.usb_connect.setText("Connect")
        # log_message("USB Interface disconnected.")
        return

    # Otherwise, try to connect
    usb_vid_string = str(main_window.text_vid.text())
    usb_pid_string = str(main_window.text_pid.text())
    dev = usb.core.find(idVendor=int(usb_vid_string, 0),
                        idProduct=int(usb_pid_string, 0))
    if dev is None:
        print("USB Device Not Found, No USB device was found with VID %s and PID %s. Verify the vendor/product ID and check the USB connection." %
              (usb_vid_string, usb_pid_string))
    else:
        main_window.usb_connect.setText("Disconnect")
        # log_message("USB Interface connected.")
        try:
            main_window.label_manufacture.setText(
                "Manufacture:   %s" % (dev.manufacturer))
            main_window.label_product.setText("Product:   %s" % (dev.product))
            main_window.label_serial.setText(
                "Serial #:   %s" % (dev.serial_number))

            # hardware_device_info_text.setText("Manufacturer: %s\nProduct: %s\nSerial #: %s" % (
            #     dev.manufacturer, dev.product, dev.serial_number))
            get_calibration()
            set_cell_status(False)  # Cell off
            set_control_mode(False)  # Potentiostatic control
            set_current_range()  # Read current range from GUI
            state = States.Idle_Init  # Start idle mode
        except ValueError:
            print("### Error USB")
            pass  # In case the device is not yet calibrated


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


def dac_bytes_to_decimal(dac_bytes):
    """Convert three data bytes in the DAC1220 format to a 20-bit number ranging from -2**19 to 2**19-1."""
    code = 2**12*dac_bytes[0]+2**4*dac_bytes[1]+dac_bytes[2]/2**4
    return code - 2**19


def get_offset():
    """Retrieve offset values from the device's flash memory."""
    global potential_offset, current_offset
    if dev is not None:  # Make sure it's connected
        dev.write(0x01, b'OFFSETREAD')  # 0x01 = write address of EP1
        response = bytes(dev.read(0x81, 64))  # 0x81 = read address of EP1
        # If no offset value has been stored, all bits will be set
        if response != bytes([255, 255, 255, 255, 255, 255]):
            potential_offset = dac_bytes_to_decimal(response[0:3])
            current_offset = dac_bytes_to_decimal(response[3:6])
            main_window.pot_offset.setText("%d" % potential_offset)
            main_window.curr_offset.setText("%d" % current_offset)
        else:
            print("ERROR get offset")
    else:
        print("Not connected")


def get_dac_calibration():
    """Retrieve DAC calibration values from the device's flash memory."""
    if dev is not None:  # Make sure it's connected
        dev.write(0x01, b'DACCALGET')  # 0x01 = write address of EP1
        response = bytes(dev.read(0x81, 64))  # 0x81 = write address of EP1
        # If no calibration value has been stored, all bits are set
        if response != bytes([255, 255, 255, 255, 255, 255]):
            dac_offset = dac_bytes_to_decimal(response[0:3])
            dac_gain = dac_bytes_to_decimal(response[3:6])+2**19
            main_window.dac_offset.setText("%d" % dac_offset)
            main_window.dac_gain.setText("%d" % dac_gain)
        else:
            print("ERROR get offset")
    else:
        print("Not connected")


def not_connected_errormessage():
    """Generate an error message stating that the device is not connected."""
    main_window.setStyleSheet("color: white;  background-color: black")
    QtGui.QMessageBox.critical(main_window, "Not connected",
                               "This command cannot be executed because the USB device is not connected. Press the \"Connect\" button and try again.")
    main_window.setStyleSheet("color: black;  background-color: black")


def get_shunt_calibration():
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
    else:
        # not_connected_errormessage()
        pass


def get_calibration():
    """Retrieve all calibration values from the device's flash memory."""
    get_dac_calibration()
    get_offset()
    get_shunt_calibration()


def set_current_range():
    """Switch the current range based on the GUI dropdown selection."""
    global currentrange
    index = main_window.current_range_box.currentIndex()
    currentrange = index


def send_command(command_string, expected_response, log_msg=None):
    """Send a command string to the USB device and check the response; optionally logs a message to the message log."""
    if dev is not None:  # Make sure it's connected
        dev.write(0x01, command_string)  # 0x01 = write address of EP1
        response = bytes(dev.read(0x81, 64))  # 0x81 = read address of EP1
        if response != expected_response:
            QtGui.QMessageBox.critical(main_window, "Unexpected Response", "The command \"%s\" resulted in an unexpected response. The expected response was \"%s\"; the actual response was \"%s\"" % (
                command_string, expected_response.decode("ascii"), response.decode("ascii")))
        return True
    else:
        # not_connected_errormessage()
        return False


def set_output(value_units_index, value):
    """Output data to the DAC; units can be either V (index 0), mA (index 1), or raw counts (index 2)."""
    if value_units_index == 0:
        send_command(b'DACSET '+decimal_to_dac_bytes(value/8.*2. **
                                                     19+int(round(potential_offset/4.))), b'OK')
    elif value_units_index == 1:
        send_command(b'DACSET '+decimal_to_dac_bytes(value/(25. /
                                                            (shunt_calibration[currentrange]*100.**currentrange))*2.**19+int(round(current_offset/4.))), b'OK')
    elif value_units_index == 2:
        send_command(b'DACSET '+decimal_to_dac_bytes(value), b'OK')


def wait_for_adcread():
    """Wait for the duration specified in the busyloop_interval."""
    if busyloop_interval == 0:
        return  # On Linux/Mac, system timing is used instead of the busyloop
    else:
        # Sleep for some time to prevent wasting too many CPU cycles
        time.sleep(busyloop_interval/2.)
        app.processEvents()  # Update the GUI
        while timeit.default_timer() < time_of_last_adcread + busyloop_interval:
            # Busy loop (this is the only way to get accurate timing on MS Windows)
            pass


def read_potential_current():
    """Read the most recent potential and current values from the device's ADC."""
    global potential, current, raw_potential, raw_current, time_of_last_adcread
    wait_for_adcread()
    time_of_last_adcread = timeit.default_timer()
    dev.write(0x01, b'ADCREAD')  # 0x01 = write address of EP1
    response = bytes(dev.read(0x81, 64))  # 0x81 = read address of EP1
    if response != b'WAIT':  # 'WAIT' is received if a conversion has not yet finished
        raw_potential = twocomplement_to_decimal(
            response[0], response[1], response[2])
        raw_current = twocomplement_to_decimal(
            response[3], response[4], response[5])
        potential = (raw_potential-potential_offset)/2097152. * \
            8.  # Calculate potential in V, compensating for offset
        # Calculate current in mA, taking current range into account and compensating for offset
        current = (raw_current-current_offset)/2097152.*25. / \
            (shunt_calibration[currentrange]*100.**currentrange)
        # potential_monitor.setText(potential_to_string(potential))
        # current_monitor.setText(current_to_string(currentrange, current))
        # # If enabled, all measurements are appended to an output file (even in idle mode)
        # if logging_enabled:
        #     try:
        #         # Output tab-separated data containing time (in s), potential (in V), and current (in A)
        #         print("%.2f\t%e\t%e" % (time_of_last_adcread, potential,
        #                                 current*1e-3), file=open(hardware_log_filename.text(), 'a', 1))
        #     except:
        #         QtGui.QMessageBox.critical(
        #             mainwidget, "Logging error!", "Logging error!")
        #         # Disable logging in case of file errors
        #         hardware_log_checkbox.setChecked(False)


def idle_init():
    """Perform some necessary initialization before entering the Idle state."""
    global potential_plot_curve, current_plot_curve, legend, state
    main_window.dynamicPlt.clear()
    try:
        legend.scene().removeItem(legend)  # Remove any previous legends
    except AttributeError:
        pass  # In case the legend was already removed
    except NameError:
        pass  # In case a legend has never been created
    main_window.dynamicPlt.setLabel('bottom', 'Sample #', units="")
    main_window.dynamicPlt.setLabel('left', 'Value', units="")
    main_window.dynamicPlt.enableAutoRange()
    main_window.dynamicPlt.setXRange(0, 200, update=True)
    legend = main_window.dynamicPlt.addLegend(size=(5, 20), offset=(10, 10))
    potential_plot_curve = main_window.dynamicPlt.plot(
        pen='g', name='Potential (V)')
    current_plot_curve = main_window.dynamicPlt.plot(
        pen='r', name='Current (mA)')
    state = States.Idle  # Proceed to the Idle state


def update_live_graph():
    """Add newly measured potential and current values to their respective buffers and update the plot curves."""
    last_potential_values.append(potential)
    last_current_values.append(current)
    last_raw_potential_values.append(raw_potential)
    last_raw_current_values.append(raw_current)
    xvalues = range(last_potential_values.maxlen -
                    len(last_potential_values), last_potential_values.maxlen)
    potential_plot_curve.setData(xvalues, list(last_potential_values))
    current_plot_curve.setData(xvalues, list(last_current_values))


def auto_current_range():
    """Automatically switch the current range based on the measured current; returns a number of measurements to skip (to suppress artifacts)."""
    global currentrange, overcounter, undercounter
    relativecurrent = abs(current/(20./100.**currentrange))
    # Switch to higher current range (if possible) after three detections
    if relativecurrent > 1.05 and currentrange != 0:
        overcounter += 1
    else:
        overcounter = 0
    # Switch to lower current range (if possible) after three detections
    if relativecurrent < 0.0095 and currentrange != 2:
        undercounter += 1
    else:
        undercounter = 0
    if overcounter > 3:
        currentrange -= 1
        set_current_range()
        overcounter = 0
        return 2  # Skip next two measurements to suppress artifacts
    elif undercounter > 3:
        currentrange += 1
        set_current_range()
        undercounter = 0
        return 2  # Skip next two measurements to suppress artifacts
    else:
        return 0


# cd_parameters = []
# cv_parameters = []
# rate_parameters = []


def cd_start(cd_parameters):
    global start_stop, cd_charges, cd_currentsetpoint, cd_starttime, cd_currentcycle, cd_time_data, cd_potential_data, cd_current_data, cd_plot_curves, state, cd_outputfile_raw, cd_outputfile_capacities
    # if not start_stop:
    #     start_stop = 1
    #     cd_stop(interrupted=False)
    #     return

    if check_state([States.Idle, States.Stationary_Graph, States.Measuring_start]):
        cd_outputfile_raw = open(cd_parameters['filename'], 'w', 1)
        cd_outputfile_raw.write("Elapsed time(s)\tPotential(V)\tCurrent(A)\n")
        base, extension = os.path.splitext(cd_parameters['filename'])
        cd_outputfile_capacities = open(base+'_capacities'+extension, 'w', 1)
        cd_outputfile_capacities.write(
            "Cycle number\tCharge capacity (Ah)\tDischarge capacity (Ah)\n")
        cd_currentcycle = 1
        cd_charges = []
        cd_plot_curves = []
        cd_currentsetpoint = cd_parameters['chargecurrent']
        set_current_range()
        set_output(1, cd_currentsetpoint)  # Set current to setpoint
        set_control_mode(True)  # Galvanostatic control
        time.sleep(.2)  # Allow DAC some time to settle
        cd_starttime = timeit.default_timer()
        # Holds averaged data for elapsed time
        cd_time_data = AverageBuffer(cd_parameters['numsamples'])
        # Holds averaged data for potential
        cd_potential_data = AverageBuffer(cd_parameters['numsamples'])
        # Holds averaged data for current
        cd_current_data = AverageBuffer(cd_parameters['numsamples'])
        set_cell_status(True)  # Cell on
        try:  # Set up the plotting area
            legend.scene().removeItem(legend)
        except AttributeError:
            pass
        main_window.dynamicPlt.clear()
        main_window.dynamicPlt.enableAutoRange()
        main_window.dynamicPlt.setLabel(
            'bottom', 'Inserted/extracted charge', units="Ah")
        main_window.dynamicPlt.setLabel('left', 'Potential', units="V")
        cd_plot_curves.append(main_window.dynamicPlt.plot(pen='y'))
        state = States.Measuring_CD
        print("------ start CD")
        # main_window.button_start.setText("Stop")
        # start_stop = 0


def cd_update(cd_parameters):
    """Add a new data point to the charge/discharge measurement (should be called regularly)."""
    global cd_currentsetpoint, cd_currentcycle, state
    elapsed_time = timeit.default_timer()-cd_starttime
    # End of charge/discharge measurements
    # print(elapsed_time)
    if cd_currentcycle > cd_parameters['numcycles'] or elapsed_time > 60*3:
        cd_stop(interrupted=False)
    else:  # Continue charge/discharge measurement process
        read_potential_current()  # Read new potential and current
        cd_time_data.add_sample(elapsed_time)
        cd_potential_data.add_sample(potential)
        cd_current_data.add_sample(1e-3*current)  # Convert mA to A
        # A new average was just calculated
        if len(cd_time_data.samples) == 0 and len(cd_time_data.averagebuffer) > 0:
            cd_outputfile_raw.write("%e\t%e\t%e\n" % (
                cd_time_data.averagebuffer[-1], cd_potential_data.averagebuffer[-1], cd_current_data.averagebuffer[-1]))  # Write it out
            charge = numpy.abs(scipy.integrate.cumtrapz(cd_current_data.averagebuffer,
                                                        cd_time_data.averagebuffer, initial=0.)/3600.)  # Cumulative charge in Ah
            # Update the graph
            cd_plot_curves[cd_currentcycle -
                           1].setData(charge, cd_potential_data.averagebuffer)
        # A potential cut-off has been reached
        if (cd_currentsetpoint > 0 and potential > cd_parameters['ubound']) or (cd_currentsetpoint < 0 and potential < cd_parameters['lbound']):
            # Switch from the discharge phase to the charge phase or vice versa
            if cd_currentsetpoint == cd_parameters['chargecurrent']:
                cd_currentsetpoint = cd_parameters['dischargecurrent']
            else:
                cd_currentsetpoint = cd_parameters['chargecurrent']
            set_current_range()  # Set new current range
            set_output(1, cd_currentsetpoint)  # Set current to setpoint
            # Start a new plot curve and append it to the plot area (keeping the old ones as well)
            cd_plot_curves.append(main_window.dynamicPlt.plot(pen='y'))
            cd_charges.append(numpy.abs(numpy.trapz(
                cd_current_data.averagebuffer, cd_time_data.averagebuffer)/3600.))  # Cumulative charge in Ah
            # Write out the charge and discharge capacities after both a charge and discharge phase (i.e. after cycle 2, 4, 6...)
            if cd_currentcycle % 2 == 0:
                cd_outputfile_capacities.write("%d\t%e\t%e\n" % (
                    cd_currentcycle/2, cd_charges[cd_currentcycle-2], cd_charges[cd_currentcycle-1]))
            # Clear average buffers to prepare them for the next cycle
            for data in [cd_time_data, cd_potential_data, cd_current_data]:
                data.clear()
            cd_currentcycle += 1  # Next cycle


def cd_stop(interrupted=True):
    """Finish the charge/discharge measurement."""
    global state
    if check_state([States.Measuring_CD]):
        # main_window.button_start.setText("Start")
        # state = States.Stationary_Graph
        set_cell_status(False)  # Cell off
        cd_outputfile_raw.close()
        cd_outputfile_capacities.close()
        state = States.Measuring_start
        # preview_cancel_button.show()


def cv_sweep(time_elapsed, ustart, ustop, ubound, lbound, scanrate, n):
    """Generate the potential profile for a cyclic voltammetry sweep.

    Keyword arguments:
    time_elapsed -- the elapsed time
    ustart -- the start potential
    ustop -- the stop potential
    ubound -- the upper potential bound
    lbound -- the lower potential bound
    scanrate -- the scan rate
    n -- the number of scans

    Returns the potential as a function of the elapsed time; if the elapsed time exceeds the end of the CV sweep, returns None.
    """
    if scanrate < 0:  # The rest of the function assumes a positive scan rate; a negative one is handled here by recursion
        try:
            # Re-run the function with inverted potentials and scan rates and invert the result
            return -cv_sweep(time_elapsed, -ustart, -ustop, -lbound, -ubound, -scanrate, n)
        except TypeError:
            return None  # If the result of the inverted function is None, it cannot be inverted, so return None
    # Potential difference to traverse in the initial stage (before potential reaches upper bound)
    srt_0 = ubound-ustart
    # Potential difference to traverse in the "cyclic stage" (repeated scans from upper to lower bound and back)
    srt_1 = (ubound-lbound)*2.*n
    # Potential difference to traverse in the final stage (from upper bound to stop potential)
    srt_2 = abs(ustop-ubound)
    srtime = scanrate*time_elapsed  # Linear potential sweep
    if srtime < srt_0:  # Initial stage
        return ustart+srtime
    elif srtime < srt_0+srt_1:  # Cyclic stage
        srtime = srtime - srt_0
        return lbound + abs((srtime) % (2*(ubound-lbound))-(ubound-lbound))
    elif srtime < srt_0+srt_1+srt_2:  # Final stage
        srtime = srtime - srt_0 - srt_1
        if ustop > ubound:
            return ubound + srtime
        else:
            return ubound - srtime
    else:
        return None  # CV finished


def charge_from_cv(time_arr, current_arr):
    """Integrate current as a function of time to calculate charge between zero crossings."""
    zero_crossing_indices = []
    charge_arr = []
    running_index = 0
    while running_index < len(current_arr):
        counter = 0
        # Iterate over a block of positive currents
        while running_index < len(current_arr) and current_arr[running_index] >= 0.:
            running_index += 1
            counter += 1
        # Check if the block holds at least 10 values (this makes the counting immune to noise around zero crossings)
        if counter >= 10:
            # If so, append the index of the start of the block to the list of zero-crossing indices
            zero_crossing_indices.append(running_index-counter)
        counter = 0
        # Do the same for a block of negative currents
        while running_index < len(current_arr) and current_arr[running_index] <= 0.:
            running_index += 1
            counter += 1
        if counter >= 10:
            zero_crossing_indices.append(running_index-counter)
    for index in range(0, len(zero_crossing_indices)-1):  # Go over all zero crossings
        zc_index1 = zero_crossing_indices[index]  # Start index
        zc_index2 = zero_crossing_indices[index+1]  # End index
        # Integrate current over time using the trapezoid rule, convert coulomb to uAh
        charge_arr.append(numpy.trapz(
            current_arr[zc_index1:zc_index2], time_arr[zc_index1:zc_index2])*1000./3.6)
    return charge_arr


def cv_start(cv_parameters):
    """Initialize the CV measurement."""
    global cv_time_data, cv_potential_data, cv_current_data, cv_plot_curve, cv_outputfile, state, skipcounter
    if check_state([States.Idle, States.Stationary_Graph, States.Measuring_start]):
        cv_outputfile = open(cv_parameters['filename'], 'w', 1)
        cv_outputfile.write("Elapsed time(s)\tPotential(V)\tCurrent(A)\n")
        set_output(0, cv_parameters['startpot'])
        set_control_mode(False)
        set_current_range()
        time.sleep(.1)  # Allow DAC some time to settle
        # Holds averaged data for elapsed time
        cv_time_data = AverageBuffer(cv_parameters['numsamples'])
        # Holds averaged data for potential
        cv_potential_data = AverageBuffer(cv_parameters['numsamples'])
        # Holds averaged data for current
        cv_current_data = AverageBuffer(cv_parameters['numsamples'])
        set_cell_status(True)
        time.sleep(.1)  # Allow feedback loop some time to settle
        read_potential_current()
        time.sleep(.1)
        # Two reads are necessary because each read actually returns the result of the previous conversion
        read_potential_current()
        set_current_range()
        time.sleep(.1)
        read_potential_current()
        time.sleep(.1)
        read_potential_current()
        set_current_range()
        try:  # Set up the plotting area
            legend.scene().removeItem(legend)
        except AttributeError:
            pass
        main_window.dynamicPlt.clear()
        main_window.dynamicPlt.enableAutoRange()
        main_window.dynamicPlt.setLabel('bottom', 'Potential', units="V")
        main_window.dynamicPlt.setLabel('left', 'Current', units="A")
        cv_plot_curve = main_window.dynamicPlt.plot(
            pen='y')  # Plot CV in yellow
        state = States.Measuring_CV
        skipcounter = 2  # Skip first two data points to suppress artifacts
        cv_parameters['starttime'] = timeit.default_timer()


def cv_update(cv_parameters):
    """Add a new data point to the CV measurement (should be called regularly)."""
    global state, skipcounter
    elapsed_time = timeit.default_timer()-cv_parameters['starttime']
    cv_output = cv_sweep(elapsed_time, cv_parameters['startpot'], cv_parameters['stoppot'],
                         cv_parameters['ubound'], cv_parameters['lbound'], cv_parameters['scanrate'], cv_parameters['numcycles'])
    if cv_output == None:  # This signifies the end of the CV scan
        cv_stop(interrupted=False)
    else:
        set_output(0, cv_output)
        read_potential_current()  # Read new potential and current
        if skipcounter == 0:  # Process new measurements
            cv_time_data.add_sample(elapsed_time)
            cv_potential_data.add_sample(potential)
            cv_current_data.add_sample(1e-3*current)  # Convert from mA to A
            # Check if a new average was just calculated
            if len(cv_time_data.samples) == 0 and len(cv_time_data.averagebuffer) > 0:
                cv_outputfile.write("%e\t%e\t%e\n" % (
                    cv_time_data.averagebuffer[-1], cv_potential_data.averagebuffer[-1], cv_current_data.averagebuffer[-1]))  # Write it out
                cv_plot_curve.setData(
                    cv_potential_data.averagebuffer, cv_current_data.averagebuffer)  # Update the graph
            skipcounter = auto_current_range()  # Update the graph
        else:  # Wait until the required number of data points is skipped
            skipcounter -= 1


def cv_stop(interrupted=True):
    """Finish the CV measurement."""
    global state
    if check_state([States.Measuring_CV]):
        cv_outputfile.close()
        # Integrate current between zero crossings to produce list of inserted/extracted charges
        main_window.dynamicPlt2.clear()
        main_window.dynamicPlt2.enableAutoRange()
        main_window.dynamicPlt2.setLabel('bottom', 'Potential', units="V")
        main_window.dynamicPlt2.setLabel('left', 'Current', units="A")
        cv_plot_curve2 = main_window.dynamicPlt2.plot(
            pen='y')  # Plot CV in yellow
        cv_plot_curve2.setData(
            cv_potential_data.averagebuffer, cv_current_data.averagebuffer)
        charge_arr = charge_from_cv(
            cv_time_data.averagebuffer, cv_current_data.averagebuffer)
        print('----> CV stop')
        # Keep displaying the last plot until the user clicks a button
        state = States.Measuring_start


def rate_start(rate_parameters):
    """Initialize the rate testing measurement."""
    global state, crate_index, rate_halfcycle_countdown, rate_chg_charges, rate_dis_charges, rate_outputfile_raw, rate_outputfile_capacities, rate_starttime, rate_time_data, rate_potential_data, rate_current_data, rate_plot_scatter_chg, rate_plot_scatter_dis, legend
    if check_state([States.Idle, States.Stationary_Graph, States.Measuring_start]):
        print("----start")
        crate_index = 0  # Index in the list of C-rates
        # Holds amount of remaining half cycles
        rate_halfcycle_countdown = 2*rate_parameters['numcycles']
        rate_chg_charges = []  # List of measured charge capacities
        rate_dis_charges = []  # List of measured discharge capacitiesa
        # Apply positive current for odd half cycles (charge phase) and negative current for even half cycles (discharge phase)
        rate_outputfile_raw = open(rate_parameters['filename'], 'w', 1)
        rate_outputfile_raw.write(
            "Elapsed time(s)\tPotential(V)\tCurrent(A)\n")
        base, extension = os.path.splitext(rate_parameters['filename'])
        # This file will contain capacity data for each C-rate
        rate_outputfile_capacities = open(base+'_capacities'+extension, 'w', 1)
        rate_outputfile_capacities.write(
            "C-rate\tCharge capacity (Ah)\tDischarge capacity (Ah)\n")
        rate_current = rate_parameters['currents'][crate_index] if rate_halfcycle_countdown % 2 == 0 else - \
            rate_parameters['currents'][crate_index]
        set_current_range()  # Set new current range
        set_output(1, rate_current)  # Set current to setpoint
        set_control_mode(True)  # Galvanostatic control
        time.sleep(.2)  # Allow DAC some time to settle
        rate_starttime = timeit.default_timer()
        numsamples = max(
            1, int(36./rate_parameters['crates'][crate_index]))
        # Holds averaged data for elapsed time
        rate_time_data = AverageBuffer(numsamples)
        # Holds averaged data for potential
        rate_potential_data = AverageBuffer(numsamples)
        # Holds averaged data for current
        rate_current_data = AverageBuffer(numsamples)
        set_cell_status(True)  # Cell on
        try:  # Set up the plotting area
            legend.scene().removeItem(legend)
        except AttributeError:
            pass
        except NameError:
            pass  # In case a legend has never been created
        main_window.dynamicPlt.clear()
        legend = main_window.dynamicPlt.addLegend()
        main_window.dynamicPlt.enableAutoRange()
        main_window.dynamicPlt.setLabel('bottom', 'C-rate')
        main_window.dynamicPlt.setLabel(
            'left', 'Inserted/extracted charge', units="Ah")
        # Plot charge capacity as a function of C-rate with red circles
        print('--------')
        rate_plot_scatter_chg = main_window.dynamicPlt.plot(
            symbol='o', pen=None, symbolPen='r', symbolBrush='r', name='Charge')
        rate_plot_scatter_dis = main_window.dynamicPlt.plot(symbol='o', pen=None, symbolPen=(100, 100, 255), symbolBrush=(
            100, 100, 255), name='Discharge')  # Plot discharge capacity as a function of C-rate with blue circles
        state = States.Measuring_Rate


def rate_update(rate_parameters):
    """Add a new data point to the rate testing measurement (should be called regularly)."""
    global state, crate_index, rate_halfcycle_countdown
    elapsed_time = timeit.default_timer()-rate_starttime
    read_potential_current()
    rate_time_data.add_sample(elapsed_time)
    rate_potential_data.add_sample(potential)
    rate_current_data.add_sample(1e-3*current)  # Convert mA to A
    # A new average was just calculated
    if len(rate_time_data.samples) == 0 and len(rate_time_data.averagebuffer) > 0:
        rate_outputfile_raw.write("%e\t%e\t%e\n" % (
            rate_time_data.averagebuffer[-1], rate_potential_data.averagebuffer[-1], rate_current_data.averagebuffer[-1]))  # Write it out
    # A potential cut-off has been reached
    if (rate_halfcycle_countdown % 2 == 0 and potential > rate_parameters['ubound']) or (rate_halfcycle_countdown % 2 != 0 and potential < rate_parameters['lbound']):
        rate_halfcycle_countdown -= 1
        print("--1")
        if rate_halfcycle_countdown == 1:  # Last charge cycle for this C-rate, so calculate and plot the charge capacity
            charge = numpy.abs(scipy.integrate.trapz(
                rate_current_data.averagebuffer, rate_time_data.averagebuffer)/3600.)  # Charge in Ah
            rate_chg_charges.append(charge)
            rate_plot_scatter_chg.setData(
                rate_parameters['crates'][0:crate_index+1], rate_chg_charges)
            print("--2")
        elif rate_halfcycle_countdown == 0:  # Last discharge cycle for this C-rate, so calculate and plot the discharge capacity, and go to the next C-rate
            charge = numpy.abs(scipy.integrate.trapz(
                rate_current_data.averagebuffer, rate_time_data.averagebuffer)/3600.)  # Charge in Ah
            rate_dis_charges.append(charge)
            rate_plot_scatter_dis.setData(
                rate_parameters['crates'][0:crate_index+1], rate_dis_charges)
            rate_outputfile_capacities.write("%e\t%e\t%e\n" % (
                rate_parameters['crates'][crate_index], rate_chg_charges[-1], rate_dis_charges[-1]))
            # Last C-rate was measured
            if crate_index == len(rate_parameters['crates'])-1:
                rate_stop(interrupted=False)
                print("--3")
                return
            else:  # New C-rate
                print('--4')
                crate_index += 1
                # Set the amount of remaining half cycles for the new C-rate
                rate_halfcycle_countdown = 2 * \
                    rate_parameters['numcycles']
                set_current_range()  # Set new current range
                # Set an appropriate amount of samples to average for the new C-rate; results in approx. 1000 points per curve
                numsamples = max(
                    1, int(36./rate_parameters['crates'][crate_index]))
                for data in [rate_time_data, rate_potential_data, rate_current_data]:
                    data.number_of_samples_to_average = numsamples
        # Apply positive current for odd half cycles (charge phase) and negative current for even half cycles (discharge phase)
        rate_current = rate_parameters['currents'][crate_index] if rate_halfcycle_countdown % 2 == 0 else - \
            rate_parameters['currents'][crate_index]
        set_output(1, rate_current)  # Set current to setpoint
        # Clear average buffers to prepare them for the next cycle
        for data in [rate_time_data, rate_potential_data, rate_current_data]:
            data.clear()


def rate_stop(interrupted=True):
    """Finish the rate testing measurement."""
    global state
    if check_state([States.Measuring_Rate]):
        # Keep displaying the last plot until the user clicks a button
        set_cell_status(False)
        rate_outputfile_raw.close()
        rate_outputfile_capacities.close()
        state = States.Measuring_start


queue_measure = []
id_ = 0
para_run = {}


def start():
    global state, start_stop, stop
    if state == States.NotConnected:
        not_connected_errormessage()
    elif state != States.NotConnected and start_stop:
        state = States.Measuring_start
        main_window.button_start.setText('Stop')
        start_stop = 0
    elif stop:
        stop = 0
        main_window.button_start.setText('Stop')
        return
    else:
        main_window.button_start.setText('Start')
        stop = 1
        # start_stop = 1
    print('----state', state)


def validate_file(filename):
    """Check if a filename can be written to. If so, return True."""
    main_window.setStyleSheet("color: white;  background-color: black")
    if os.path.isfile(filename):
        if QtGui.QMessageBox.question(main_window, "File exists", "<font color=\"White\">The specified output file already exists. Do you want to overwrite it?", QtGui.QMessageBox.Yes | QtGui.QMessageBox.No, QtGui.QMessageBox.No) != QtGui.QMessageBox.Yes:
            main_window.setStyleSheet("color: black;  background-color: black")
            return False
    try:
        tryfile = open(filename, 'w', 1)
        tryfile.close()
        main_window.setStyleSheet("color: black;  background-color: black")
        return True
    except IOError:
        QtGui.QMessageBox.critical(
            main_window, "File error", "<font color=\"White\">The specified output file path is not valid.")
        main_window.setStyleSheet("color: black;  background-color: black")
        return False


class Frame(QPushButton):
    def __init__(self, parent):
        super(Frame, self).__init__(parent)
        self.check_move = 0
        self.check_stack = 0  # Check frame is on stack list or not
        self.index_table = 0
        self.index_line = 0
        self.setMouseTracking(True)
        self.index_measure = 0
        self.parameters = {}

    def mousePressEvent(self, e):
        self.check_move = 1

    def mouseReleaseEvent(self, e):
        global queue_measure, index_cd, index_cv, index_rate
        if (main_window.frame_y.pos().y()-50 < self.pos().y() < main_window.frame_y.pos().y()+50) and self.check_stack == 0:
            self.check_move = 0
            self.check_stack = 1
            pos_x_line = main_window.button_refresh.pos(
            ).x() + main_window.button_refresh.width()
            pos_y_line = main_window.frame_y.pos().y()
            self.resize(120, main_window.frame_y.height())
            # self.setStyleSheet(
            #     "background-color: #202932;")
            self.move(pos_x_line + main_window.status_line*120, pos_y_line)
            main_window.status_line += 1
            # main_window.status_table -= 1
            self.index_line = main_window.status_line
            # if self.index_measure == 0:
            #     queue_measure.append({"index": index_cd, "type": "cd"})
            #     index_cd += 1
            # elif self.index_measure == 1:
            #     queue_measure.append({"index": index_rate, "type": "rate"})
            #     index_rate += 1
            # elif self.index_measure == 2:
            #     queue_measure.append({"index": index_cv, "type": "cv"})
            #     index_cv += 1
            if self.parameters:
                queue_measure.append(self.parameters)
                print('----- > queue_measure', queue_measure)
        else:
            if self.parameters:
                for queue_measure_ in queue_measure:
                    if queue_measure_['id'] == self.parameters['id']:
                        queue_measure.remove(queue_measure_)
                        print('----- > queue_measure remove', queue_measure)
                self.check_move = 0
                self.check_stack = 0
                self.resize(80, 61)
                if self.index_line:
                    main_window.status_line -= 1
                    self.index_line = 0
                # self.setStyleSheet("background-color: #181818;")
                self.move(main_window.x_axis[int(self.index_table % ADD_TABLE_SIZE[1])],
                          main_window.y_axis[int(self.index_table / ADD_TABLE_SIZE[1])])
            else:
                self.check_move = 0
                self.check_stack = 0
                self.resize(80, 61)
                if self.index_line:
                    main_window.status_line -= 1
                    self.index_line = 0
                # self.setStyleSheet("background-color: #181818;")
                self.move(main_window.x_axis[int(self.index_table % ADD_TABLE_SIZE[1])],
                          main_window.y_axis[int(self.index_table / ADD_TABLE_SIZE[1])])

    def frame_refresh(self):
        self.check_move = 0
        self.check_stack = 0
        self.resize(80, 61)
        if self.index_line:
            main_window.status_line -= 1
            self.index_line = 0
        # self.setStyleSheet("background-color: #181818;")
        self.move(main_window.x_axis[int(self.index_table % ADD_TABLE_SIZE[1])],
                  main_window.y_axis[int(self.index_table / ADD_TABLE_SIZE[1])])


def refresh():
    global state, start_stop, stop, queue_measure
    stop = 0
    start_stop = 1
    main_window.button_start.setText('Start')
    state = States.Idle_Init
    queue_measure = []
    frames = main_window.main_widget.findChildren(Frame)
    for frame in frames:
        if frame.check_stack:
            frame.frame_refresh()


class create(QMainWindow):
    def __init__(self, parent=None):
        super(create, self).__init__(parent)
        uic.loadUi('./create_window.ui', self)
        self.setFixedSize(305, 543)
        self.option = self.findChild(QComboBox, 'comboBox')
        self.option.addItems(LIST_TECHNIQUES)

        self.button_cancel = self.findChild(QPushButton, 'button_cancel')
        self.button_cancel.clicked.connect(self.exit_window)

        self.button_add = self.findChild(QPushButton, 'button_add')
        self.button_add.clicked.connect(self.add)

        self.save_button = self.findChild(QPushButton, 'choose_file')
        self.save_button.clicked.connect(self.choose_file_)
        self.save_path = self.findChild(QLineEdit, 'save_path')

        self.frame_0 = self.findChild(QFrame, 'charge_disch')
        self.frame_1 = self.findChild(QFrame, 'rate_testing')
        self.frame_2 = self.findChild(QFrame, 'cyclic_voltammetry')

        self.cd_ubound = self.findChild(QLineEdit, 'cd_ubound')
        self.cd_chargecurrent = self.findChild(QLineEdit, 'cd_chargecurrent')
        self.cd_dischargecurrent = self.findChild(
            QLineEdit, 'cd_dischargecurrent')
        self.cd_numsamples = self.findChild(QLineEdit, 'cd_numsamples')
        self.cd_numcycles = self.findChild(QLineEdit, 'cd_numcycles')
        self.cd_lbound = self.findChild(QLineEdit, 'cd_lbound')

        self.cv_ubound = self.findChild(QLineEdit, 'cv_ubound')
        self.cv_startpot = self.findChild(QLineEdit, 'cv_startpot')
        self.cv_stoppot = self.findChild(
            QLineEdit, 'cv_stoppot')
        self.cv_numsamples = self.findChild(QLineEdit, 'cv_numsamples')
        self.cv_scanrate = self.findChild(QLineEdit, 'cv_scanrate')
        self.cv_numcycles = self.findChild(QLineEdit, 'cv_numcycles')
        self.cv_lbound = self.findChild(QLineEdit, 'cv_lbound')

        self.rate_lbound = self.findChild(QLineEdit, 'rate_lbound')
        self.rate_ubound = self.findChild(QLineEdit, 'rate_ubound')
        self.rate_one_c_current = self.findChild(
            QLineEdit, 'rate_one_c_current')
        self.rate_crates = self.findChild(QLineEdit, 'rate_crates')
        self.rate_crates.setText("1, 2, 5, 10, 20, 50, 100")
        self.rate_numcycles = self.findChild(QLineEdit, 'rate_numcycles')

        self.cd_parameter = {}
        self.cv_parameter = {}
        self.rate_parameter = {}

        self.cd_parameter['filename'] = './save/{}_{}.txt'.format(
            'cd', str(time.time()))
        self.cv_parameter['filename'] = './save/{}_{}.txt'.format(
            'cv', str(time.time()))
        self.rate_parameter['filename'] = './save/{}_{}.txt'.format(
            'rate', str(time.time()))

        self.index = 0

        self.frame_1.hide()
        self.frame_2.hide()
        self.save_path.setText(self.cd_parameter['filename'])

        self.option.activated.connect(self.do_something)

    def cv_validate_parameters(self):
        if self.cv_parameter['ubound'] < self.cv_parameter['lbound']:
            QtGui.QMessageBox.critical(
                self, "CV error", "<font color=\"White\">The upper bound cannot be lower than the lower bound.")
            return False
        if self.cv_parameter['scanrate'] == 0:
            QtGui.QMessageBox.critical(
                self, "CV error", "<font color=\"White\">The scan rate cannot be zero.")
            return False
        if (self.cv_parameter['scanrate'] > 0) and (self.cv_parameter['ubound'] < self.cv_parameter['startpot']):
            QtGui.QMessageBox.critical(
                self, "CV error", "<font color=\"White\">For a positive scan rate, the start potential must be lower than the upper bound.")
            return False
        if (self.cv_parameter['scanrate'] < 0) and (self.cv_parameter['lbound'] > self.cv_parameter['startpot']):
            QtGui.QMessageBox.critical(
                self, "CV error", "<font color=\"White\">For a negative scan rate, the start potential must be higher than the lower bound.")
            return False
        if self.cv_parameter['numsamples'] < 1:
            QtGui.QMessageBox.critical(
                self, "CV error", "<font color=\"White\">The number of samples to average must be at least 1.")
            return False
        return True

    def cd_validate_parameters(self):
        """Check if the chosen charge/discharge parameters make sense. If so, return True."""
        if self.cd_parameter['ubound'] < self.cd_parameter['lbound']:
            QtGui.QMessageBox.critical(self, "Charge/discharge error",
                                       "<font color=\"White\">The upper bound cannot be lower than the lower bound.")
            return False
        if self.cd_parameter['chargecurrent'] == 0.:
            QtGui.QMessageBox.critical(
                self, "Charge/discharge error", "<font color=\"White\">The charge current cannot be zero.")
            return False
        if self.cd_parameter['dischargecurrent'] == 0.:
            QtGui.QMessageBox.critical(
                self, "Charge/discharge error", "<font color=\"White\">The discharge current cannot be zero.")
            return False
        if self.cd_parameter['chargecurrent']*self.cd_parameter['dischargecurrent'] > 0:
            QtGui.QMessageBox.critical(self, "Charge/discharge error",
                                       "<font color=\"White\">Charge and discharge current must have opposite sign.")
            return False
        if self.cd_parameter['numcycles'] <= 0:
            QtGui.QMessageBox.critical(self, "Charge/discharge error",
                                       "<font color=\"White\">The number of half cycles must be positive and non-zero.")
            return False
        if self.cd_parameter['numsamples'] < 1:
            QtGui.QMessageBox.critical(self, "Charge/discharge error",
                                       "<font color=\"White\">The number of samples to average must be at least 1.")
            return False
        return True

    def rate_validate_parameters(self):
        """Check if the chosen charge/discharge parameters make sense. If so, return True."""
        if self.rate_parameter['ubound'] < self.rate_parameter['lbound']:
            QtGui.QMessageBox.critical(self, "Rate testing error",
                                       "<font color=\"White\">The upper bound cannot be lower than the lower bound.")
            return False
        if 0. in self.rate_parameter['currents']:
            QtGui.QMessageBox.critical(
                self, "Rate testing error", "<font color=\"White\">The charge/discharge current cannot be zero.")
            return False
        if self.rate_parameter['numcycles'] <= 0:
            QtGui.QMessageBox.critical(self, "Charge/discharge error",
                                       "<font color=\"White\">The number of half cycles must be positive and non-zero.")
            return False
        return True

    def choose_file_(self):
        """Open a file dialog and write the path of the selected file to a given entry field."""
        filedialog = QtGui.QFileDialog()
        self.setStyleSheet("color: white;  background-color: black")
        if self.index == 0:
            tuple_file = filedialog.getSaveFileName(
                self, "Choose where to save the charge/discharge measurement data", "", "ASCII data (*.txt)", options=QtGui.QFileDialog.DontConfirmOverwrite)
            file_name = tuple_file[0]
            self.cd_parameter['filename'] = file_name
            self.save_path.setText(self.cd_parameter['filename'])
        elif self.index == 1:
            tuple_file = filedialog.getSaveFileName(
                self, "Choose where to save the rate testing measurement data", "", "ASCII data (*.txt)", options=QtGui.QFileDialog.DontConfirmOverwrite)
            file_name = tuple_file[0]
            self.rate_parameter['filename'] = file_name
            self.save_path.setText(self.rate_parameter['filename'])
        elif self.index == 2:
            tuple_file = filedialog.getSaveFileName(
                self, "Choose where to save the CV measurement data", "", "ASCII data (*.txt)", options=QtGui.QFileDialog.DontConfirmOverwrite)
            file_name = tuple_file[0]
            self.cv_parameter['filename'] = file_name
            self.save_path.setText(self.cv_parameter['filename'])
        # file_entry_field.setText(file_name)
        self.setStyleSheet("color: black;  background-color: black")

        # return file_name

    def do_something(self, index):
        if (index == 0):
            self.frame_1.hide()
            self.frame_2.hide()
            self.frame_0.show()
            self.index = index
            self.save_path.setText(self.cd_parameter['filename'])
        elif (index == 1):
            self.frame_0.hide()
            self.frame_2.hide()
            self.frame_1.show()
            self.index = index
            self.save_path.setText(self.rate_parameter['filename'])
        else:
            self.frame_0.hide()
            self.frame_1.hide()
            self.frame_2.show()
            self.index = index
            self.save_path.setText(self.cv_parameter['filename'])

    def get_para(self, index):
        if index == 0:
            try:
                self.cd_parameter['lbound'] = float(self.cd_lbound.text())
                self.cd_parameter['ubound'] = float(self.cd_ubound.text())
                self.cd_parameter['chargecurrent'] = float(
                    self.cd_chargecurrent.text())/1e3
                self.cd_parameter['dischargecurrent'] = float(
                    self.cd_dischargecurrent.text())/1e3
                self.cd_parameter['numcycles'] = int(self.cd_numcycles.text())
                self.cd_parameter['numsamples'] = int(
                    self.cd_numsamples.text())
                # self.cd_parameter['filename'] = choose_file(
                #     "Choose where to save the charge/discharge measurement data")
                if self.cd_validate_parameters() and validate_file(self.cd_parameter['filename']):
                    parameters = {'id': id_, 'type': 'cd',
                                  'value': self.cd_parameter}
                    return parameters
                else:
                    return False
            except ValueError:
                self.exit_window()
                return False
        elif index == 1:
            try:
                self.rate_parameter['lbound'] = float(self.rate_lbound.text())
                self.rate_parameter['ubound'] = float(self.rate_ubound.text())
                self.rate_parameter['one_c_current'] = float(
                    self.rate_one_c_current.text())/1e3
                self.rate_parameter['numcycles'] = int(
                    self.rate_numcycles.text())
                self.rate_parameter['crates'] = [
                    float(x) for x in self.rate_crates.text().split(",")]
                self.rate_parameter['currents'] = [
                    self.rate_parameter['one_c_current']*rc for rc in self.rate_parameter['crates']]
                self.rate_parameter['numsamples'] = 1
                # self.rate_parameter['filename'] = choose_file(
                #     "Choose where to save the rate testing measurement data")
                if self.rate_validate_parameters() and validate_file(self.rate_parameter['filename']):
                    parameters = {'id': id_, 'type': 'rate',
                                  'value': self.rate_parameter}
                    return parameters
                else:
                    return False
            except ValueError:
                self.exit_window()
                return False
        elif index == 2:
            try:
                self.cv_parameter['lbound'] = float(self.cv_lbound.text())
                self.cv_parameter['ubound'] = float(self.cv_ubound.text())
                self.cv_parameter['startpot'] = float(self.cv_startpot.text())
                self.cv_parameter['stoppot'] = float(self.cv_stoppot.text())
                self.cv_parameter['scanrate'] = float(
                    self.cv_scanrate.text())/1e3
                self.cv_parameter['numcycles'] = int(self.cv_numcycles.text())
                self.cv_parameter['numsamples'] = int(
                    self.cv_numsamples.text())
                # self.cv_parameter['filename'] = choose_file(
                #     "Choose where to save the CV measurement data")
                if self.cv_validate_parameters() and validate_file(self.cv_parameter['filename']):
                    parameters = {'id': id_, 'type': 'cv',
                                  'value': self.cv_parameter}
                    # print(parameters)
                    return parameters
                else:
                    # self.exit_window()
                    return False
            except ValueError:
                self.exit_window()
                return False

    def exit_window(self):
        self.close()

    def add(self):
        global id_
        if main_window.status_table < ADD_TABLE_SIZE[0]*ADD_TABLE_SIZE[1]:
            frame_ = Frame(main_window.main_widget)
            frame_.index_measure = self.option.currentIndex()
            frame_.parameters = self.get_para(
                frame_.index_measure)
            if frame_.parameters:
                id_ += 1
                print('----> frame', frame_.parameters)
                frame_.setStyleSheet("background-color: %s;" %
                                     COLOR_TABLE[frame_.index_measure])
                frame_.setText(LIST_TECHNIQUES[frame_.index_measure])
                frame_.resize(80, 61)
                frame_.index_table = main_window.status_table
                frame_.move(main_window.x_axis[int(main_window.status_table % ADD_TABLE_SIZE[1])],
                            main_window.y_axis[int(main_window.status_table / ADD_TABLE_SIZE[1])])
                main_window.status_table += 1
                frame_.show()
        self.exit_window()


class main(QMainWindow):
    def __init__(self):
        super(main, self).__init__()
        uic.loadUi('./mainwindow.ui', self)
        self.setMouseTracking(True)

        # Create index for album area
        setting_width = self.frame.width()
        addBtn_width = self.create_measure.width()
        addBtn_height = self.create_measure.height()
        gap_col = (setting_width -
                   ADD_TABLE_SIZE[1] * addBtn_width)/(ADD_TABLE_SIZE[1] - 1)
        self.x_axis = [col*(gap_col + addBtn_width)
                       for col in range(ADD_TABLE_SIZE[1])]
        gap_row = 10
        self.y_axis = [self.create_frame.y() + row*(gap_row + addBtn_height)
                       for row in range(ADD_TABLE_SIZE[0])]

        self.main_widget = self.findChild(QWidget, 'main_widget')

        self.usb_connect = self.findChild(QPushButton, 'usb_connect')
        self.usb_connect.clicked.connect(connect_disconnect_usb)

        self.button_start = self.findChild(QPushButton, 'button_start')
        self.button_start.clicked.connect(start)

        self.button_refresh = self.findChild(QPushButton, 'button_refresh')
        self.button_refresh.clicked.connect(refresh)

        self.current_range_set = self.findChild(
            QPushButton, 'current_range_set')
        self.current_range_set.clicked.connect(set_current_range)

        self.current_range_box = self.findChild(QComboBox, 'current_range_box')
        self.current_range_box.addItems(["20 mA", u"200 µA", u"2 µA"])
        self.option2 = self.findChild(QComboBox, 'comboBox_2')
        self.option2.addItems(["Potential (V)", "Current (mA)", "DAC Code"])

        self.dac_offset = self.findChild(QLineEdit, 'dac_offset_input')
        self.dac_gain = self.findChild(QLineEdit, 'dac_gain_input')
        self.pot_offset = self.findChild(QLineEdit, 'pot_offset_input')
        self.curr_offset = self.findChild(QLineEdit, 'curr_offset_input')

        self.text_vid = self.findChild(QLineEdit, 'usb_vid')
        self.text_vid.setText(usb_vid)
        self.text_pid = self.findChild(QLineEdit, 'usb_pid')
        self.text_pid.setText(usb_pid)

        self.label_manufacture = self.findChild(QLabel, 'label_manufacture')
        self.label_product = self.findChild(QLabel, 'label_product')
        self.label_serial = self.findChild(QLabel, 'label_serial')

        self.status_table = 1
        self.status_line = 0
        self.sort_ = 0

        self.index_measure = 0

        # self.frame_x = Frame(self.main_widget)
        # self.frame_x.setStyleSheet("background-color: #181818;")
        # self.frame_x.resize(127, 102)
        # self.frame_x.move(450, 3)

        self.button_create = self.findChild(QPushButton, 'create_measure')
        self.button_create.clicked.connect(self.open_new)

        self.frame_y = self.findChild(QFrame, 'frame_20')
        self.dynamicPlt = pg.PlotWidget(self)

        self.dynamicPlt.move(305, 22)
        self.dynamicPlt.resize(690, 520)

        self.dynamicPlt2 = pg.PlotWidget(self)
        self.dynamicPlt2.move(1000, 22)
        self.dynamicPlt2.resize(370, 520)

        self.timer2 = pg.QtCore.QTimer()
        self.timer2.timeout.connect(self.update)
        self.timer2.start(qt_timer_period)
        self.show()

    def update(self):
        global queue_measure, state, para_run
        if state == States.Idle_Init:
            idle_init()
        elif state == States.Idle:
            read_potential_current()
            update_live_graph()
        elif stop:
            pass
        elif state == States.Measuring_CD and stop == 0:
            cd_update(para_run)
        elif state == States.Measuring_CV and stop == 0:
            cv_update(para_run)
        elif state == States.Measuring_Rate and stop == 0:
            rate_update(para_run)
        elif state == States.Measuring_start and stop == 0:
            if queue_measure:
                print(queue_measure)
                if queue_measure[0]["type"] == "cd":
                    # self.index_measure = queue_measure[0]["index"]
                    cd_start(queue_measure[0]['value'])
                    para_run = queue_measure[0]['value']
                    print("------", queue_measure[0])
                    queue_measure.pop(0)
                elif queue_measure[0]["type"] == "cv":
                    # self.index_measure = queue_measure[0]["index"]
                    cv_start(queue_measure[0]['value'])
                    para_run = queue_measure[0]['value']
                    queue_measure.pop(0)
                elif queue_measure[0]["type"] == "rate":
                    # self.index_measure = queue_measure[0]["index"]
                    rate_start(queue_measure[0]['value'])
                    para_run = queue_measure[0]['value']
                    queue_measure.pop(0)
            else:
                state = States.Stationary_Graph
                self.button_start.setText('Start')

    def open_new(self):
        qt_wid = create(self)
        qt_wid.show()

    def mouseMoveEvent(self, e):
        list_frame = self.findChildren(Frame)
        for frame in list_frame:
            if frame.check_move:
                frame.move(e.x()-50, e.y()-50)

    def mousePressEvent(self, e):
        pass

    def mouseReleaseEvent(self, e):
        pass


app = QApplication(sys.argv)
main_window = main()
main_window.activateWindow()
sys.exit(app.exec_())
app.exec_()
