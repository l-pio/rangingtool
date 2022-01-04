from PyQt5 import QtWidgets, QtGui, QtCore, uic
import numpy as np
from pkg_resources import resource_filename


class AlignmentWindow(QtWidgets.QWidget):
    def __init__(self, background_process, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Initialize appearance of the UI
        uic.loadUi(resource_filename(__name__, './alignment.ui'), self)

        # Declare Variables
        self.background_process = background_process
        self.signal_strength = None
        self.max_signal_strength = None
        self.snr = None
        self.level_range = 2  # Range for fine signal-strength indication
        self.a1 = 0.5  # Feedback filter coefficient of IIR lowpass filter

        # Update label
        self.label_range_1.setText('0 ... 100 %%')
        self.label_range_2.setText('%d ... 100 %%' % (100 - self.level_range))

        # Update measured data timer
        self.update_measured_data_timer = QtCore.QTimer()
        self.update_measured_data_timer.timeout.connect(self.update_measured_data)
        self.update_measured_data_timer.start(100)

        # Signals
        self.btn_reset_indicator.clicked.connect(self.btn_reset_indicator_clicked)

        # Slots to background process
        self.background_process.new_data_signal.connect(self.new_data)

    def closeEvent(self, event):
        # Stop timer & Disconnect new data signal
        self.update_measured_data_timer.stop()
        self.background_process.new_data_signal.disconnect(self.new_data)

        event.accept()

    def new_data(self, value):
        """Slot for incoming data."""
        # Update measured values
        if not np.isnan(np.mean(value['power_db'])):
            # Filter signal strength value by IIR lowpass filter
            x = np.mean(value['power_db'])
            self.signal_strength = (x if self.signal_strength is None
                                    else (1 - self.a1) * x + self.a1 * self.signal_strength)

        if not np.isnan(np.mean(value['snr_db'])):
            # Filter SNR value by IIR lowpass filter
            x = np.mean(value['snr_db'])
            self.snr = (x if self.snr is None
                        else (1 - self.a1) * x + self.a1 * self.snr)

        # Update value for drag indicator
        if self.max_signal_strength is None:
            self.max_signal_strength = self.signal_strength
        elif self.signal_strength > self.max_signal_strength:
            self.max_signal_strength = self.signal_strength

    def update_measured_data(self):
        """Slot to timer for updating user interface with measured data."""
        # Update signal level
        if self.max_signal_strength is not None:
            level = 10**((self.signal_strength - self.max_signal_strength) / 10) * 100  # Linear !
            self.ledit_level.setText('%.2f %%' % level)
            self.pbar_1.setValue(round(level))
            self.pbar_2.setValue(
                {True: round((level - 100 + self.level_range) * 100 / self.level_range),
                 False: 0
                 }[level >= 100 - self.level_range]
            )

        # Update line edit values
        if self.signal_strength is not None:
            self.ledit_signal_strength.setText('%.2f' % self.signal_strength)

        if self.snr is not None:
            self.ledit_snr.setText('%.2f' % self.snr)

    def btn_reset_indicator_clicked(self):
        self.max_signal_strength = None
