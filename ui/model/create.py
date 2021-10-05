import time
from .frame import Frame
from utils.util import *
from utils.global_var import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5 import uic, QtOpenGL, QtGui
import sys
sys.path.append('.')
# from main import Frame


class Create(QMainWindow):
    def __init__(self, parent=None):
        super(Create, self).__init__(parent)
        uic.loadUi('./ui/sub_window/create_window.ui', self)
        self.main_window = parent
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
        self.id_ = 0

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
                if self.cd_validate_parameters() and validate_file(self.main_window, self.cd_parameter['filename']):
                    parameters = {'id': self.id_, 'type': 'cd',
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
                if self.rate_validate_parameters() and validate_file(self.main_window, self.rate_parameter['filename']):
                    parameters = {'id': self.id_, 'type': 'rate',
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
                if self.cv_validate_parameters() and validate_file(self.main_window, self.cv_parameter['filename']):
                    parameters = {'id': self.id_, 'type': 'cv',
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
        # global id_
        if self.main_window.status_table < ADD_TABLE_SIZE[0]*ADD_TABLE_SIZE[1]:
            frame_ = Frame(self.main_window, self.main_window.main_widget)
            frame_.index_measure = self.comboBox.currentIndex()
            frame_.parameters = self.get_para(
                frame_.index_measure)
            if frame_.parameters:
                self.id_ += 1
                frame_.setStyleSheet("background-color: %s;" %
                                     COLOR_TABLE[frame_.index_measure])
                name_technique = LIST_TECHNIQUES[frame_.index_measure] + \
                    '\n' + str(INDEX_TECHNIQUES[frame_.index_measure])
                frame_.setText(name_technique)
                INDEX_TECHNIQUES[frame_.index_measure] += 1
                frame_.resize(80, 61)
                frame_.index_table = self.main_window.status_table
                frame_.move(self.main_window.x_axis[int(self.main_window.status_table % ADD_TABLE_SIZE[1])],
                            self.main_window.y_axis[int(self.main_window.status_table / ADD_TABLE_SIZE[1])])
                self.main_window.status_table += 1
                frame_.show()
        self.exit_window()
