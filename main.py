import os
import sys

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5 import uic, QtOpenGL, QtGui
import pyqtgraph as pg
import time
from utils.global_var import *
from utils.util import *
from utils.calculate import *
from utils.control_usb import *
from models.device import Device
from ui.model.manual_ui import Manual
from ui.model.calibrate_ui import Calibration

pg.setConfigOptions(foreground="#e5e5e5", background="#00304f")


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
        if (main_window.frame_20.pos().y()-50 < self.pos().y() < main_window.frame_20.pos().y()+50) and self.check_stack == 0:
            self.check_move = 0
            self.check_stack = 1
            pos_x_line = main_window.button_refresh.pos(
            ).x() + main_window.button_refresh.width()
            pos_y_line = main_window.frame_20.pos().y()
            self.resize(120, main_window.frame_20.height())
            # self.setStyleSheet(
            #     "background-color: #202932;")
            self.move(pos_x_line + main_window.status_line*120, pos_y_line)
            main_window.status_line += 1
            # main_window.status_table -= 1
            self.index_line = main_window.status_line
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

class create(QMainWindow):
    def __init__(self, parent=None):
        super(create, self).__init__(parent)
        uic.loadUi('./ui/sub_window/create_window.ui', self)
        self.setFixedSize(305, 543)
        self.comboBox.addItems(LIST_TECHNIQUES)

        self.button_cancel.clicked.connect(self.exit_window)

        self.button_add.clicked.connect(self.add)

        self.choose_file.clicked.connect(self.choose_file_)

        self.rate_crates.setText("1, 2, 5, 10, 20, 50, 100")

        self.ocp_button.clicked.connect(self.cv_get_ocp)

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

        self.rate_testing.hide()
        self.cyclic_voltammetry.hide()
        self.save_path.setText(self.cd_parameter['filename'])

        self.comboBox.activated.connect(self.do_something)

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
            self.rate_testing.hide()
            self.cyclic_voltammetry.hide()
            self.charge_disch.show()
            self.index = index
            self.save_path.setText(self.cd_parameter['filename'])
        elif (index == 1):
            self.charge_disch.hide()
            self.cyclic_voltammetry.hide()
            self.rate_testing.show()
            self.index = index
            self.save_path.setText(self.rate_parameter['filename'])
        else:
            self.charge_disch.hide()
            self.rate_testing.hide()
            self.cyclic_voltammetry.show()
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
                if self.cd_validate_parameters() and validate_file(main_window, self.cd_parameter['filename']):
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
                if self.rate_validate_parameters() and validate_file(main_window, self.rate_parameter['filename']):
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
                if self.cv_validate_parameters() and validate_file(main_window, self.cv_parameter['filename']):
                    parameters = {'id': id_, 'type': 'cv',
                                  'value': self.cv_parameter}
                    return parameters
                else:
                    # self.exit_window()
                    return False
            except ValueError:
                self.exit_window()
                return False

    def cv_get_ocp(self):
        """Insert the currently measured (open-circuit) potential into the start potential input field."""
        self.cv_startpot.setText('%5.3f' % potential)

    def exit_window(self):
        self.close()

    def add(self):
        global id_
        if main_window.status_table < ADD_TABLE_SIZE[0]*ADD_TABLE_SIZE[1]:
            frame_ = Frame(main_window.main_widget)
            frame_.index_measure = self.comboBox.currentIndex()
            frame_.parameters = self.get_para(
                frame_.index_measure)
            if frame_.parameters:
                id_ += 1
                frame_.setStyleSheet("background-color: %s;" %
                                     COLOR_TABLE[frame_.index_measure])
                name_technique = LIST_TECHNIQUES[frame_.index_measure] + \
                    '\n' + str(INDEX_TECHNIQUES[frame_.index_measure])
                frame_.setText(name_technique)
                INDEX_TECHNIQUES[frame_.index_measure] += 1
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
        uic.loadUi('./ui/mainwindow.ui', self)
        self.setMouseTracking(True)

        # Create index for album area
        setting_width = self.frame.width()
        addBtn_width = self.create_measure.width()
        addBtn_height = self.create_measure.height()

        self.usb_vid.setText(usb_vid_)
        self.usb_pid.setText(usb_pid_)

        self.new_device = Device(self)

        self.manual_window = Manual(self, self.new_device)
        self.calibration_window = Calibration(self.new_device)

        gap_col = (setting_width -
                   ADD_TABLE_SIZE[1] * addBtn_width)/(ADD_TABLE_SIZE[1] - 1)
        self.x_axis = [col*(gap_col + addBtn_width)
                       for col in range(ADD_TABLE_SIZE[1])]
        gap_row = 10
        self.y_axis = [self.create_frame.y() + row*(gap_row + addBtn_height)
                       for row in range(ADD_TABLE_SIZE[0])]
        


        self.usb_connect.clicked.connect(self.new_device.connect_disconnect_usb)

        self.button_start.clicked.connect(self.new_device.start)

        self.calibration_window.auto_zero.clicked.connect(self.new_device.zero_offset)
        self.calibration_window.auto_calibrate.clicked.connect(self.new_device.dac_calibrate)
        self.calibration_window.load_from_device.clicked.connect(
            self.new_device.get_calibration)
        self.calibration_window.save_to_device.clicked.connect(
            self.new_device.set_calibration)

        self.button_refresh.clicked.connect(self.refresh)

        self.actionControl.triggered.connect(self.open_manual)

        self.actionCalibration.triggered.connect(self.open_calibration)

        self.current_range_set.clicked.connect(self.new_device.set_current_range)

        self.manual_window.current_range_box.addItems(
            ["20 mA", u"200 µA", u"2 µA"])
        self.manual_window.comboBox_2.addItems(
            ["Potential (V)", "Current (mA)", "DAC Code"])

        
        self.status_table = 1
        self.status_line = 0
        self.sort_ = 0

        self.index_measure = 0

        self.create_measure.clicked.connect(self.open_new)

        self.dynamicPlt = pg.PlotWidget(self)

        self.dynamicPlt.move(305, 92)
        self.dynamicPlt.resize(690, 450)

        self.dynamicPlt2 = pg.PlotWidget(self)
        self.dynamicPlt2.move(1000, 22)
        self.dynamicPlt2.resize(370, 520)

        self.timer2 = pg.QtCore.QTimer()
        self.timer2.timeout.connect(self.update)
        self.timer2.start(self.new_device.qt_timer_period)
        self.show()

    def update(self):
        global queue_measure, para_run
        if self.new_device.state == States.Idle_Init:
            self.new_device.idle_init()
        elif self.new_device.state == States.Idle:
            self.new_device.read_potential_current()
            self.new_device.update_live_graph()
        elif stop:
            pass
        elif self.new_device.state == States.Measuring_CD and stop == 0:
            self.new_device.cd_update(para_run)
        elif self.new_device.state == States.Measuring_CV and stop == 0:
            self.new_device.cv_update(para_run)
        elif self.new_device.state == States.Measuring_Rate and stop == 0:
            self.new_device.rate_update(para_run)
        elif self.new_device.state == States.Measuring_start and stop == 0:
            if queue_measure:
                if queue_measure[0]["type"] == "cd":
                    self.new_device.zero_offset_()
                    self.new_device.cd_start(queue_measure[0]['value'])
                    para_run = queue_measure[0]['value']
                    queue_measure.pop(0)
                elif queue_measure[0]["type"] == "cv":
                    self.new_device.zero_offset_()
                    self.new_device.cv_start(queue_measure[0]['value'])
                    para_run = queue_measure[0]['value']
                    queue_measure.pop(0)
                elif queue_measure[0]["type"] == "rate":
                    self.new_device.zero_offset_()
                    self.new_device.rate_start(queue_measure[0]['value'])
                    para_run = queue_measure[0]['value']
                    queue_measure.pop(0)
            else:
                self.new_device.state = States.Stationary_Graph
                self.button_start.setText('Start')

    def refresh(self):
        global queue_measure
        self.new_device.refresh()
        self.button_start.setText('Start')
        queue_measure = []
        frames = self.main_widget.findChildren(Frame)
        for frame in frames:
            if frame.check_stack:
                frame.frame_refresh()

    def open_new(self):
        qt_wid = create(self)
        qt_wid.show()

    def open_manual(self):
        self.manual_window.show()

    def open_calibration(self):
        self.calibration_window.show()

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
