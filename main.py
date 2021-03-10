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
from ui.model.create import Create
from ui.model.frame import Frame

from pathlib import Path

pg.setConfigOptions(foreground="#e5e5e5", background="#00304f")
CONFIG = get_config('./config/config.yml')
# path save file result
base_dir = os.path.dirname(os.path.realpath(__file__))
SAVE_PATH = os.path.join(base_dir, 'save')
# Create save path for each technique
Path(SAVE_PATH).mkdir(parents=True, exist_ok=True)


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

        self.usb_connect.clicked.connect(
            self.new_device.connect_disconnect_usb)

        self.button_start.clicked.connect(self.new_device.start)

        self.calibration_window.auto_zero.clicked.connect(
            self.button_zero_offset)
        self.calibration_window.auto_calibrate.clicked.connect(
            self.new_device.dac_calibrate)
        self.calibration_window.load_from_device.clicked.connect(
            self.new_device.get_calibration)
        self.calibration_window.save_to_device.clicked.connect(
            self.new_device.set_calibration)

        self.button_refresh.clicked.connect(self.refresh)

        self.actionControl.triggered.connect(self.open_manual)

        self.actionCalibration.triggered.connect(self.open_calibration)

        self.current_range_set.clicked.connect(
            self.new_device.set_current_range)

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
                check_auto_zero = 0
                if queue_measure[0]["type"] == "cd":
                    while not check_auto_zero:
                        self.new_device.zero_offset_()
                        self.new_device.read_potential_current()
                        self.new_device.update_live_graph()
                        time.sleep(0.3)
                        print(self.new_device.potential,
                              self.new_device.current)
                        check_auto_zero = CONFIG['para']['pot_offs_zero'][0] < self.new_device.potential < CONFIG['para']['pot_offs_zero'][
                            1] and CONFIG['para']['cur_offs_zero'][0] < self.new_device.current < CONFIG['para']['cur_offs_zero'][1]
                elif queue_measure[0]["type"] == "cv":
                    while not check_auto_zero:
                        self.new_device.zero_offset_()
                        self.new_device.read_potential_current()
                        self.new_device.update_live_graph()
                        time.sleep(0.3)
                        print(self.new_device.potential,
                              self.new_device.current)
                        check_auto_zero = CONFIG['para']['pot_offs_zero'][0] < self.new_device.potential < CONFIG['para']['pot_offs_zero'][
                            1] and CONFIG['para']['cur_offs_zero'][0] < self.new_device.current < CONFIG['para']['cur_offs_zero'][1]
                    self.new_device.zero_offset_()
                    self.new_device.cv_start(queue_measure[0]['value'])
                    para_run = queue_measure[0]['value']
                    queue_measure.pop(0)
                elif queue_measure[0]["type"] == "rate":
                    while not check_auto_zero:
                        self.new_device.zero_offset_()
                        self.new_device.read_potential_current()
                        self.new_device.update_live_graph()
                        time.sleep(0.3)
                        print(self.new_device.potential,
                              self.new_device.current)
                        check_auto_zero = CONFIG['para']['pot_offs_zero'][0] < self.new_device.potential < CONFIG['para']['pot_offs_zero'][
                            1] and CONFIG['para']['cur_offs_zero'][0] < self.new_device.current < CONFIG['para']['cur_offs_zero'][1]
                    self.new_device.zero_offset_()
                    self.new_device.rate_start(queue_measure[0]['value'])
                    para_run = queue_measure[0]['value']
                    queue_measure.pop(0)
            else:
                self.new_device.state = States.Stationary_Graph
                self.button_start.setText('Start')

    def button_zero_offset(self):
        check_auto_zero = 0
        while not check_auto_zero:
            self.new_device.zero_offset_()
            self.new_device.read_potential_current()
            self.new_device.update_live_graph()
            time.sleep(0.3)
            print(self.new_device.potential, self.new_device.current)
            check_auto_zero = CONFIG['para']['pot_offs_zero'][0] < self.new_device.potential < CONFIG['para']['pot_offs_zero'][
                1] and CONFIG['para']['cur_offs_zero'][0] < self.new_device.current < CONFIG['para']['cur_offs_zero'][1]

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
        qt_wid = Create(self)
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
