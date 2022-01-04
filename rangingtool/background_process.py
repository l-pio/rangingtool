import numpy as np
from PyQt5 import QtCore
from contextlib import ExitStack
from warnings import warn
from twopilabs.sense.x1000 import SenseX1000
from twopilabs.utils.usbtmc.usbtmc_exception import UsbTmcTimeoutException
import mmwranging
import dracalvcp


class BackgroundProcess(QtCore.QObject):
    """Background process for user interface."""
    # Signals from worker
    new_data_signal = QtCore.pyqtSignal(object)
    radar_initialized_signal = QtCore.pyqtSignal()

    # Signals to worker
    set_proc_attribute_signal = QtCore.pyqtSignal(str, object)
    call_proc_method_signal = QtCore.pyqtSignal(str, object)

    # Set offset on RTT, i.e., to properly correct PPV and as an initial value for the distance origin
    # rtt_offset = 500E-12

    def __init__(self, radar_serial_number=None, atm_sensor_comport=None, co2_sensor_comport=None):
        """Initialize background process."""
        super().__init__()

        # Init worker thread
        self.thread = QtCore.QThread(self)
        self.moveToThread(self.thread)
        self.thread.started.connect(self.worker)
        self.is_running = False

        # Slots from worker thread
        self.set_proc_attribute_signal.connect(
            lambda attribute_name, attribute_value: setattr(self._proc, attribute_name, attribute_value)
        )
        self.call_proc_method_signal.connect(
            lambda method_name, kwargs: getattr(self._proc, method_name)(**kwargs)
        )

        # Devices
        radar_devices = SenseX1000.find_devices()
        if len(radar_devices) < 1:
            raise Exception('No Sense X1000 devices found')

        if radar_serial_number is None:
            # Use first device
            self.radar_device = radar_devices[0]
        else:
            # Search for device with respective ID
            try:
                self.radar_device = {
                    device.serialnum.upper(): device for device in radar_devices
                }[radar_serial_number.upper()]
            except KeyError:
                raise Exception('Sense X1000 device not found')

        self.atm_sensor_comport = atm_sensor_comport
        self.co2_sensor_comport = co2_sensor_comport

        # Processor
        self._proc = None

    def _set_proc_attribute(self, attribute_name, attribute_value):
        """Slot for threadsafe set of processor attribute."""
        setattr(self.proc, attribute_name, attribute_value)

    def _call_proc_method(self, method_name, **kwargs):
        """Slot for threadsafe call of processor method."""
        getattr(self.proc, method_name)(**kwargs)

    def start(self):
        self.is_running = True
        self.thread.start()

    def stop(self):
        self.is_running = False
        self.thread.quit()
        self.thread.wait()

    def set_as_origin(self):
        """Set origin."""
        if self._proc is not None:
            self.call_proc_method_signal.emit('set_as_origin', {})

    def set_direction(self, direction):
        """Set direction of measurement."""
        if self._proc is not None:
            self.set_proc_attribute_signal.emit('direction', direction)

    def set_roi(self, roi):
        """Set ROI."""
        if self._proc is not None:
            self.set_proc_attribute_signal.emit('roi', roi)

    def set_nfc_none(self):
        """Disable near-field correction."""
        if self._proc is not None:
            self.set_proc_attribute_signal.emit('nearfield_correction', None)

    def set_nfc_am(self, d1, d2):
        """Set approximate model for near-field correction."""
        if self._proc is not None:
            self.set_proc_attribute_signal.emit('nearfield_correction',
                                                {'mode': 'AM', 'd1': d1, 'd2': d2, 'rtt_offset': 500E-12})

    def set_nfc_pm(self, a_tot, r_off):
        """Set parametric model for near-field correction."""
        if self._proc is not None:
            self.set_proc_attribute_signal.emit('nearfield_correction',
                                                {'mode': 'PM', 'a_tot': a_tot, 'r_off': r_off})

    def set_nfc_func(self, pulse_position_variation_func, pulse_phase_variation_func):
        """Set function for compensation for near-field correction."""
        if self._proc is not None:
            self.set_proc_attribute_signal.emit('nearfield_correction',
                                                {'mode': 'func',
                                                 'pulse_position_variation_func': pulse_position_variation_func,
                                                 'pulse_phase_variation_func': pulse_phase_variation_func})

    def get_radar_config(self):
        """Get configuration of radar."""
        return self._radar_config

    def do_rf_path_calibration(self):
        """Do RF path calibration."""
        if self._proc is not None:
            self.call_proc_method_signal.emit('do_rf_path_calibration', {})

    def get_rf_path_response(self):
        """Get RF path response."""
        if self._proc is not None:
            return {'freq': self._proc.freq_axis, 'response': self._proc.rf_path_response}

    def load_rf_path_response(self, freq, response):
        """Load RF path response from data."""
        if self._proc is not None:
            self.call_proc_method_signal.emit('load_rf_path_response', {'freq': freq, 'response': response})

    def worker(self):
        """Start main loop of background process."""
        with ExitStack() as stack:
            # Conditional opening of devices
            radar_device = stack.enter_context(SenseX1000.open_device(self.radar_device))

            if self.atm_sensor_comport is not None:
                atm_sensor_device = stack.enter_context(dracalvcp.Device(self.atm_sensor_comport))
            else:
                atm_sensor_device = None

            if self.co2_sensor_comport is not None:
                co2_sensor_device = stack.enter_context(dracalvcp.Device(self.co2_sensor_comport))
            else:
                co2_sensor_device = None

            # Recall preset and clear registers
            radar_device.core.rst()
            radar_device.core.cls()

            # Configure radar
            radar_device.sense.frequency_start(182E9)
            radar_device.sense.frequency_stop(126E9)
            radar_device.sense.sweep_time(2E-3)
            radar_device.sense.sweep_count(2 * 3)
            radar_device.sense.sweep_period(10E-3)
            radar_device.sense.sweep_mode(getattr(SenseX1000.SweepMode, 'ALTERNATING'))
            radar_device.calc.trace_list([0])  # Centered channel
            radar_device.control.accessory_enable(False)  # Disable LED
            self._radar_config = radar_device.sense.dump()  # Dump radar configuration

            # Update effective center frequency
            self._radar_config['FREQUENCY']['CENTER'] = 154007370664

            # Init ranging processor
            if_data_order = {
                True: 'ud',
                False: 'du'
            }[self._radar_config['FREQUENCY']['STOP'] > self._radar_config['FREQUENCY']['START']]

            self._proc = mmwranging.Processor(
                self._radar_config['FREQUENCY']['CENTER'],
                abs(self._radar_config['FREQUENCY']['STOP'] - self._radar_config['FREQUENCY']['START']),
                self._radar_config['SWEEP']['TIME'],
                self._radar_config['SWEEP']['POINTS'],
                td_length=self._radar_config['SWEEP']['POINTS'] * 1,
                use_triangular_modulation=True,
                use_phase=True,
                if_data_order=if_data_order,
                estimator='QIPS',
                window='hann',
                refractive_index_model='dband' if atm_sensor_device is not None else None,  # Use C0 if no atm device
                if_path_filter='phase',
                nearfield_correction=None
            )

            # Load default signal calibration (RF-path frequency response)
            data = np.load('./calibration/rf_path_2piSENSE.npz')
            self._proc.load_rf_path_response(data['freq'], data['response'])

            # Load default IF-path frequency response
            data = np.genfromtxt('./calibration/if_path_sim_2piSENSE.txt', delimiter=',', skip_header=1).T
            self._proc.load_if_path_response(data[0], 10 ** (data[1] / 20) * np.exp(1j * data[2] / 180 * np.pi))

            # Set initial origin
            # self._proc.origin = -self.rtt_offset * mmwranging.C0 / 2

            # Emit radar initialized signal
            self.radar_initialized_signal.emit()

            # Processing loop
            self.is_running = True
            while self.is_running:
                # Read data from radar
                try:
                    acq = radar_device.initiate.immediate_and_receive()  # Initiate initial data (non-blocking)
                    data = acq.read()  # Blocking
                except UsbTmcTimeoutException:
                    warn('USB TMC timeout')
                    continue

                # Push IF data into processor
                if_data = data.array[:, 0, :]  # [#Sweep, #Trace, #Sample]
                if_data = if_data / (2 ** (8 * data.header.data_size - 1))  # Normalize data
                self._proc.update_if_data(if_data)

                # Push atmospheric data into processor
                if atm_sensor_device is not None:
                    temp_data = atm_sensor_device.get_temp()
                    press_data = atm_sensor_device.get_press()
                    hum_data = atm_sensor_device.get_hum()
                else:
                    temp_data = press_data = hum_data = None

                if co2_sensor_device is not None:
                    co2_data = co2_sensor_device.get_co2()
                else:
                    co2_data = None

                self._proc.update_atmospheric_data(
                    temp_data + 273.15 if temp_data is not None else None,
                    press_data,
                    hum_data,
                    co2_data * 1E-6 if co2_data is not None else None
                )

                # Emit signals of raw and processed data
                self.new_data_signal.emit({
                    'if_data': if_data,
                    'time_axis': self._proc.time_axis,
                    'td_data_db': self._proc.td_data_db,
                    'distance': self._proc.distance,
                    'snr_db': self._proc.snr_db,
                    'power_db': self._proc.power_db,
                    'refractive_index': self._proc.refractive_index,
                    'temp': temp_data,
                    'press': press_data,
                    'hum': hum_data,
                    'co2': co2_data
                })

