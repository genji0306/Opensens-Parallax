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

pg.setConfigOption('background', 'w')

x = [450, 594, 310, 450, 594, 310, 450, 594]
y = [3, 3, 115, 115, 115, 227, 227, 227]
y_size = [56, 176, 296, 416, 536]

usb_vid = "0xa0a0"  # Default USB vendor ID, can also be adjusted in the GUI
usb_pid = "0x0002"  # Default USB product ID, can also be adjusted in the GUI

dev = None  # Global object which is reserved for the USB device


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
    print(dev)
    if dev is None:
        print("USB Device Not Found, No USB device was found with VID %s and PID %s. Verify the vendor/product ID and check the USB connection." %
              (usb_vid_string, usb_pid_string))
    else:
        main_window.usb_connect.setText("Disconnect")
        # log_message("USB Interface connected.")
        try:
            print(dev.manufacturer, dev.product, dev.serial_number)
            main_window.label_manufacture.setText(
                "Manufacture:   %s" % (dev.manufacturer))
            main_window.label_product.setText("Product:   %s" % (dev.product))
            main_window.label_serial.setText(
                "Serial #:   %s" % (dev.serial_number))

            # hardware_device_info_text.setText("Manufacturer: %s\nProduct: %s\nSerial #: %s" % (
            #     dev.manufacturer, dev.product, dev.serial_number))
            # get_calibration()
            # set_cell_status(False)  # Cell off
            # set_control_mode(False)  # Potentiostatic control
            # set_current_range()  # Read current range from GUI
            state = States.Idle_Init  # Start idle mode
        except ValueError:
            print("### Error USB")
            pass  # In case the device is not yet calibrated


class Frame(QPushButton):
    def __init__(self, parent):
        super(Frame, self).__init__(parent)
        self.check_move = 0
        self.index_table = 0
        self.index_line = 0
        self.setMouseTracking(True)

    def mousePressEvent(self, e):
        self.check_move = 1

    def mouseReleaseEvent(self, e):
        if (main_window.frame_y.pos().y()-50 < self.pos().y() < main_window.frame_y.pos().y()+50):
            self.check_move = 0
            self.resize(120, 73)
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

    def exit_window(self):
        self.close()

    def add(self):
        if main_window.status_table < 8:
            frame_ = Frame(main_window.main_widget)
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
        self.option = self.findChild(QComboBox, 'comboBox')

        self.usb_connect = self.findChild(QPushButton, 'usb_connect')
        self.usb_connect.clicked.connect(connect_disconnect_usb)

        self.option.addItems(["20 mA", u"200 µA", u"2 µA"])
        self.option2 = self.findChild(QComboBox, 'comboBox_2')
        self.option2.addItems(["Potential (V)", "Current (mA)", "DAC Code"])

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

        self.dynamicPlt.move(0, 630)
        self.dynamicPlt.resize(1440, 50)

        self.dynamicPlt2 = pg.PlotWidget(self)

        self.dynamicPlt2.move(777, 0)
        self.dynamicPlt2.resize(663, 519)

        self.timer2 = pg.QtCore.QTimer()
        self.timer2.timeout.connect(self.update)
        self.timer2.start(200)
        self.show()

    def update(self):
        QApplication.processEvents()
        z = np.random.normal(size=1)
        u = np.random.normal(size=1)
        self.dynamicPlt.plot(z, u, pen=None, symbol='o')
        self.dynamicPlt2.plot(z, u, pen=None, symbol='o')

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
