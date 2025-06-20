import serial
import time
from PyQt5.QtCore import QObject, pyqtSignal, Qt 
from PyQt5.QtWidgets import QWidget
from enum import Enum

class NPILaserStatus(Enum):
    POWER = "POWER"
    READY = "READY"
    ON = "ON"
    ERROR = "ERROR"
    DISCONNECTED = "DISCONNECTED"


class NPILaser(QObject):
    statusUpdate = pyqtSignal(bool)

    def __init__(self, parent:QWidget, port: str = None, baudrate: int = 115200, timeout:float = 1):
        super().__init__()
        self.parentWidget = parent
        self.parentWidget.setCursor(Qt.ArrowCursor)
        if port:
            self.port = port
            try:
                self.serial =  serial.Serial(port=f"COM{port}", baudrate=baudrate, timeout=timeout)
                self.connected = self.serial.is_open
                self.turnOff()
                self.configureRemote()
                self.status = self.getStatus()
            except serial.SerialException as e:
                print(f"[Serial Error] Could not open port COM{port}: {e}")
                self.serial = None
                self.connected = False
        else:
            self.connected = False
            self.serial = None
            self.status = NPILaserStatus.DISCONNECTED

    def sendCommand(self, command): # Send command to laser and wait for response
        if self.serial != None:
            full_command = command + '\r'
            self.serial.write(full_command.encode())
            self.parentWidget.setCursor(Qt.WaitCursor)
            time.sleep(0.9)
            self.parentWidget.setCursor(Qt.ArrowCursor)
            response = self.serial.read_all().decode().strip()
            return response
        else:
            print(command)
            return ""
    

    def turnOff(self): # Turn off laser
        if self.status != NPILaserStatus.DISCONNECTED:
            self.statusUpdate.emit(False)
            return self.sendCommand("sEmission_flag0")
        else: 
            return ""

    def turnOn(self): # Turn on laser
        if self.status == NPILaserStatus.READY:
            self.statusUpdate.emit(True)
            return self.sendCommand("sEmission_flag1")
        else: 
            return ""


    def disconnect(self): # Disconnect from laser
        self.turnOff()
        self.serial.close()
        self.connected = False

    
    def configureRemote(self, local = 0): # Configure whether to locally interact with the motor or via software
        return self.sendCommand(f"sRemote_flag{local}")
    

    def getStatus(self): # Get current status of laser
        response = str(self.sendCommand("gstatus"))
        #print(response)
        cuttedResponse = response[11:]
        if len(cuttedResponse) != 4 or not all(c in "01" for c in cuttedResponse):
            print(f"Ungültige response: {cuttedResponse}")
            return NPILaserStatus.DISCONNECTED

        bits = int(cuttedResponse, 2)
        if bits & 0b0001:
            self.status = NPILaserStatus.ERROR
            return NPILaserStatus.ERROR
        elif bits & 0b0010:
            self.status = NPILaserStatus.ON
            return NPILaserStatus.ON
        elif bits & 0b0100:
            self.status = NPILaserStatus.READY
            return NPILaserStatus.READY
        elif bits & 0b1000:
            self.status = NPILaserStatus.POWER
            return NPILaserStatus.POWER
        else: 
            return NPILaserStatus.DISCONNECTED

