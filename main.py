import os
import sys

from PyQt5.QtWidgets import *
# from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5 import uic, QtOpenGL, QtGui
import numpy as np
import pyqtgraph as pg
import random
import copy
import usb
import time
import platform
import timeit
import collections

pg.setConfigOption('background', 'w')

x = [450, 590, 310, 450, 590, 310, 450, 590, 310, 450, 590, 310, 450, 590]
y = [3, 3, 115, 115, 115, 227, 227, 227, 339, 339, 339, 451, 451, 451]
y_size = [110, 230, 350, 470, 590]

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
cv_parameters = {}  # Dictionary to hold the CV parameters
cd_parameters = {}  # Dictionary to hold the charge/discharge parameters
rate_parameters = {}  # Dictionary to hold the rate testing parameters
# Global counters used for automatic current ranging
overcounter, undercounter, skipcounter = 0, 0, 0
time_of_last_adcread = 0.
adcread_interval = 0.09  # ADC sampling interval (in seconds)
# Enable logging of potential and current in idle mode (can be adjusted in the GUI)
logging_enabled = False

if platform.system() != "Windows":
    # On Linux/OSX, use the Qt timer
    busyloop_interval = 0
    qt_timer_period = 1e3*adcread_interval  # convert to ms
else:
    # On MS Windows, system timing is inaccurate, so use a busy loop instead
    busyloop_interval = adcread_interval
    qt_timer_period = 0


class States:
    """Expose a named list of states to be used as a simple state machine."""
    NotConnected, Idle_Init, Idle, Measuring_Offset, Stationary_Graph, Measuring_CV, Measuring_CD, Measuring_Rate = range(
        8)


state = States.NotConnected  # Initial state


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
            # set_cell_status(False)  # Cell off
            # set_control_mode(False)  # Potentiostatic control
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


def get_calibration():
    """Retrieve all calibration values from the device's flash memory."""
    get_dac_calibration()
    get_offset()
    # get_shunt_calibration()


def set_current_range():
    """Switch the current range based on the GUI dropdown selection."""
    global currentrange
    index = main_window.current_range_box.currentIndex()
    currentrange = index


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


class Frame(QPushButton):
    def __init__(self, parent):
        super(Frame, self).__init__(parent)
        self.check_move = 0
        self.index_table = 0
        self.index_line = 0
        self.setMouseTracking(True)
        self.index_measure = 0

    def mousePressEvent(self, e):
        self.check_move = 1

    def mouseReleaseEvent(self, e):
        if (main_window.frame_y.pos().y()-50 < self.pos().y() < main_window.frame_y.pos().y()+50):
            self.check_move = 0
            self.resize(120, 37)
            # self.setStyleSheet(
            #     "background-color: #202932;")
            self.move(y_size[main_window.status_line],
                      main_window.frame_y.pos().y())
            main_window.status_line += 1
            main_window.status_table -= 1
            self.index_line = main_window.status_line
        else:
            self.check_move = 0
            self.resize(127, 102)
            if self.index_line:
                main_window.status_line -= 1
                self.index_line = 0
            # self.setStyleSheet("background-color: #181818;")
            self.move(x[self.index_table], y[self.index_table])


class create(QMainWindow):
    def __init__(self, parent=None):
        super(create, self).__init__(parent)
        uic.loadUi('./mainwindow.ui', self)
        self.setFixedSize(305, 543)
        self.option = self.findChild(QComboBox, 'comboBox')
        self.option.addItems(
            ["Charge/disch", "Rate testing", "Cyclic voltammetry"])

        self.button_cancel = self.findChild(QPushButton, 'button_cancel')
        self.button_cancel.clicked.connect(self.exit_window)

        self.button_add = self.findChild(QPushButton, 'button_add')
        self.button_add.clicked.connect(self.add)

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

        self.cd_parameters = {}

        self.frame_1.hide()
        self.frame_2.hide()

        self.option.activated.connect(self.do_something)

    def do_something(self, index):
        if (index == 0):
            self.frame_1.hide()
            self.frame_2.hide()
            self.frame_0.show()
        elif (index == 1):
            self.frame_0.hide()
            self.frame_2.hide()
            self.frame_1.show()
        else:
            self.frame_0.hide()
            self.frame_1.hide()
            self.frame_2.show()

    def get_para(self, index):
        if index == 0:
            self.cd_parameters['lbound'] = float(self.cd_lbound.text())
            self.cd_parameters['ubound'] = float(self.cd_ubound.text())
            self.cd_parameters['chargecurrent'] = float(
                self.cd_chargecurrent.text())/1e3
            self.cd_parameters['dischargecurrent'] = float(
                self.cd_dischargecurrent.text())/1e3
            self.cd_parameters['numcycles'] = int(self.cd_numcycles.text())
            self.cd_parameters['numsamples'] = int(self.cd_numsamples.text())

    def exit_window(self):
        self.close()

    def add(self):
        if main_window.status_table < 8:
            frame_ = Frame(main_window.main_widget)
            frame_.index_measure = self.option.currentIndex()
            self.get_para(frame_.index_measure)
            frame_.setStyleSheet("background-color: #181818;")
            frame_.resize(127, 102)
            frame_.index_table = main_window.status_table
            frame_.move(x[main_window.status_table],
                        y[main_window.status_table])
            main_window.status_table += 1
            frame_.show()
        self.exit_window()


class main(QMainWindow):
    def __init__(self):
        super(main, self).__init__()
        uic.loadUi('./form.ui', self)
        self.setMouseTracking(True)

        self.main_widget = self.findChild(QWidget, 'main_widget')

        self.usb_connect = self.findChild(QPushButton, 'usb_connect')
        self.usb_connect.clicked.connect(connect_disconnect_usb)

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

        self.status_table = 0
        self.status_line = 0
        self.sort_ = 0

        # self.frame_x = Frame(self.main_widget)
        # self.frame_x.setStyleSheet("background-color: #181818;")
        # self.frame_x.resize(127, 102)
        # self.frame_x.move(450, 3)

        self.button_create = self.findChild(QPushButton, 'create_measure')
        self.button_create.clicked.connect(self.open_new)

        self.frame_y = self.findChild(QFrame, 'frame_20')
        self.dynamicPlt = pg.PlotWidget(self)

        self.dynamicPlt.move(0, 585)
        self.dynamicPlt.resize(1440, 120)

        self.dynamicPlt2 = pg.PlotWidget(self)
        self.dynamicPlt2.move(777, 0)
        self.dynamicPlt2.resize(663, 519)

        self.timer2 = pg.QtCore.QTimer()
        self.timer2.timeout.connect(self.update)
        self.timer2.start(qt_timer_period)
        self.show()

    def update(self):
        if state == States.Idle_Init:
            idle_init()
        if state == States.Idle:
            read_potential_current()
            update_live_graph()

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
