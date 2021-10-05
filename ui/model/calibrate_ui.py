from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5 import uic, QtOpenGL, QtGui


class Calibration(QMainWindow):
    def __init__(self, device, parent=None):
        super(Calibration, self).__init__(parent)
        uic.loadUi('./ui/menubar/calibration.ui', self)
        self.R = [self.r1, self.r2, self.r3]
        for i in range(0, 3):
            self.R[i].editingFinished.connect(
                device.shunt_calibration_changed_callback)
