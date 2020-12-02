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

pg.setConfigOption('background', 'w')

x = [450, 594, 310, 450, 594, 310, 450, 594]
y = [3, 3, 115, 115, 115, 227, 227, 227]
y_size = [0, 120, 240, 360, 480]


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
            self.setStyleSheet(
                "background-color: rgb(136, 138, 133)")
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
            self.setStyleSheet("background-color: #181818;")
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

        self.option.addItems(["20 mA", u"200 µA", u"2 µA"])
        self.option2 = self.findChild(QComboBox, 'comboBox_2')
        self.option2.addItems(["Potential (V)", "Current (mA)", "DAC Code"])

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
