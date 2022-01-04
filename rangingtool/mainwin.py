from PyQt5 import QtWidgets, QtGui, QtCore, uic
import numpy as np
from contextlib import suppress
from scipy.interpolate import interp1d
from pkg_resources import resource_filename

from .misc import gauge_formatter, MeasurementDataContainer
from .alignment import AlignmentWindow
from .echo import EchoPlotWindow
from .history import HistoryPlotWindow
from .calibration import SignalCalibrationWindow


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, app, background_process, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Initialize appearance of the UI
        uic.loadUi(resource_filename(__name__, './mainwin.ui'), self)

        QtCore.QLocale.setDefault(QtCore.QLocale("en_US"))  # Fixes dot as the decimal separator
        self.ledit_sample_count.setValidator(
            QtGui.QIntValidator(bottom=1)
        )
        self.ledit_roi_min.setValidator(
            QtGui.QDoubleValidator(bottom=0, decimals=2, notation=QtGui.QDoubleValidator.StandardNotation)
        )
        self.ledit_roi_max.setValidator(
            QtGui.QDoubleValidator(bottom=0, decimals=2, notation=QtGui.QDoubleValidator.StandardNotation)
        )
        self.ledit_d1.setValidator(
            QtGui.QDoubleValidator(bottom=0, decimals=1, notation=QtGui.QDoubleValidator.StandardNotation)
        )
        self.ledit_d2.setValidator(
            QtGui.QDoubleValidator(bottom=0, decimals=1, notation=QtGui.QDoubleValidator.StandardNotation)
        )
        self.ledit_a_tot.setValidator(
            QtGui.QDoubleValidator(bottom=0, decimals=1, notation=QtGui.QDoubleValidator.StandardNotation)
        )
        self.ledit_r_off.setValidator(
            QtGui.QDoubleValidator(decimals=1, notation=QtGui.QDoubleValidator.StandardNotation)
        )

        # Declare Variables
        self.app = app
        self.background_process = background_process
        self.distance = None
        self.signal_stength = None
        self.snr = None
        self.temp = None
        self.hum = None
        self.press = None
        self.co2 = None
        self.refractivity = None
        self.win_alignment = None
        self.win_echo = None
        self.win_history = None
        self.win_calibration = None
        self.pulse_position_variation_func = None
        self.pulse_phase_variation_func = None

        # Init measurement environment
        self.measurement_started = False
        self.measurement_sample_idx = 0
        self.measurement_sample_count = 10
        self.measurement_data_container = MeasurementDataContainer()

        # Update measured data timer
        self.update_measured_data_timer = QtCore.QTimer()
        self.update_measured_data_timer.timeout.connect(self.update_measured_data)
        self.update_measured_data_timer.start(100)

        # Signals
        self.btn_set_origin.clicked.connect(self.btn_set_origin_clicked)
        self.btn_start_measurement.clicked.connect(self.btn_start_measurement_clicked)
        self.btn_load_preset.clicked.connect(self.btn_load_preset_clicked)
        self.btn_save_preset.clicked.connect(self.btn_save_preset_clicked)
        self.btn_save_data.clicked.connect(self.btn_save_data_clicked)
        self.btn_save_raw_data.clicked.connect(self.btn_save_raw_data_clicked)
        self.btn_reset.clicked.connect(self.btn_reset_clicked)
        self.ledit_sample_count.textChanged.connect(self.ledit_sample_count_changed)
        self.ledit_roi_min.textChanged.connect(self.ledit_roi_changed)
        self.ledit_roi_max.textChanged.connect(self.ledit_roi_changed)
        self.cbox_nfc_none.clicked.connect(lambda _: self.cbox_nfc_clicked('cbox_nfc_none'))
        self.cbox_nfc_cfe.clicked.connect(lambda _: self.cbox_nfc_clicked('cbox_nfc_cfe'))
        self.ledit_d1.textChanged.connect(self.ledit_d_changed)
        self.ledit_d2.textChanged.connect(self.ledit_d_changed)
        self.cbox_nfc_pm.clicked.connect(lambda _: self.cbox_nfc_clicked('cbox_nfc_pm'))
        self.ledit_a_tot.textChanged.connect(self.ledit_k_changed)
        self.ledit_r_off.textChanged.connect(self.ledit_k_changed)
        self.cbox_nfc_func.clicked.connect(lambda _: self.cbox_nfc_clicked('cbox_nfc_func'))
        self.cobox_direction.currentTextChanged.connect(self.cobox_direction_changed)

        self.action_alignment.triggered.connect(
            lambda: self.open_sub_window('win_alignment', AlignmentWindow))
        self.action_echo.triggered.connect(
            lambda: self.open_sub_window('win_echo', EchoPlotWindow))
        self.action_history.triggered.connect(
            lambda: self.open_sub_window('win_history', HistoryPlotWindow))
        self.action_calibration.triggered.connect(
            lambda: self.open_sub_window('win_calibration', SignalCalibrationWindow))

        # Slots to background process
        self.background_process.new_data_signal.connect(self.new_data)
        self.background_process.radar_initialized_signal.connect(self.radar_initialized)

        # Start backgrund process
        background_process.start()

    def closeEvent(self, event):
        result = QtWidgets.QMessageBox.question(
            self, 'Confirm Exit', 'Are you sure you want to exit?',
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)

        if result == QtWidgets.QMessageBox.Yes:
            self.app.closeAllWindows()
            self.background_process.stop()
            event.accept()
        else:
            event.ignore()

    def radar_initialized(self):
        """Routine when the radar is initialized."""
        # Set initial values of the UI, and set values of background process
        self.ledit_sample_count.setText('%d' % 100)
        self.ledit_roi_min.setText('%.2f' % 0.15)
        self.ledit_roi_max.setText('%.2f' % 10)
        self.ledit_d1.setText('%.2f' % 0)
        self.ledit_d2.setText('%.2f' % 0)
        self.ledit_a_tot.setText('%.2f' % 0)
        self.ledit_r_off.setText('%.2f' % 0)
        self.cobox_direction.setCurrentIndex(0)
        self.cbox_nfc_clicked('cbox_nfc_none')  # Direct call of method as "clicked" signal is used

        # Status bar
        radar_config = self.background_process.get_radar_config()
        self.statusBar().showMessage(
            'Radar initialized: ' +
            'center frequency = %.2f GHz, ' % (radar_config['FREQUENCY']['CENTER'] / 1E9) +
            'bandwidth = %.2f GHz, ' % (abs(radar_config['FREQUENCY']['SPAN']) / 1E9) +
            'sweep time = %.2f ms' % (radar_config['SWEEP']['TIME'] * 1E3) +
            '!', 2000
        )

    def new_data(self, value):
        """Slot for incoming data."""
        if_data = value['if_data']
        self.distance = value['distance']
        self.snr = np.mean(value['snr_db'])
        self.signal_stength = np.mean(value['power_db'])
        self.refractivity = (np.mean(value['refractive_index']) - 1) * 1E6
        self.temp = value['temp']
        self.press = value['press']
        self.hum = value['hum']
        self.co2 = value['co2']

        # Add measured data to data container
        if self.measurement_started:
            if self.measurement_sample_idx < self.measurement_sample_count:
                self.measurement_data_container.add_measurements(
                    if_data=if_data,
                    distance=self.distance,
                    snr=self.snr,
                    signal_strength=self.signal_stength,
                    refractivity=self.refractivity,
                    temp=self.temp,
                    press=self.press,
                    hum=self.hum,
                    co2=self.co2
                )
                self.measurement_sample_idx += self.distance.size

    def cbox_nfc_clicked(self, name):
        # List of checkboxes
        names_list = [
            'cbox_nfc_none',
            'cbox_nfc_cfe',
            'cbox_nfc_pm',
            'cbox_nfc_func',
        ]
        # Ensure that only one necessary check box is selected
        for name_ in names_list:
            if name_ == name:
                getattr(self, name_).setChecked(True)
            else:
                getattr(self, name_).setChecked(False)
        # Call specific method
        {
            'cbox_nfc_none': lambda: self.background_process.set_nfc_none(),
            'cbox_nfc_cfe': lambda: self.ledit_d_changed(None),
            'cbox_nfc_pm': lambda: self.ledit_k_changed(None),
            'cbox_nfc_func': lambda: self.load_nfc_func(),
        }[name]()

    def cobox_direction_changed(self, value):
        self.background_process.set_direction(value.lower())

    def ledit_sample_count_changed(self, value):
        with suppress(ValueError):
            self.measurement_sample_count = int(value)
        self.btn_reset_clicked()  # Reset measured data

    def ledit_roi_changed(self, _):
        with suppress(ValueError):
            min_ = float(self.ledit_roi_min.text()) * 2 / 3E8
            max_ = float(self.ledit_roi_max.text()) * 2 / 3E8
            roi = [min_, max_]
            self.background_process.set_roi(roi)

    def ledit_d_changed(self, _):
        with suppress(ValueError):
            d1 = float(self.ledit_d1.text()) * 1E-3
            d2 = float(self.ledit_d2.text()) * 1E-3
            self.background_process.set_nfc_am(d1, d2)

    def ledit_k_changed(self, _):
        with suppress(ValueError):
            a_tot = float(self.ledit_a_tot.text()) * 1E-2**2
            r_off = float(self.ledit_r_off.text()) * 1E-2
            self.background_process.set_nfc_pm(a_tot, r_off)

    def btn_set_origin_clicked(self):
        self.background_process.set_as_origin()

    def btn_start_measurement_clicked(self):
        self.measurement_started = True

    def btn_load_preset_clicked(self):
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Load File', filter='Numpy files (*.npz)')
        if filename != '':
            data = np.load(filename)
            self.ledit_a_tot.setText('%.2f' % (data['a_tot'] / 1E-2**2))
            self.ledit_r_off.setText('%.2f' % (data['r_off'] / 1E-2))

    def btn_save_preset_clicked(self):
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Save File', filter='Numpy files (*.npz)')
        if filename != '':
            a_tot = float(self.ledit_a_tot.text()) * 1E-2**2
            r_off = float(self.ledit_r_off.text()) * 1E-2
            np.savez(filename, a_tot=a_tot, r_off=r_off)

    def btn_save_data_clicked(self):
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Save File', filter='CSV files (*.csv)')
        if filename != '':
            self.measurement_data_container.save_data(filename)
            self.statusBar().showMessage('Data saved sucessfully!', 2000)

    def btn_save_raw_data_clicked(self):
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Save File', filter='Numpy files (*.npz)')
        if filename != '':
            radar_config = self.background_process.get_radar_config()
            self.measurement_data_container.save_raw_data(filename, additional_data={'radar_config': radar_config})
            self.statusBar().showMessage('Raw data saved sucessfully!', 2000)

    def btn_reset_clicked(self):
        self.measurement_data_container.clear_data()
        self.table_measurements.setRowCount(0)
        self.statusBar().showMessage('Measurements cleared!', 2000)

    def load_nfc_func(self):
        """Load PPV function from file."""
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Load File', filter='Numpy files (*.npz)')
        if filename != '':
            data = np.load(filename)
            self.pulse_position_variation_func = interp1d(data['r'], data['pulse_position_variation'])
            self.pulse_phase_variation_func = interp1d(data['r'], data['pulse_phase_variation'])
            self.background_process.set_nfc_func(
                self.pulse_position_variation_func,
                self.pulse_phase_variation_func
            )
        else:
            self.cbox_nfc_clicked('cbox_nfc_none')

    def open_sub_window(self, win_object_name, win_class):
        """Open a new sub window."""
        if (getattr(self, win_object_name) is None) or (not getattr(self, win_object_name).isVisible()):
            # Open sub-window if window is not yet open
            setattr(self, win_object_name, win_class(self.background_process))
            getattr(self, win_object_name).show()
        elif getattr(self, win_object_name).isVisible():
            # Set window to focus
            getattr(self, win_object_name).activateWindow()

    def update_measured_data(self):
        """Slot to timer for updating user interface with measured data."""
        # Update estimates
        if self.distance is not None:
            self.ledit_distance_value.setText(gauge_formatter(np.mean(self.distance), 9))
            self.ledit_distance_std.setText(chr(177) + gauge_formatter(np.std(self.distance) * 1E6, 3))
        if self.signal_stength is not None:
            self.ledit_signal_strength.setText(gauge_formatter(self.signal_stength, 2))
        if self.snr is not None:
            self.ledit_snr.setText(gauge_formatter(self.snr, 2))

        # Update atmospheric data
        if self.temp is not None:
            self.ledit_temp.setText('%.2f' % self.temp)
        if self.hum is not None:
            self.ledit_hum.setText('%.2f' % self.hum)
        if self.press is not None:
            self.ledit_press.setText('%d' % round(self.press))
        if self.co2 is not None:
            self.ledit_co2.setText('%d' % round(self.co2))
        if self.refractivity is not None:
            self.ledit_refractivity.setText('%.2f' % self.refractivity)

        # Measurement of data
        if self.measurement_started:
            # Update progress bar
            progress = round((self.measurement_sample_idx + 1) / self.measurement_sample_count * 100)
            progress = 100 if progress > 100 else progress
            self.pbar_measurement.setValue(progress)
            # Update table widget
            if self.measurement_sample_idx >= self.measurement_sample_count:
                # Compute values for table item
                series_number = self.measurement_data_container.n_series + 1
                distance_mean = self.measurement_data_container.get_series_mean(-1)['distance']
                distance_std = self.measurement_data_container.get_series_std(-1)['distance']
                # Set table item
                row_position = self.table_measurements.rowCount()
                self.table_measurements.insertRow(row_position)
                self.table_measurements.setItem(
                    row_position, 0, QtWidgets.QTableWidgetItem('#%d' % series_number)
                )
                self.table_measurements.setItem(
                    row_position, 1, QtWidgets.QTableWidgetItem('%.9f' % distance_mean)
                )
                self.table_measurements.setItem(
                    row_position, 2, QtWidgets.QTableWidgetItem(chr(177) + '%.3f' % (distance_std * 1E6))
                )
                self.table_measurements.scrollToBottom()
                # Next measurement series
                self.measurement_started = False
                self.measurement_sample_idx = 0
                self.measurement_data_container.next_series()
