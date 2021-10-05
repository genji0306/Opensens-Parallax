from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5 import uic, QtOpenGL, QtGui
from utils.control_usb import *
class Manual(QMainWindow):
    def __init__(self, main_window, device, parent=None):
        super(Manual, self).__init__(parent)
        uic.loadUi('./ui/menubar/manual.ui', self)
        self.cell_connect_on.clicked.connect(
            lambda: set_cell_status(device.dev, main_window, True))
        self.cell_connect_off.clicked.connect(
            lambda: set_cell_status(device.dev, main_window, False))
        self.potentiostat.clicked.connect(
            lambda: set_control_mode(device.dev, main_window, False))
        self.galvanostatic.clicked.connect(
            lambda: set_control_mode(device.dev, main_window, True))
        self.current_range_set.clicked.connect(device.set_current_range)
        self.lineEdit_13.returnPressed.connect(device.set_output_from_gui)
        self.pushButton_10.clicked.connect(device.set_output_from_gui)