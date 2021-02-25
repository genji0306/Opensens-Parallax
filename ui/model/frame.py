from utils.global_var import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5 import uic, QtOpenGL, QtGui
import sys
sys.path.append('.')


class Frame(QPushButton):
    def __init__(self, main_window, parent):
        super(Frame, self).__init__(parent)
        self.main_window = main_window
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
        global queue_measure
        if (self.main_window.frame_20.pos().y()-50 < self.pos().y() < self.main_window.frame_20.pos().y()+50) and self.check_stack == 0:
            self.check_move = 0
            self.check_stack = 1
            pos_x_line = self.main_window.button_refresh.pos(
            ).x() + self.main_window.button_refresh.width()
            pos_y_line = self.main_window.frame_20.pos().y()
            self.resize(120, self.main_window.frame_20.height())
            # self.setStyleSheet(
            #     "background-color: #202932;")
            self.move(pos_x_line + self.main_window.status_line*120, pos_y_line)
            self.main_window.status_line += 1
            # self.main_window.status_table -= 1
            self.index_line = self.main_window.status_line
            if self.parameters:
                queue_measure.append(self.parameters)
        else:
            if self.parameters:
                for queue_measure_ in queue_measure:
                    if queue_measure_['id'] == self.parameters['id']:
                        queue_measure.remove(queue_measure_)
                self.check_move = 0
                self.check_stack = 0
                self.resize(80, 61)
                if self.index_line:
                    self.main_window.status_line -= 1
                    self.index_line = 0
                # self.setStyleSheet("background-color: #181818;")
                self.move(self.main_window.x_axis[int(self.index_table % ADD_TABLE_SIZE[1])],
                          self.main_window.y_axis[int(self.index_table / ADD_TABLE_SIZE[1])])
            else:
                self.check_move = 0
                self.check_stack = 0
                self.resize(80, 61)
                if self.index_line:
                    self.main_window.status_line -= 1
                    self.index_line = 0
                # self.setStyleSheet("background-color: #181818;")
                self.move(self.main_window.x_axis[int(self.index_table % ADD_TABLE_SIZE[1])],
                          self.main_window.y_axis[int(self.index_table / ADD_TABLE_SIZE[1])])

    def frame_refresh(self):
        self.check_move = 0
        self.check_stack = 0
        self.resize(80, 61)
        if self.index_line:
            self.main_window.status_line -= 1
            self.index_line = 0
        # self.setStyleSheet("background-color: #181818;")
        self.move(self.main_window.x_axis[int(self.index_table % ADD_TABLE_SIZE[1])],
                  self.main_window.y_axis[int(self.index_table / ADD_TABLE_SIZE[1])])
