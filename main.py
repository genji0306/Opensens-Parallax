import os
import sys
# Import UI library
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5 import uic, QtOpenGL, QtGui
import pyqtgraph as pg
import time
# Import utils helper function
# Get static var from global_var file
from utils.global_var import *
from utils.util import *
from utils.calculate import *
from utils.control_usb import *
# Import class Device
from models.device import Device
# Import UI class
from ui.model.manual_ui import Manual
from ui.model.calibrate_ui import Calibration
from ui.model.create import Create
from ui.model.frame import Frame

from pathlib import Path

# Init and set color of UI
pg.setConfigOptions(foreground="#e5e5e5", background="#00304f")
# Read config to stop zero offset funciton
CONFIG = get_config('./config/config.yml')
# path save file result
base_dir = os.path.dirname(os.path.realpath(__file__))
# Create path dir for save result technique
SAVE_PATH = os.path.join(base_dir, 'save')
# Create save path for each technique
Path(SAVE_PATH).mkdir(parents=True, exist_ok=True)


class main(QMainWindow):
    '''
    Main window of UI:
    1. Add sub window from other UI class
    2. Add control logic to UI
    '''
    def __init__(self):
        super(main, self).__init__()
        # Load main window UI
        uic.loadUi('./ui/mainwindow.ui', self)
        # Set tracking mouse to get the coordinate in UI
        self.setMouseTracking(True)

        # Create index for list technique area (e.g: Album)
        setting_width = self.frame.width()
        addBtn_width = self.create_measure.width()
        addBtn_height = self.create_measure.height()

        # Set default value for VID, PID, value usb_vid_, usb_pid_ was imported in utils/global_var.py
        self.usb_vid.setText(usb_vid_)
        self.usb_pid.setText(usb_pid_)

        # Create new Device object
        self.new_device = Device(self)

        # Add sub UI with manual and calibaration in taskbar main UI
        self.manual_window = Manual(self, self.new_device)
        self.calibration_window = Calibration(self.new_device)

        # Defind the coordinate and put frame in list technique area
        gap_col = (setting_width -
                   ADD_TABLE_SIZE[1] * addBtn_width)/(ADD_TABLE_SIZE[1] - 1)
        self.x_axis = [col*(gap_col + addBtn_width)
                       for col in range(ADD_TABLE_SIZE[1])]
        gap_row = 10
        self.y_axis = [self.create_frame.y() + row*(gap_row + addBtn_height)
                       for row in range(ADD_TABLE_SIZE[0])]
        # Add control for mouse click connect button
        self.usb_connect.clicked.connect(
            self.new_device.connect_disconnect_usb)
        # Add control for start button
        self.button_start.clicked.connect(self.new_device.start)
        # Add control for auto_zero button in Calibration UI
        self.calibration_window.auto_zero.clicked.connect(
            self.button_zero_offset)
        # Add control for auto_calibrate button in Calibration UI
        self.calibration_window.auto_calibrate.clicked.connect(
            self.new_device.dac_calibrate)
        # Add control for load_from_device button in Calibration UI
        self.calibration_window.load_from_device.clicked.connect(
            self.new_device.get_calibration)
        # Add control for save_to_device button in Calibration UI
        self.calibration_window.save_to_device.clicked.connect(
            self.new_device.set_calibration)
        # Add control for refresh button
        self.button_refresh.clicked.connect(self.refresh)
        # Add control for open_manual taskbar
        self.actionControl.triggered.connect(self.open_manual)
        # Add control for open_calibration taskbar
        self.actionCalibration.triggered.connect(self.open_calibration)
        # Add control for current_range_set in Manual UI
        self.current_range_set.clicked.connect(
            self.new_device.set_current_range)

        # Set value for current_range_set in Manual UI
        self.manual_window.current_range_box.addItems(
            ["20 mA", u"200 µA", u"2 µA"])

        # Set value for Potential in Manual UI
        self.manual_window.comboBox_2.addItems(
            ["Potential (V)", "Current (mA)", "DAC Code"])
        # Get the i_th measure of table measure
        self.status_table = 1
        # Get the i_th measure of list ready measure in start/refresh bar
        self.status_line = 0

        self.index_measure = 0

        # Create new measure in main UI with Add button in techique area
        self.create_measure.clicked.connect(self.open_new)

        # Set first plot zone UI -> dynamic plot continuous update
        self.dynamicPlt = pg.PlotWidget(self)

        self.dynamicPlt.move(305, 92)
        self.dynamicPlt.resize(690, 450)
        # Set first plot zone UI -> result zone
        self.dynamicPlt2 = pg.PlotWidget(self)
        self.dynamicPlt2.move(1000, 22)
        self.dynamicPlt2.resize(370, 520)

        # Set timer for loop UI
        self.timer2 = pg.QtCore.QTimer()
        # Auto run self.update method loop with timer
        self.timer2.timeout.connect(self.update)
        self.timer2.start(self.new_device.qt_timer_period)
        # Plot Main UI and Sub UI
        self.show()

    def update(self):
        global queue_measure, para_run
        #queue_measure: Queue of list measure
        # Check state of Device
        if self.new_device.state == States.Idle_Init:
            # Init idel device
            self.new_device.idle_init()
        elif self.new_device.state == States.Idle:
            self.new_device.read_potential_current()
            self.new_device.update_live_graph()
        elif stop: # stop default = 0
            pass
        # Init measure follow its techniques
        elif self.new_device.state == States.Measuring_CD and stop == 0:
            self.new_device.cd_update(para_run)
        elif self.new_device.state == States.Measuring_CV and stop == 0:
            self.new_device.cv_update(para_run)
        elif self.new_device.state == States.Measuring_Rate and stop == 0:
            self.new_device.rate_update(para_run)
        elif self.new_device.state == States.Measuring_start and stop == 0:
            if queue_measure:
                if queue_measure[0]["type"] == "cd":
                    # Calibrate to zero offet to start new measure
                    self.button_zero_offset()
                    self.new_device.cd_start(queue_measure[0]['value'])
                    para_run = queue_measure[0]['value']
                    queue_measure.pop(0)
                elif queue_measure[0]["type"] == "cv":
                    # Calibrate to zero offet to start new measure
                    self.button_zero_offset()
                    self.new_device.cv_start(queue_measure[0]['value'])
                    para_run = queue_measure[0]['value']
                    queue_measure.pop(0)
                elif queue_measure[0]["type"] == "rate":
                    # Calibrate to zero offet to start new measure
                    self.button_zero_offset()
                    self.new_device.rate_start(queue_measure[0]['value'])
                    para_run = queue_measure[0]['value']
                    queue_measure.pop(0)
            else:
                # IF Queue is empty -> reset button to start
                self.new_device.state = States.Stationary_Graph
                self.button_start.setText('Start')

    def button_zero_offset(self):
        '''
        Calibrate to zero offet to start new measure
        '''
        check_auto_zero = 0
        while not check_auto_zero:
            # offset the device
            self.new_device.zero_offset_()
            # Read current value
            self.new_device.read_potential_current()
            # Update main UI
            self.new_device.update_live_graph()
            time.sleep(0.3)
            print(self.new_device.potential,
                  self.new_device.current, check_auto_zero)
            # Condition to stop zero offet
            check_auto_zero = CONFIG['para']['pot_offs_zero'][0] < self.new_device.potential < CONFIG['para']['pot_offs_zero'][
                1] and CONFIG['para']['cur_offs_zero'][0] < self.new_device.current < CONFIG['para']['cur_offs_zero'][1]

    def refresh(self):
        '''
        Refresh button to reset the UI
        '''
        global queue_measure
        self.new_device.refresh()
        self.button_start.setText('Start')
        queue_measure = []
        frames = self.main_widget.findChildren(Frame)
        for frame in frames:
            if frame.check_stack:
                frame.frame_refresh()

    def open_new(self):
        # Create new measure
        qt_wid = Create(self)
        qt_wid.show()

    def open_manual(self):
        # Open manual taskbar
        self.manual_window.show()

    def open_calibration(self):
        # Open open_calibration taskbar
        self.calibration_window.show()

    def mouseMoveEvent(self, e):
        # Get the coordinate of mouse, if mouse click in measure, it will move measure to album zone
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
