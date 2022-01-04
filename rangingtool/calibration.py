from PyQt5 import QtWidgets, QtCore, uic
import numpy as np
from pkg_resources import resource_filename


class SignalCalibrationWindow(QtWidgets.QWidget):
    def __init__(self, background_process, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Initialize appearance of the UI
        uic.loadUi(resource_filename(__name__, './calibration.ui'), self)

        # Declare Variables
        self.background_process = background_process
        self.zp_order = 10  # Order of zero-padding
        self.freq = None
        self.freq_response = None

        # Update measured data timer
        self.update_plot_timer = QtCore.QTimer()
        self.update_plot_timer.timeout.connect(self.update_plot)
        self.update_plot_timer.start(1000)

        # Signals
        self.btn_do_calibration.clicked.connect(self.btn_do_calibration_clicked)
        self.btn_load_calibration.clicked.connect(self.btn_load_calibration_clicked)
        self.btn_save_calibration.clicked.connect(self.btn_save_calibration_clicked)

        # Setup plot widget
        self.curve = self.plt_calibration.plot()
        self.plt_calibration.getAxis('left').setLabel('Normalized Impulse Response (dB)')
        self.plt_calibration.getAxis('bottom').setLabel('Normalized Time (#)')
        self.plt_calibration.setXRange(-20, 20)
        self.plt_calibration.setYRange(-40, 0)

    def closeEvent(self, event):
        # Stop timer
        self.update_plot_timer.stop()

        event.accept()

    def btn_do_calibration_clicked(self):
        self.background_process.do_rf_path_calibration()

    def btn_load_calibration_clicked(self):
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Load File', filter='Numpy files (*.npz)')
        if filename != '':
            data = np.load(filename)
            freq = data['freq']
            freq_response = data['freq_response']
            self.background_process.load_rf_path_response(freq, freq_response)

    def btn_save_calibration_clicked(self):
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Save File', filter='Numpy files (*.npz)')
        if filename != '':
            np.savez(filename, freq=self.freq, freq_response=self.freq_response)

    def update_plot(self):
        """Slot to timer for updating user interface with measured data."""
        # Fetch rf path response from background process
        data = self.background_process.get_rf_path_response()
        self.freq = data['freq']
        self.freq_response = data['response']

        if self.freq_response is not None:
            # Compute impulse response
            impulse_response = np.fft.fftshift(np.fft.ifft(self.freq_response, len(self.freq_response) * self.zp_order))
            impulse_response_db = 20 * np.log10(np.abs(impulse_response))
            impulse_response_db -= np.max(impulse_response_db)  # Normalization
            time = np.linspace(-(len(self.freq_response)/2), (len(self.freq_response)/2 - 1), len(impulse_response))

            # Update plot
            self.curve.setData(time, impulse_response_db)
