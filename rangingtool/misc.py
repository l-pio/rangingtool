import numpy as np


def gauge_formatter(value, precision):
    """Format float value for gauge of the user interface."""
    decimal_separator = '.'
    thousands_separator = ' '

    # Handle "nan"
    if np.isnan(value):
        return 'nan'

    # Compute integer and fractional part of value
    sign = int(np.sign(value))
    integer = [int(digit) for digit in '%d' % ((sign * value) // 1)]
    fractional = [int(digit) for digit in (('%.' + ('%d' % precision) + 'f') % ((sign * value) % 1))[2:]]

    # Create List of characters
    loc = [{0: '', 1: '', -1: '-'}[sign]]
    loc += [
               '%d' % value + thousands_separator if (idx != 0) and (idx % 3 == 0) else '%d' % value
               for idx, value in enumerate(integer[::-1])
           ][::-1]
    loc += decimal_separator
    loc += [
        thousands_separator + '%d' % value if (idx != 0) and (idx % 3 == 0) else '%d' % value
        for idx, value in enumerate(fractional)
    ]

    return ''.join(loc)


class MeasurementDataContainer:
    """Container for measurement data."""
    def __init__(self):
        """Initialize container."""
        self.entries = [
            'if_data',
            'distance',
            'snr',
            'signal_strength',
            'refractivity',
            'temp',
            'press',
            'hum',
            'co2'
        ]

        self.n_series = None
        self.clear_data()

    def add_measurements(self, **kwargs):
        """Add measurements to the current series of the container."""
        for key in kwargs:
            if key in self.entries:
                value = kwargs[key]
                getattr(self, key)[self.n_series].append(value)

    def next_series(self):
        """Increment measurement series."""
        self.n_series += 1
        for entry in self.entries:
            getattr(self, entry).append([])

    def clear_data(self):
        """Clear measurement data."""
        self.n_series = 0
        for entry in self.entries:
            setattr(self, entry, [[]])

    def get_series_mean(self, n=None):
        """Get mean measurement data of series n."""
        data = {}
        for entry in self.entries:
            if entry != 'if_data':
                try:
                    if n is not None:
                        data[entry] = np.mean(getattr(self, entry)[n])
                    else:
                        data[entry] = np.asarray([np.mean(_data) for _data in getattr(self, entry) if len(_data) > 0])
                except TypeError:  # If data is not available
                    data[entry] = None
        return data

    def get_series_std(self, n=None):
        """Get standard deviation of measurement data of series n."""
        data = {}
        for entry in self.entries:
            if entry != 'if_data':
                try:
                    if n is not None:
                        data[entry] = np.std(getattr(self, entry)[n])
                    else:
                        data[entry] = np.asarray([np.std(_data) for _data in getattr(self, entry) if len(_data) > 0])
                except TypeError:  # If data is not available
                    data[entry] = None
        return data

    def save_data(self, filename):
        """Save processed measurement data to CSV file."""
        data = self.get_series_mean()
        delimiter = ','
        header = ''.join([key + ',' for key in data])[:-1]
        data_array = np.asarray([data[key] for key in data]).T

        np.savetxt(filename, data_array, header=header, fmt='%.9E', delimiter=delimiter, newline='\n')

    def save_raw_data(self, filename, additional_data=None):
        """Save raw measurement data including configuration as numpy file."""
        data = {'if_data': np.asarray([_data for _data in self.if_data if len(_data) > 0])}
        data.update(self.get_series_mean())
        if additional_data is not None:
            data.update(additional_data)  # Config etc.

        np.savez_compressed(filename, **data)
