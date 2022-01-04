import sys
from PyQt5 import QtWidgets, QtGui
import argparse
from rangingtool import MainWindow
from rangingtool import BackgroundProcess


def main():
    # Init argument parser
    parser = argparse.ArgumentParser()
    parser.add_argument('--radar_serial_number', type=str, required=False)
    parser.add_argument('--atm_sensor_comport', type=str, required=False)
    parser.add_argument('--co2_sensor_comport', type=str, required=False)
    args = parser.parse_args()

    # Init QT application
    app = QtWidgets.QApplication(sys.argv)

    # Dark style
    app.setStyle('Fusion')
    dark_palette = QtGui.QPalette()
    dark_palette.setColor(QtGui.QPalette.Window, QtGui.QColor(53, 53, 53))
    dark_palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor(255, 255, 255))
    dark_palette.setColor(QtGui.QPalette.Base, QtGui.QColor(61, 70, 76))
    dark_palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(185, 206, 25))
    dark_palette.setColor(QtGui.QPalette.ToolTipBase, QtGui.QColor(255, 255, 255))
    dark_palette.setColor(QtGui.QPalette.ToolTipText, QtGui.QColor(255, 255, 255))
    dark_palette.setColor(QtGui.QPalette.Text, QtGui.QColor(255, 255, 255))
    dark_palette.setColor(QtGui.QPalette.Button, QtGui.QColor(53, 53, 53))
    dark_palette.setColor(QtGui.QPalette.ButtonText, QtGui.QColor(255, 255, 255))
    dark_palette.setColor(QtGui.QPalette.BrightText, QtGui.QColor(255, 0, 0))
    dark_palette.setColor(QtGui.QPalette.Link, QtGui.QColor(42, 130, 218))
    dark_palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(42, 130, 218))
    dark_palette.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor(0, 0, 0))
    app.setPalette(dark_palette)

    # Start background process
    background_process = BackgroundProcess(
        radar_serial_number=args.radar_serial_number,
        atm_sensor_comport=args.atm_sensor_comport,
        co2_sensor_comport=args.co2_sensor_comport
    )
    app.aboutToQuit.connect(background_process.stop)

    # Show main window
    win = MainWindow(app, background_process)
    win.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
