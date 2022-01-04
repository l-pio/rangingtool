# rangingTool
A graphical user interface, written in Python, to conduct distance measurements using 2pi-Labs's 2piSENSE radar systems
and atmospheric sensors from Dracal.

Note: rangingTool requires Python 3.9.

## Installation
Please simply copy the package directory to your workspace, and install the requirements by running:
```
$ pip install -r requirements.txt
```

## Usage
Examples:
```
$ python3 run.py --radar_serial_number U202921D2677EF5B8 --atm_sensor_comport COM5 --co2_sensor_comport COM4
```
or
```
$ python3 run.py --radar_serial_number U202921D2677EF5B8
```
