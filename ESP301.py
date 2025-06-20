import serial
import time
import numpy as np
from PyQt5.QtCore import QTimer, QObject, pyqtSignal, Qt
from PyQt5.QtWidgets import QWidget
from enum import Enum
from NPILaser import NPILaser, NPILaserStatus

class ESP301Status(Enum):
    READY = "ready"
    MOVING = "moving"
    GROUP_MOVING = "groupMoving"
    DISCONNECTED = "disconnected"
    OFF = "off"   

class ESP301(QObject):
    statusUpdate = pyqtSignal(str)
    groupMoveNextStep = pyqtSignal(str)

    def __init__(self, parent:QWidget, port: str=None, baudrate: int = 921600, timeout:float = 1):
        super().__init__()
        self.parentWidget = parent
        self.parentWidget.setCursor(Qt.ArrowCursor)
        self.pixel_size = 0.000089 #mm
        self.joystickMode = False #False: Command Mode, True: Joystick Mode
        self.activeGroup = False
        
        self.currentPosition = [0.0000, 0.0000, 0.0000]
        self.currentMotorsPosition = [0.0000, 0.0000, 0.0000]
        self.lastMotorDirection = [1, 1, 1] #1 positive, 0 negative
        self.backlash = [0.012, 0.009, 0] #mm #IS CHANGING THE WHOLE TIME?
        self.motorHasOffset = [False, False, False]
        self.waitingForGroupMovementFinish = False
        self.stopGM = False
    
        self.velocity = 0.2
        self.acceleration = 0.8
        self.motor = True
        if port:
            self.port = port
            if port == "": return
            try:
                self.esp301 = serial.Serial(port=f"COM{port}", baudrate=baudrate, timeout=timeout)
                self.connected = self.esp301.is_open
                self.currentPosition = [self.getPosition(1), self.getPosition(2), self.getPosition(3)]
                self.acceleration = self.getAcceleration()
                self.velocity = self.getVelocity()
                self.motor_on()
                self.breakGroup() #In case Group existed
                self.changeToCommandMode()
                self.setLastDirectionsMotors()

            except serial.SerialException as e:
                print(f"[Serial Error] Could not open port COM{port}: {e}")
                self.currentPosition = [2.2, 3.1, 4.2]
                self.esp301 = None
                self.connected = False
                self.status = ESP301Status.DISCONNECTED
                self.updateStatus()

        else:
            self.status = ESP301Status.DISCONNECTED
            self.connected = False



    def send_command(self, command:str): # Send a command and wait for response
        if self.esp301 != None:
            full_command = command + '\r'
            self.esp301.write(full_command.encode())
            self.parentWidget.setCursor(Qt.WaitCursor)
            time.sleep(0.2)
            self.parentWidget.setCursor(Qt.ArrowCursor)
            response = self.esp301.read_all().decode().strip()
            return response
        else:
            print(command)
            return ""


    def send_command_without_reading(self, command:str): # Used for async fetches
        if self.esp301 != None:
            full_command = command + '\r'
            self.esp301.write(full_command.encode())
        else:
            print(command)


    def read_response(self): # Used for async fetches
        if self.esp301 != None:
            response = self.esp301.read_all().decode().strip()
            return response


    def disconnect(self):
        self.esp301.close()
        self.connected = False
        self.updateStatus()

    def updateStatus(self):
        if not self.connected: return
        response = self.send_command("TS")
        try:
            response = response.split("\n")[-1]
            status_byte = ord(response) if response else 0
        except TypeError:
            print("[Status Error] Could not decode response for status.", response)
            self.status = ESP301Status.DISCONNECTED
            return

        # Bit 4 = Motor power on (1) or off (0)
        motor_power_on = bool(status_byte & (1 << 4))
        # Bits 0–3 = Movement status of 4 motors (1 = in movement)
        motion_bits = status_byte & 0x0F
        moving_motors = []
        for i in range(4):
            if (motion_bits >> i) & 1:
                moving_motors.append(i+1)

        # Statuslogik
        if not motor_power_on and not self.waitingForGroupMovementFinish: #If waiting for certain group movement to finish, controller will not return anything
            self.motor = False
            self.status = ESP301Status.OFF
        elif motor_power_on and len(moving_motors) == 0 and not self.activeGroup and not self.joystickMode:
            self.status = ESP301Status.READY
            self.currentPosition = [self.getPosition(1), self.getPosition(2), self.getPosition(3)]
            #print(tuple(self.currentPosition))
            #print(tuple(self.currentMotorsPosition))
            self.statusUpdate.emit(str(tuple(self.currentPosition)))
        elif len(moving_motors) == 1:
            self.status = ESP301Status.MOVING
            self.waitForMovement(moving_motors[0])
        elif len(moving_motors) >= 2 or self.activeGroup or self.joystickMode:
            self.status = ESP301Status.GROUP_MOVING
            self.waitForMovement()
        else:
            return "Unbekannter Status"

    # Settings
    def motor_on(self, axis: np.array=np.array([1, 2, 3])):  # Turns motors of axis [1, 2 , 3] on
        self.motor = True
        command = ""
        for i in axis:
            command += f"{i}MO;"
        self.send_command(command)
        self.updateStatus()


    def motor_off(self, axis: np.array=np.array([1, 2, 3])): # Turns motors off
        self.motor = False
        command = ""
        for i in axis:
            command += f"{i}MF;"
        self.send_command(command)
        self.updateStatus()


    def setVelocity(self, value: float): # Values between 0 and 0.4
        if 0< value <= 0.4:
            self.send_command(f"1VA{value}; 2VA{value}")
            self.velocity = self.getVelocity()
            self.statusUpdate.emit(str(self.currentPosition))
        else: return False


    def getVelocity(self): # Returns current velocity setting
         return self.safeFloat(self.send_command("1VA?"))
            

    def getAcceleration(self): # Returns current acceleration setting
        return self.safeFloat(self.send_command("1AC?"))

    def setAcceleration(self, value: float): # Values between 0 and 1.8
        if 0< value <= 1.8:
            self.send_command(f"1AC{value}; 2AC{value}")
            self.acceleration = self.getAcceleration()
            self.statusUpdate.emit(str(self.currentPosition))
        else: return False

    # Position
    def goToHome(self, axis:int): # Goes to Home Position
        self.send_command(f"{axis}OR")
        self.updateStatus()


    def setLastDirectionsMotors(self): # When not knowing what the last direction of motors are, performs a group movement to establish it
        self.defineGroup(1, 2)
        self.handleGroupMovement([f"line;{self.currentPosition[0]};{self.currentPosition[1]};{self.currentPosition[0]-0.02};{self.currentPosition[1]-0.02}"], 0, 0)

    def setAbsPosition(self, axis:int, position: float): # Goes to specific absolute position between 0 and 12
        if 0<= position<=12:
            adjustedPosition = position
            if position > self.currentPosition[axis-1]:
                if self.lastMotorDirection[axis-1] == 0: #If direction change and true movement
                    self.lastMotorDirection[axis-1] = 1
                    if self.motorHasOffset[axis-1]: #If has offset removes it, as error in two contrary movements cancel each other out
                        self.motorHasOffset[axis-1] = False
                    else:
                        adjustedPosition += self.backlash[axis-1]
                        self.motorHasOffset[axis-1] = True
                elif self.motorHasOffset[axis-1]:
                    adjustedPosition += self.backlash[axis-1]
            elif position < self.currentPosition[axis-1]:
                if self.lastMotorDirection[axis-1] == 1: #If direction change and true movement
                    self.lastMotorDirection[axis-1] = 0
                    if self.motorHasOffset[axis-1]:
                        self.motorHasOffset[axis-1] = False
                    else:
                        adjustedPosition -= self.backlash[axis-1]
                        self.motorHasOffset[axis-1] = True
                elif self.motorHasOffset[axis-1]:
                    adjustedPosition -= self.backlash[axis-1]
            elif position == self.currentPosition[axis-1] and self.motorHasOffset[axis-1]:
                    if self.lastMotorDirection[axis-1] == 1:
                        adjustedPosition += self.backlash[axis-1]
                    else:
                        adjustedPosition -= self.backlash[axis-1]

            self.send_command_without_reading(f"{axis}PA{round(adjustedPosition, 5)}")
            self.updateStatus()
        else: return False

    def setRelPosition(self, axis:int, position: float): # Moves distance relative to current position. This does not consider the last movement direction! Use abs position to get reliable position
        self.getPosition(axis)
        currentPosition = self.currentMotorsPosition[axis-1]
        endAbsPosition = self.safeFloat(currentPosition)+position
        if 0<= endAbsPosition<=12:
            self.send_command_without_reading(f"{axis}PR{position}")
            self.updateStatus()
        else: return False

    def getPosition(self, axis:int): # Returns current position
        value = self.safeFloat(self.send_command(f"{axis}TP?"))
        self.currentMotorsPosition[axis-1] = value
        if self.motorHasOffset[axis-1]:
            return round((value-self.backlash[axis-1]) if self.lastMotorDirection == 1 else (value+self.backlash[axis-1]), 5)
        return round(value, 5)


    # Wait, Delays, Stops
    def waitForMovement(self, axis: int = 1): #Performs Async Code that keeps checking position when controller in movement
        if self.status == ESP301Status.MOVING or self.status == ESP301Status.GROUP_MOVING:
            if not self.activeGroup and not self.joystickMode:
                self.send_command_without_reading(f"{axis}TP?")
            else:
                self.send_command_without_reading("1HP")
            self.checksNotMoving = 0
            self.fetchedCurrentPosition = str(self.currentPosition)
            self.checkAsyncPosition(axis)

    def checkAsyncPosition(self, axisInMov): #Handles async calls of function
        self.checkPosAsyncStartTime = time.time()
        self.checkPosAsyncTimer = QTimer()
        self.checkPosAsyncTimer.timeout.connect(lambda: self.fetchPositionLoop(axisInMov))
        self.checkPosAsyncTimer.start(200)

    def fetchPositionLoop(self, axisInMov): #Fetches asynchroniously the current position, updates GUI and handles in GM steps
        response = self.read_response()
        if response == "": 
            self.checkPosAsyncTimer.stop()
            self.checkAsyncPosition(axisInMov)
            return
        if response != self.fetchedCurrentPosition:
            self.fetchedCurrentPosition = response
        elif not self.waitingForGroupMovementFinish: self.checksNotMoving += 1

        if self.checksNotMoving > 2:
            self.checkPosAsyncTimer.stop()
            #print("Stopped Moving")
            if self.activeGroup:
                if (self.groupMoveType == "quadr" or self.groupMoveType == "rect" or self.groupMoveType == "del_rect" or self.groupMoveType == "subrect" or self.currentStepGM == 0) and not self.stopGM:
                    self.currentStepGM += 1
                elif self.currentStepGM == 1 or self.stopGM:
                    self.currentStepGM = 5
                self.handleGroupMovement(self.currentInstructions, self.currentInstructionItem, self.currentStepGM, self.cutInGM, self.laserController)
            else:
                self.updateStatus()

        else:
            if not self.activeGroup and not self.joystickMode:
                floatFetchedCurrentPosition = self.safeFloat(self.fetchedCurrentPosition)
                
                self.currentMotorsPosition[axisInMov-1] = round(floatFetchedCurrentPosition, 5)
                offsetedCurrentPosition = floatFetchedCurrentPosition
                updateCurrentPosition = True
                if self.motorHasOffset[axisInMov-1]:
                    offsetedCurrentPosition = (floatFetchedCurrentPosition-self.backlash[axisInMov-1]) if self.lastMotorDirection == 1 else (floatFetchedCurrentPosition+self.backlash[axisInMov-1])
                    if (offsetedCurrentPosition<self.currentPosition[axisInMov-1] if self.lastMotorDirection == 1 else offsetedCurrentPosition>self.currentPosition[axisInMov-1]):
                        updateCurrentPosition = False
                elif (self.currentPosition[axisInMov-1]<self.currentMotorsPosition[axisInMov-1] if self.lastMotorDirection == 1 else self.currentPosition[axisInMov-1]>self.currentMotorsPosition[axisInMov-1]):
                    updateCurrentPosition = False

                if updateCurrentPosition:
                    self.currentPosition[axisInMov-1] = round(offsetedCurrentPosition, 5)
                    self.statusUpdate.emit(str(tuple(self.currentPosition)))
                self.send_command_without_reading(f"{axisInMov}TP?")
            else:
                self.send_command_without_reading("1HP")
                fetchedPositionXY = [p.strip() for p in self.fetchedCurrentPosition.split("\n")[-1].strip("()").split(",")]
                try: 
                    floatFetchedPositionXY = [self.safeFloat(fetchedPositionXY[0]),  self.safeFloat(fetchedPositionXY[1])]
                    self.waitingForGroupMovementFinish = False #Otherwise would not recieve anything
                    self.currentMotorsPosition[0] = round(floatFetchedPositionXY[0], 5)
                    self.currentMotorsPosition[1] = round(floatFetchedPositionXY[1], 5)
                    offsetedCurrentPosition = floatFetchedPositionXY
                    updateCurrentPosition = [True, True]
                    for axis in range(len(floatFetchedPositionXY)):
                        if self.motorHasOffset[axis]:
                            offsetedCurrentPosition[axis] = (floatFetchedPositionXY[axis]-self.backlash[axis]) if self.lastMotorDirection == 1 else (floatFetchedPositionXY[axis]+self.backlash[axis])
                            if (offsetedCurrentPosition[axis]<self.currentPosition[axis] if self.lastMotorDirection == 1 else offsetedCurrentPosition[axis]>self.currentPosition[axis]):
                                updateCurrentPosition[axis] = False
                        elif (self.currentPosition[axis]<self.currentMotorsPosition[axis] if self.lastMotorDirection == 1 else self.currentPosition[axis]>self.currentMotorsPosition[axis]):
                            updateCurrentPosition[axis] = False
                        
                    if updateCurrentPosition[0]: self.currentPosition[0] = round(offsetedCurrentPosition[0], 5)
                    if updateCurrentPosition[1]: self.currentPosition[1] = round(offsetedCurrentPosition[1], 5)
                    self.statusUpdate.emit(str(tuple(self.currentPosition)))
                except: print("Loading", response)
                
            self.checkPosAsyncTimer.stop()
            self.checkAsyncPosition(axisInMov)

    def abortMotion(self): #Stops all kind of movement
        self.motor = False
        self.send_command("AB")
        self.updateStatus()

    def stopMotion(self, axis:int): #Stops movement of certain axis:int
        return self.send_command(f"{axis}ST")
    
    def stopGroupMovement(self):
        if self.activeGroup:
            self.stopGM = True
            self.send_command("1HS")

    # Group Movement (GM) i.e Design
    def handleGroupMovement(self, instructions, item:int = 0, step:int = 0, cut = False, laserController: NPILaser = None):
        #print(f"Handling GM at step {step}")
        if step == 0 and instructions != []: #Step 0: Defining Group Movement (GM), handling instructions, going to Start-coordinates
            self.currentInstructions = instructions
            self.currentInstructionItem = item
            currentGMItem = instructions[item]
            self.currentStepGM = step
            #print("Handling instruction Item: ", currentGMItem)
            self.instrPartsGM = currentGMItem.split(";") # Example instructions: "line;3.0;4.0;2.2;3.3"
            self.groupMoveType = self.instrPartsGM[0]
            self.cutInGM = cut
            self.laserController = laserController

            if self.laserController != None and item == 0 and self.cutInGM:
                if self.laserController.status != NPILaserStatus.DISCONNECTED: self.laserController.turnOff(); self.laserController.status = self.laserController.getStatus()

            laserSpotWidth = 0.001 #mm (1 micron)
            if self.groupMoveType == "rect" and self.instrPartsGM[10] != 0: #Check if has surface to burn
                # Update Instructions: Create many rectangles around cutted rectangle, that will be performed to burn surface
                absBurnSurfaceWidth = int(self.instrPartsGM[10])*self.pixel_size
                hypoBurnSurfaceWidth = np.sqrt(2)*absBurnSurfaceWidth
                rectCornerExpansionStep = round(hypoBurnSurfaceWidth/laserSpotWidth)
                
                cornerPositions = np.array([self.safeFloat(e) for e in self.instrPartsGM[1:9]])
                corners = cornerPositions.reshape(-1,2)

                for i in range(1, rectCornerExpansionStep+1):
                    newCorners = np.array([])
                    v1 = corners[1]-corners[0]
                    v2 = corners[3]-corners[0]
                    axis_x = v1/np.linalg.norm(v1)
                    axis_y = v2/np.linalg.norm(v2)

                    center = np.mean(corners, axis=0)

                    signs = [(-1, -1), (1, -1), (1, 1), (-1, 1)]

                    for sign_x, sign_y in signs:
                        corner = center+sign_x*(np.linalg.norm(v1)/2+i*laserSpotWidth)*axis_x + sign_y*(np.linalg.norm(v2)/2+i*laserSpotWidth)*axis_y
                        newCorners = np.append(newCorners, corner)

                    newCorners = newCorners.flatten()
                    newCorners = np.round(newCorners, 5)
                    self.currentInstructions.insert(self.currentInstructionItem+i, f"subrect;{newCorners[0]};{newCorners[1]};{newCorners[2]};{newCorners[3]};{newCorners[4]};{newCorners[5]};{newCorners[6]};{newCorners[7]};{self.instrPartsGM[9]};0;")
            
            if self.groupMoveType == "del_rect":
                cornerPositions = np.array([self.safeFloat(e) for e in self.instrPartsGM[1:9]])
                corners = cornerPositions.reshape(-1,2)
                laserSpotWidth = 0.001 #mm (1 micron)
                

                side1 = np.sqrt((corners[1][0]-corners[0][0])**2 + (corners[1][1]-corners[0][1])**2)
                side2 = np.sqrt((corners[2][0]-corners[1][0])**2 + (corners[2][1]-corners[1][1])**2)

                width = min(side1, side2)/2
                rectCornerExpansionStep = round(width/laserSpotWidth)
                for i in range(1, rectCornerExpansionStep+1):
                    newCorners = np.array([])
                    v1 = corners[1]-corners[0]
                    v2 = corners[3]-corners[0]
                    axis_x = v1/np.linalg.norm(v1)
                    axis_y = v2/np.linalg.norm(v2)

                    center = np.mean(corners, axis=0)

                    signs = [(-1, -1), (1, -1), (1, 1), (-1, 1)]

                    for sign_x, sign_y in signs:
                        corner = center+sign_x*(np.linalg.norm(v1)/2-i*laserSpotWidth)*axis_x + sign_y*(np.linalg.norm(v2)/2-i*laserSpotWidth)*axis_y #Same as normal rect but with -, since rectangles are getting smaller
                        newCorners = np.append(newCorners, corner)

                    newCorners = newCorners.flatten()
                    newCorners = np.round(newCorners, 5)
                    self.currentInstructions.insert(self.currentInstructionItem+i, f"subrect;{newCorners[0]};{newCorners[1]};{newCorners[2]};{newCorners[3]};{newCorners[4]};{newCorners[5]};{newCorners[6]};{newCorners[7]};{self.instrPartsGM[9]};0;")

            startX = self.safeFloat(self.instrPartsGM[1])
            startY = self.safeFloat(self.instrPartsGM[2])
            if not self.groupMoveLine(startX, startY):
                if self.laserController != None or self.stopGM:
                        if (self.laserController.status != NPILaserStatus.DISCONNECTED if self.laserController != None else True) and self.cutInGM:
                            self.laserController.turnOff()
                            self.laserController.status = self.laserController.getStatus()  
                self.breakGroup()
                print("Could not perform Group-Movement because of drawing at limits")
                return

        elif step == 1: #Step 1: Turn on laser -> Move line | Move to second corner | Move arc
            if self.cutInGM and self.laserController != None:
                if self.laserController.status == NPILaserStatus.READY:
                    self.laserController.turnOn()
                    self.laserController.status = self.laserController.getStatus()

            if self.groupMoveType == "line":
                endX = self.safeFloat(self.instrPartsGM[3])
                endY = self.safeFloat(self.instrPartsGM[4])
                if not self.groupMoveLine(endX, endY):
                    if self.laserController != None or self.stopGM:
                        if (self.laserController.status != NPILaserStatus.DISCONNECTED if self.laserController != None else True) and self.cutInGM:
                            self.laserController.turnOff()
                            self.laserController.status = self.laserController.getStatus()  
                    self.breakGroup()
                    print("Could not perform Group-Movement because of drawing at limits")
                    return

            elif self.groupMoveType == "quadr" or self.groupMoveType == "rect" or self.groupMoveType == "del_rect" or self.groupMoveType == "subrect":
                corner2X = self.safeFloat(self.instrPartsGM[3])
                corner2Y = self.safeFloat(self.instrPartsGM[4])
                if not self.groupMoveLine(corner2X, corner2Y):
                    if self.laserController != None or self.stopGM:
                        if (self.laserController.status != NPILaserStatus.DISCONNECTED if self.laserController != None else True) and self.cutInGM:
                            self.laserController.turnOff()
                            self.laserController.status = self.laserController.getStatus()  
                    self.breakGroup()
                    print("Could not perform Group-Movement because of drawing at limits")
                    return

            elif self.groupMoveType == "arc":
                centerX = self.safeFloat(self.instrPartsGM[3])
                centerY = self.safeFloat(self.instrPartsGM[4])
                degrees = self.safeFloat(self.instrPartsGM[5])
                #self.groupMoveArc(centerX, centerY, degrees)

        elif step == 2: #Step 2: Only Quadr/Rect/Del_rect- Move to third corner (which is t 4 position)
            corner3X = self.safeFloat(self.instrPartsGM[5])
            corner3Y = self.safeFloat(self.instrPartsGM[6])

            if not self.groupMoveLine(corner3X, corner3Y):
                if self.laserController != None or self.stopGM:
                        if (self.laserController.status != NPILaserStatus.DISCONNECTED if self.laserController != None else True) and self.cutInGM:
                            self.laserController.turnOff()
                            self.laserController.status = self.laserController.getStatus()  
                self.breakGroup()
                print("Could not perform Group-Movement because of drawing at limits")
                return

        elif step == 3: #Step 3: Only Quadr/Rect/Del_rect- Move to forth corner
            corner4X = self.safeFloat(self.instrPartsGM[7])
            corner4Y = self.safeFloat(self.instrPartsGM[8])

            if not self.groupMoveLine(corner4X, corner4Y):
                if self.laserController != None or self.stopGM:
                        if (self.laserController.status != NPILaserStatus.DISCONNECTED if self.laserController != None else True) and self.cutInGM:
                            self.laserController.turnOff()
                            self.laserController.status = self.laserController.getStatus()  
                self.breakGroup()
                print("Could not perform Group-Movement because of drawing at limits")
                return

        elif step == 4: #Step 4: Only Quadr/Rect/Del_rect- Move to back to starting corner
            startingX = self.safeFloat(self.instrPartsGM[1])
            startingY = self.safeFloat(self.instrPartsGM[2])
            self.groupMoveLine(startingX, startingY)

        elif step == 5: # Step 5: Turn laser of and go to next instruction item, if existing
            nextIsSubrect = False
            if self.currentInstructionItem != len(instructions)-1:
                nextInstruction = self.currentInstructions[self.currentInstructionItem+1]
                if nextInstruction.split(";")[0] == "subrect":
                    nextIsSubrect = True    
            if (self.laserController != None and not nextIsSubrect) or self.stopGM:
                if (self.laserController.status != NPILaserStatus.DISCONNECTED if self.laserController != None else True) and self.cutInGM:
                    self.laserController.turnOff()
                    self.laserController.status = self.laserController.getStatus()
            
            if self.currentInstructionItem == len(instructions)-1 or self.stopGM: #Is last instruction -> break group
                self.breakGroup()
                #print("Finished group movement")
                return
            self.handleGroupMovement(self.currentInstructions, self.currentInstructionItem+1, 0, self.cutInGM, self.laserController)
        else: 
            print("Error in Handling GM")
            self.currentInstructions = []
            self.currentInstructionItem = 0
            self.currentStepGM = 0
            self.breakGroup()
    
    def defineGroup(self, axis1: int, axis2: int, velocity=0.1, acceleration=0.1):
        self.stopGM = False
        if 0 < velocity<=0.4 and 0 < acceleration<=1.6:
            self.activeGroup = True
            return self.send_command(f"1HN{axis1}, {axis2};1HV{velocity};1HA{acceleration};1HD{acceleration}")

        else: return False

    def getGroupPosition(self):
        response = self.send_command("1HP")
        fetchedPositionXY = [p.strip() for p in response.strip("()").split(",")]
        returnPosition = "("
        for axis in range(len(fetchedPositionXY)):
            value = self.safeFloat(fetchedPositionXY[axis])
            self.currentMotorsPosition[axis] = value
            if self.motorHasOffset[axis]:
                returnPosition += str((value-self.backlash[axis]) if self.lastMotorDirection == 1 else (value+self.backlash[axis]))
            else: returnPosition += fetchedPositionXY[axis]
            returnPosition += ","
        returnPosition = returnPosition[:-1]
        returnPosition += ")"
        return returnPosition

    def groupMoveLine(self, endX: float, endY:float):
        #print("Moving line")
        if endX>0 and endX < 12 and endY >0 and endY <12:
            coordinates = [endX, endY]
            #print("Moving Line Group to original coordinates:", coordinates)
            #print("Current motor coordinates ", self.currentMotorsPosition)
            #print("Current position coordinates ", self.currentPosition)
            #print("Last Movement direction ", self.lastMotorDirection)
            #print("Current offset ", self.motorHasOffset)
            updatedCoordinates = coordinates[:]
            hasToPerformOffsetCorrection = [0, 0]
            for axis in range(len(coordinates)):
                if round(coordinates[axis], 3) > round(self.currentPosition[axis], 3):
                    if self.lastMotorDirection[axis] == 0: #If direction change and true movement
                        self.lastMotorDirection[axis] = 1
                        hasToPerformOffsetCorrection[axis] = 1
                        if self.motorHasOffset[axis]: #If has offset removes it, as error in two contrary movements cancel each other out
                            self.motorHasOffset[axis] = False
                        else:
                            updatedCoordinates[axis] += self.backlash[axis]
                            self.motorHasOffset[axis] = True
                    elif self.motorHasOffset[axis]:
                        updatedCoordinates[axis] += self.backlash[axis]
                elif round(coordinates[axis], 3) < round(self.currentPosition[axis], 3):
                    if self.lastMotorDirection[axis] == 1: #If direction change
                        self.lastMotorDirection[axis] = 0
                        hasToPerformOffsetCorrection[axis] = -1
                        if self.motorHasOffset[axis]:
                            self.motorHasOffset[axis] = False
                        else:
                            updatedCoordinates[axis] -= self.backlash[axis]
                            self.motorHasOffset[axis] = True
                    elif self.motorHasOffset[axis]:
                        updatedCoordinates[axis] -= self.backlash[axis]
                elif round(coordinates[axis], 3) == round(self.currentPosition[axis], 3) and self.motorHasOffset[axis]:
                    if self.lastMotorDirection[axis] == 1:
                        updatedCoordinates[axis] += self.backlash[axis]
                    else:
                        updatedCoordinates[axis] -= self.backlash[axis]

            updatedCoordinates = [round(e, 5) for e in updatedCoordinates]
            coordinates = [round(e, 5) for e in coordinates]
            if hasToPerformOffsetCorrection[0] != 0 or hasToPerformOffsetCorrection[1] != 0:
                relativeCoordinates = [self.currentMotorsPosition[i]+hasToPerformOffsetCorrection[i]*self.backlash[i] for i in range(len(hasToPerformOffsetCorrection))]
                self.send_command_without_reading(f"1HL{round(relativeCoordinates[0], 5)}, {round(relativeCoordinates[1], 5)};")
                self.send_command_without_reading(f"1HW0")
                self.waitingForGroupMovementFinish = True
            self.send_command_without_reading(f"1HL{round(updatedCoordinates[0], 5)}, {round(updatedCoordinates[1], 5)}")
            self.updateStatus()
            return True
        else: 
            print("Movement out of range")
            return False
    
    def breakGroup(self):
        self.activeGroup = False
        self.send_command("1HX")
        self.updateStatus()

    # Joystick
    def changeToJoystickMode(self):
        self.joystickMode = True
        self.send_command("BO0;1BP11,10,12;2BP9,8,12;3BP13,14,12;1BQ1;2BQ1;3BQ1;1TJ3;2TJ3;3TJ3;1MO;2MO;3MO")
        self.updateStatus()

    def changeToCommandMode(self):
        self.joystickMode = False
        self.send_command("1BQ0;2BQ0;3BQ0;1TJ1;2TJ1;3TJ1")
        self.currentPosition[0] = self.safeFloat(self.send_command("1TP"))
        self.currentPosition[1] = self.safeFloat(self.send_command("2TP"))
        self.setLastDirectionsMotors()
        self.updateStatus()
    

    #Helper Functions
    def safeFloat(self, s):
        try: return float(s)
        except: return