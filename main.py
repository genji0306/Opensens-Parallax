import os
import sys

from PyQt5.QtWidgets import QApplication, QMainWindow, QComboBox, QGridLayout, QPushButton, QWidget, QFrame
from PyQt5 import uic, QtOpenGL
import numpy as np
import pyqtgraph as pg
import random

pg.setConfigOption('background', 'w')

class create(QMainWindow):
    def __init__(self, parent=None):
        super(create, self).__init__(parent)
        uic.loadUi('./mainwindow.ui', self)
        self.setFixedSize(305,543)
        self.option = self.findChild(QComboBox, 'comboBox')
        self.option.addItems(["Charge/disch", "Rate testing", "Cyclic voltammetry"])
        self.button_cancel = self.findChild(QPushButton, 'button_cancel')
        self.button_cancel.clicked.connect(self.exit_window)

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

class main(QMainWindow):
    def __init__(self):
        super(main, self).__init__()
        uic.loadUi('./form.ui', self)
        self.setMinimumSize(300,521)
        self.option = self.findChild(QComboBox, 'comboBox')
        self.option.addItems(["20 mA", u"200 µA", u"2 µA"])
        self.option2 = self.findChild(QComboBox, 'comboBox_2')
        self.option2.addItems(["Potential (V)", "Current (mA)", "DAC Code"])

        self.button_create = self.findChild(QPushButton, 'pushButton_2')
        self.button_create.clicked.connect(self.open_new)

        self.dynamicPlt = pg.PlotWidget(self)

        self.dynamicPlt.move(0,550)
        self.dynamicPlt.resize(1440,200)

        self.dynamicPlt2 = pg.PlotWidget(self)

        self.dynamicPlt2.move(777,0)
        self.dynamicPlt2.resize(663,519)

        self.timer2 = pg.QtCore.QTimer()
        self.timer2.timeout.connect(self.update)
        self.timer2.start(200)

    def update(self):
        z = np.random.normal(size=1)
        u = np.random.normal(size=1)
        self.dynamicPlt.plot(z,u,pen=None, symbol='o')
        self.dynamicPlt2.plot(z,u,pen=None, symbol='o')

    def open_new(self):
        print("---")
        qt_wid = create(self)
        qt_wid.show()
        # qt_wid.exec_()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = main()
    main_window.show()
    sys.exit(app.exec_())
