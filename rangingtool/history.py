from PyQt5 import QtWidgets, QtCore, uic
import numpy as np
from pkg_resources import resource_filename


class HistoryPlotWindow(QtWidgets.QWidget):
    def __init__(self, background_process, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Initialize appearance of the UI
        uic.loadUi(resource_filename(__name__, './history.ui'), self)

        # Declare Variables
        self.background_process = background_process
        self.distance = None
        self.window_length = None
        self.distance_mem = None

        # Update measured data timer
        self.update_measured_data_timer = QtCore.QTimer()
        self.update_measured_data_timer.timeout.connect(self.update_measured_data)
        self.update_measured_data_timer.start(100)

        # Signals
        self.sb_window_length.valueChanged.connect(self.sb_window_length_changed)

        # Slots to background process
        self.background_process.new_data_signal.connect(self.new_data)

        # Setup plot widget
        self.curve = self.plt_echo.plot()
        self.plt_echo.getAxis('left').setLabel('Distance (m)')
        self.plt_echo.getAxis('bottom').setLabel('Sample (#)')

        # Set initial values of the UI
        self.sb_window_length.setValue(1000)

    def closeEvent(self, event):
        # Stop timer & Disconnect new data signal
        self.update_measured_data_timer.stop()
        self.background_process.new_data_signal.disconnect(self.new_data)

        event.accept()

    def new_data(self, value):
        """Slot for incoming data."""
        # Update buffer
        self.distance = value['distance']
        if len(self.distance) <= self.window_length:
            self.distance_mem = np.roll(self.distance_mem, -len(self.distance))
            self.distance_mem[-len(self.distance):] = self.distance

    def sb_window_length_changed(self, value):
        # Init memory buffer
        if self.window_length is None:
            self.distance_mem = np.full(value, np.nan)
            self.window_length = value

        # Change size of memory buffer
        if value > self.window_length:
            self.distance_mem = np.append(np.full(value - self.window_length, np.nan), self.distance_mem)
        elif value < self.window_length:
            self.distance_mem = self.distance_mem[-value:]
        self.window_length = value

    def update_measured_data(self):
        """Slot to timer for updating user interface with measured data."""
        if self.distance is not None:
            self.curve.setData(self.distance_mem)
