from PyQt5 import QtWidgets, QtCore, uic
from pkg_resources import resource_filename


class EchoPlotWindow(QtWidgets.QWidget):
    def __init__(self, background_process, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Initialize appearance of the UI
        uic.loadUi(resource_filename(__name__, './echo.ui'), self)

        # Declare Variables
        self.background_process = background_process
        self.time_axis = None
        self.td_data = None

        # Update measured data timer
        self.update_measured_data_timer = QtCore.QTimer()
        self.update_measured_data_timer.timeout.connect(self.update_measured_data)
        self.update_measured_data_timer.start(100)

        # Slots to background process
        self.background_process.new_data_signal.connect(self.new_data)

        # Setup plot widget
        self.curve = self.plt_echo.plot()
        self.plt_echo.getAxis('left').setLabel('Echo (dB)')
        self.plt_echo.getAxis('bottom').setLabel('Distance (m)')

    def closeEvent(self, event):
        # Stop timer & Disconnect new data signal
        self.update_measured_data_timer.stop()
        self.background_process.new_data_signal.disconnect(self.new_data)

        event.accept()

    def new_data(self, value):
        """Slot for incoming data."""
        self.time_axis = value['time_axis']
        self.td_data = value['td_data_db'][0]  # first sweep

    def update_measured_data(self):
        """Slot to timer for updating user interface with measured data."""
        if self.td_data is not None:
            x = (self.time_axis * 3E8 / 2)[:len(self.time_axis)//2]
            y = self.td_data[:len(self.time_axis) // 2]
            self.curve.setData(x, y)
