from ESP301 import ESP301, ESP301Status
from NPILaser import NPILaser, NPILaserStatus
from CameraView import CameraView
import sys
from PyQt5.QtCore import pyqtSlot, Qt, QSize
from PyQt5 import QtCore
from PyQt5.QtGui import QPixmap, QIntValidator, QPainter, QPen, QColor, QBrush
from PyQt5.QtWidgets import QLabel, QApplication, QWidget, QFrame, QCheckBox, QMessageBox, QVBoxLayout, QPushButton, QLineEdit, QHBoxLayout, QStackedWidget, QGridLayout, QListWidgetItem, QListWidget
import GuiHelper

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.controller = ESP301(self, "3")
        self.laser = NPILaser(self)
        self.setWindowTitle("Laser-Cutting Microscope GUI")
        self.controller.statusUpdate.connect(self.updateView)
        self.laser.statusUpdate.connect(self.updateView)
        self.pixel_size = 0.000089 #mm

        print("Starting Graphic User Interface, this may take a couple of seconds")

        screen_size = QApplication.primaryScreen().availableGeometry()
        self.setFixedSize(screen_size.width(), int(screen_size.height()*0.95))
        self.designItems = []


        # Main horizontal layout (left + right)
        main_layout = QHBoxLayout()
        self.setLayout(main_layout)

        # ===== Left box (Camera View) =====
        self.cameraView = CameraView()
        main_layout.addWidget(self.cameraView, 7)
        self.cameraView.imageLabel.updated.connect(self.updateDesignItems)
        self.lineHorizontalStepSize = 76.8 #pixels
        self.lineVerticalStepSize = 102.5 #pixels

        # ===== Right box =====
        self.right_box = QFrame()
        main_layout.addWidget(self.right_box, 3) 
        self.setup_right_box()
        
        #Laser safety overlay Image
        self.laserSafetyOverlayImage = QLabel(self)
        overlayPixmap = QPixmap("Measurements and Images/laser_safety.png")
        self.laserSafetyOverlayImage.setPixmap(overlayPixmap)
        self.laserSafetyOverlayImage.setScaledContents(True)
        self.laserSafetyOverlayImage.resize(int(overlayPixmap.width()/7), int(overlayPixmap.height()/7))
        self.laserSafetyOverlayImage.move(50, 30)
        self.laserSafetyOverlayImage.setHidden(True)
        self.updateView()
        
        self.laserSafetyOverlayImage.raise_()

    # --- Design of right box ---
    def setup_right_box(self):
        layout = QVBoxLayout()
        self.right_box.setLayout(layout)
        layout.addStretch(1)

        # Title
        title = QLabel("Position Controller")
        title.setStyleSheet("font-weight: bold; font-size: 18px;")
        layout.addWidget(title)


        # Connection row
        connection_row = QHBoxLayout()
        self.status_label = QLabel("Connect to controller in COM")
        connection_row.addWidget(self.status_label)

        self.com_input = QLineEdit()
        self.com_input.setValidator(QIntValidator())
        self.com_input.setFixedWidth(60)
        self.com_input.setPlaceholderText("3")
        connection_row.addWidget(self.com_input)

        self.connect_button = QPushButton("Connect")
        self.connect_button.setFixedWidth(100)
        connection_row.addWidget(self.connect_button)
        self.connect_button.clicked.connect(self.toggleComConnection)

        layout.addLayout(connection_row)

        self.disabled_widgets = []
        self.disabled_section_layout = QVBoxLayout()
        self.disabled_section_layout.setSpacing(10)
        self.disabled_section_layout.setContentsMargins(0, 5, 0, 0)
        layout.addLayout(self.disabled_section_layout)


        # Current Position
        subtitle = QLabel("Current Position")
        subtitle.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(subtitle)
        self.disabled_widgets.append(subtitle)
        self.disabled_section_layout.addWidget(subtitle)


        # Position + Buttons vertikal angeordnet
        position_layout = QVBoxLayout()
        
        # X-Position
        x_row = QHBoxLayout()
        x_label = GuiHelper.EditableLabel("x:", self.controller.currentPosition[0])
        self.x_edit = x_label
        x_row.addWidget(x_label)
        x_unit = QLabel("mm")
        x_row.addWidget(x_unit)
        position_layout.addLayout(x_row)

        # Y-Position
        y_row = QHBoxLayout()
        y_label = GuiHelper.EditableLabel("y:", self.controller.currentPosition[1])
        self.y_edit = y_label
        y_row.addWidget(y_label)
        y_unit = QLabel("mm")
        y_row.addWidget(y_unit)
        position_layout.addLayout(y_row)

        # Z-Position
        z_row = QHBoxLayout()
        z_label = GuiHelper.EditableLabel("z:", self.controller.currentPosition[2])
        self.z_edit = z_label
        z_row.addWidget(z_label)
        z_unit = QLabel("mm")
        z_row.addWidget(z_unit)
        position_layout.addLayout(z_row)

        button_col = QVBoxLayout()
        self.reloadButton = QPushButton("Reload")
        self.stop_button = QPushButton("Stop")
        self.home_button = QPushButton("Go to Home")
        self.reloadButton.setFixedWidth(120)
        self.stop_button.setFixedWidth(120)
        self.home_button.setFixedWidth(120)
        button_col.addWidget(self.reloadButton)
        button_col.addWidget(self.stop_button)
        button_col.addWidget(self.home_button)

        combined_row = QHBoxLayout()
        combined_row.addLayout(position_layout)
        combined_row.addSpacing(10)
        combined_row.addLayout(button_col)

        self.disabled_widgets.extend([self.x_edit, self.y_edit, self.z_edit, self.reloadButton, self.stop_button, self.home_button])
        self.disabled_section_layout.addLayout(combined_row)

        self.x_edit.valueChanged.connect(lambda val: (self.controller.setAbsPosition(1, val), self.updateView()) if not self.controller.joystickMode and 0 <= val <= 12 else self.x_edit.value_label.setText(f"{self.controller.currentPosition[0]:.5f}"))
        self.y_edit.valueChanged.connect(lambda val: (self.controller.setAbsPosition(2, val), self.updateView()) if not self.controller.joystickMode and 0 <= val <= 12 else self.y_edit.value_label.setText(f"{self.controller.currentPosition[1]:.5f}"))
        self.z_edit.valueChanged.connect(lambda val: (self.controller.setAbsPosition(3, val), self.updateView()) if not self.controller.joystickMode and 0 <= val <= 10 else self.z_edit.value_label.setText(f"{self.controller.currentPosition[2]:.5f}"))

        self.reloadButton.clicked.connect(lambda: (self.controller.updateStatus(), self.laser.getStatus(), self.updateView()))
        self.home_button.clicked.connect(lambda: (self.controller.goToHome(1), self.controller.goToHome(2), self.controller.goToHome(3), self.updateView()))
        self.stop_button.clicked.connect(lambda: (self.controller.abortMotion(), self.updateView()))

        # --- Subsection: Design and Cutting ---
        group_label = QLabel("Design and Cutting")
        group_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        self.disabled_widgets.append(group_label)
        self.disabled_section_layout.addWidget(group_label)

        cut_box_layout = QHBoxLayout()
        cut_label = QLabel("Cut:")
        self.cut_checkbox = QCheckBox("Laser will be turned OFF")
        self.cut_checkbox.setCheckState(Qt.Unchecked)
        self.cut_checkbox.stateChanged.connect(lambda val: self.cut_checkbox.setText("Laser will be turned ON") if val == Qt.Checked else self.cut_checkbox.setText("Laser will be turned OFF"))
        cut_box_layout.addWidget(cut_label)
        cut_box_layout.addWidget(self.cut_checkbox)
        cut_box_layout.addStretch()
        self.disabled_section_layout.addLayout(cut_box_layout)

         # Tab container
        group_card_container = QHBoxLayout()
        self.disabled_section_layout.addLayout(group_card_container)

        # Tab data
        self.group_card_names = ["design", "line", "quadr", "del_rect"]
        self.group_cards = []
        self.group_card_buttons = []
        self.group_menu_stack = QStackedWidget()

        self.input_fields_by_name = {}

        #Content of different tabs
        for i, name in enumerate(self.group_card_names):
            card = QWidget()
            card_layout = QVBoxLayout()
            card.setLayout(card_layout)
            # Red placeholder icon
            icon = QLabel()
            icon.setFixedSize(60, 60)
            pixmap = QPixmap(60, 60)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setPen(QPen(Qt.red, 3))

            if name == "design":
                points = [
                    QtCore.QPoint(15, 2),
                    QtCore.QPoint(10, 7),
                    QtCore.QPoint(25, 13),
                    QtCore.QPoint(30, 7)
                ]
                points2 = [
                    QtCore.QPoint(7, 12),
                    QtCore.QPoint(2, 20),
                    QtCore.QPoint(13, 27),
                    QtCore.QPoint(20, 20)
                ]
                painter.drawPolygon(*points)
                painter.drawPolygon(*points2)
            elif name == "line":
                painter.drawLine(5, 15, 30, 15)
            elif name == "quadr":
                points = [
                    QtCore.QPoint(0, 10),
                    QtCore.QPoint(20, 3),
                    QtCore.QPoint(40, 10),
                    QtCore.QPoint(20, 30)
                ]
                painter.drawPolygon(*points)
            elif name == "arc":
                painter.drawArc(10, 10, 40, 40, 30 * 16, 120 * 16)
            elif name == "del_rect":
                brush = QBrush(QColor(255, 0, 0, 128))
                painter.setBrush(brush)
                painter.drawRect(5, 5, 20, 20) 
            painter.end()
            icon.setPixmap(pixmap)
            label = QLabel(name.capitalize() if name != "del_rect" else "Burn \nRect")
            label.setAlignment(Qt.AlignCenter)
            btn = QPushButton()
            btn.setFixedHeight(50)
            btn_layout = QHBoxLayout()
            btn_layout.setAlignment(Qt.AlignCenter)
            btn.setLayout(btn_layout)
            btn_layout.addWidget(icon)
            btn_layout.addWidget(label)
            btn.clicked.connect(lambda checked, index=i: (self.group_menu_stack.setCurrentIndex(index), self.updateDesignItems()))
            group_card_container.addWidget(btn)
            self.disabled_widgets.append(btn)
            self.group_card_buttons.append(btn)
            input_fields = []
            # Placeholder for each menu
            if name == "design":
                menu = QWidget()
                self.design_menu_layout = QVBoxLayout(menu)
                self.design_menu_layout.setAlignment(Qt.AlignTop)
                card_title = QLabel("Whole Design")
                card_title.setAlignment(Qt.AlignLeft)
                font = card_title.font()
                font.setBold(True)
                font.setPointSize(10)
                card_title.setFont(font)
                self.design_menu_layout.addWidget(card_title)
                card_description = QLabel("Add rectangles drawing them directly on the image view. \nTo draw lines or filled rectangles, select it on the menu and draw them on the image")
                card_description.setAlignment(Qt.AlignLeft)
                font = card_title.font()
                font.setBold(False)
                font.setPointSize(8)
                card_description.setFont(font)
                self.design_menu_layout.addWidget(card_description)
                self.list_widget = QListWidget()
                self.list_widget.setStyleSheet("""
                            QListWidget::item:selected {
                                background: transparent;
                            }
                        """)
                self.design_menu_layout.addWidget(self.list_widget)
                
                menubuttons_hbox = QHBoxLayout()
                self.perform_gm_btn = QPushButton("Perform")
                self.perform_gm_btn.setFixedWidth(120)
                self.perform_gm_btn.clicked.connect(lambda: self.performDesign(self.designItems[:], (self.cut_checkbox.checkState() == Qt.Checked)))
                self.stop_gm_btn = QPushButton("Stop")
                self.stop_gm_btn.setFixedWidth(120)
                self.stop_gm_btn.clicked.connect(self.controller.stopGroupMovement)
                menubuttons_hbox.addWidget(self.perform_gm_btn)
                menubuttons_hbox.addWidget(self.stop_gm_btn)
                menubuttons_hbox.addStretch()
                self.design_menu_layout.addLayout(menubuttons_hbox)
            elif name == "line":
                menu = QWidget()
                menu_layout = QVBoxLayout(menu)
                menu_layout.setAlignment(Qt.AlignTop)
                card_title = QLabel("Line Movement")
                card_title.setAlignment(Qt.AlignLeft)
                font = card_title.font()
                font.setBold(True)
                font.setPointSize(10)
                card_title.setFont(font)
                menu_layout.addWidget(card_title)
                card_description = QLabel("Draw a line directly on the camera image")
                card_description.setAlignment(Qt.AlignLeft)
                font = card_title.font()
                font.setBold(False)
                font.setPointSize(8)
                card_description.setFont(font)
                menu_layout.addWidget(card_description)
                for axis in ["Start x", "Start y", "End x", "End y"]:
                    row = QHBoxLayout()
                    row.setAlignment(Qt.AlignRight)
                    field = QLineEdit()
                    field.setMaximumWidth(120)
                    row.addWidget(QLabel(axis))
                    row.addWidget(field)
                    row.addWidget(QLabel("mm"))
                    menu_layout.addLayout(row)
                    input_fields.append(field)

                add_groupMovement_btn = QPushButton("Add")
                add_groupMovement_btn.setFixedWidth(120)
                add_groupMovement_btn.clicked.connect(lambda: self.addDesignShape(self.input_fields_by_name, self.group_card_names[self.group_menu_stack.currentIndex()]))
                menu_layout.addWidget(add_groupMovement_btn)
            elif name == "quadr":
                menu = QWidget()
                menu_layout = QGridLayout(menu)
                menu_layout.setVerticalSpacing(10)
                menu_layout.setHorizontalSpacing(20)
                corner_names = ["First corner", "Second corner", "Third corner", "Fourth corner"]
                positions = [(0, 0), (0, 1), (1, 0), (1, 1)]
                for (row_pos, col_pos), corner in zip(positions, corner_names):
                    group = QVBoxLayout()
                    group.setContentsMargins(0, 0, 0, 0)
                    group_subtitle = QLabel(corner)
                    group_subtitle.setContentsMargins(0, 0, 0, 0)
                    group_subtitle.setAlignment(Qt.AlignCenter)
                    font = group_subtitle.font()
                    font.setBold(True)
                    font.setPointSize(8)
                    group_subtitle.setFont(font)
                    group.addWidget(group_subtitle)

                    for axis in ["x:", "y:"]:
                        row = QHBoxLayout()
                        row.setAlignment(Qt.AlignRight)
                        field = QLineEdit()
                        field.setMaximumWidth(120)
                        row.addWidget(QLabel(axis))
                        row.addWidget(field)
                        row.addWidget(QLabel("mm"))
                        group.addLayout(row)
                        input_fields.append(field)


                    group_container = QWidget()
                    group_container.setLayout(group)
                    menu_layout.addWidget(group_container, row_pos, col_pos)

                add_groupMovement_btn = QPushButton("Add")
                add_groupMovement_btn.setFixedWidth(120)
                add_groupMovement_btn.clicked.connect(lambda: self.addDesignShape(self.input_fields_by_name, self.group_card_names[self.group_menu_stack.currentIndex()]))
                menu_layout.addWidget(add_groupMovement_btn)
            elif name == "arc":
                menu = QWidget()
                menu_layout = QVBoxLayout(menu)
                menu_layout.setAlignment(Qt.AlignTop)


                card_title = QLabel("Arc Movement")
                card_title.setAlignment(Qt.AlignLeft)
                font = card_title.font()
                font.setBold(True)
                font.setPointSize(10)
                card_title.setFont(font)
                menu_layout.addWidget(card_title)


                for label_text, unit in [("Start x", "mm"), ("Start y", "mm"), ("Center x", "mm"), ("Center y", "mm"), ("Degrees", "°")]:
                    row = QHBoxLayout()
                    row.setAlignment(Qt.AlignRight)
                    field = QLineEdit()
                    field.setMaximumWidth(120)
                    row.addWidget(QLabel(label_text))
                    row.addWidget(field)
                    row.addWidget(QLabel(unit))
                    menu_layout.addLayout(row)
                    input_fields.append(field)


                add_groupMovement_btn = QPushButton("Add")
                add_groupMovement_btn.setFixedWidth(120)
                add_groupMovement_btn.clicked.connect(lambda: self.addDesignShape(self.input_fields_by_name, self.group_card_names[self.group_menu_stack.currentIndex()]))
                menu_layout.addWidget(add_groupMovement_btn)
            elif name == "del_rect":
                menu = QWidget()
                menu_layout = QGridLayout(menu)
                menu_layout.setVerticalSpacing(10)
                menu_layout.setHorizontalSpacing(20)
                card_description = QLabel("Add filled rectangles drawing them directly on the image view. \nThe inner content of these rectangles will be burned out")
                card_description.setAlignment(Qt.AlignLeft)
                font = card_title.font()
                font.setBold(False)
                font.setPointSize(8)
                card_description.setFont(font)
                menu_layout.addWidget(card_description)
            self.input_fields_by_name[name] = input_fields
            self.group_menu_stack.addWidget(menu)
        self.disabled_section_layout.addWidget(self.group_menu_stack)
        self.disabled_widgets.append(self.group_menu_stack)
        self.group_menu_stack.setCurrentIndex(0)
        
        
        # --- Subsectione: Settings ---
        settings_label = QLabel("Settings")
        settings_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        self.disabled_widgets.append(settings_label)
        self.disabled_section_layout.addWidget(settings_label)


        # Switch Motor On/Off
        motor_switch_row = QHBoxLayout()
        motor_label = QLabel("Motor:")
        self.motor_switch = GuiHelper.ToggleSwitch(self.controller.motor)
        self.motor_switch.valueChanged.connect(lambda val: (self.controller.motor_on() if val else self.controller.motor_off(), self.updateView()))
        motor_switch_row.addWidget(motor_label)
        motor_switch_row.addWidget(self.motor_switch)
        motor_switch_row.addStretch()
        self.disabled_widgets.extend([motor_label, self.motor_switch])
        self.disabled_section_layout.addLayout(motor_switch_row)


        # Set Velocity
        velocity_row = QHBoxLayout()
        velocity_label = QLabel("Set Velocity:")
        self.velocity_input = QLineEdit()
        self.velocity_input.setFixedWidth(80)
        self.velocity_input.setPlaceholderText(str(self.controller.velocity))
        
        def update_velocity():
            try:
                val = float(self.velocity_input.text())
                if 0 <= val <= 0.4:
                    self.controller.setVelocity(val)
                    self.accel_input.setText("")
                    self.updateView()
                else:
                    raise ValueError
            except ValueError:
                self.velocity_input.setText(str(self.controller.velocity))
            self.velocity_input.clearFocus()

        self.velocity_input.editingFinished.connect(update_velocity)
        self.max_vel_label = QLabel("mm/s.  Max. Velocity: 0.4")
        self.max_vel_label.setStyleSheet("color: gray;")
        velocity_row.addWidget(velocity_label)
        velocity_row.addWidget(self.velocity_input)
        velocity_row.addWidget(self.max_vel_label)
        velocity_row.addStretch()
        self.disabled_widgets.extend([velocity_label, self.velocity_input, self.max_vel_label])
        self.disabled_section_layout.addLayout(velocity_row)

        # Set Acceleration
        accel_row = QHBoxLayout()
        accel_label = QLabel("Set Acceleration:")
        self.accel_input = QLineEdit()
        self.accel_input.setFixedWidth(80)
        self.accel_input.setPlaceholderText(str(self.controller.acceleration))
        
        def update_acceleration():
            try:
                val = float(self.accel_input.text())
                if 0 <= val <= 1.6:
                    self.controller.setAcceleration(val)
                    self.accel_input.setText("")
                    self.updateView()
                else:
                    raise ValueError
            except ValueError:
                self.accel_input.setText(str(self.controller.acceleration))
            self.accel_input.clearFocus()
        
        self.accel_input.editingFinished.connect(update_acceleration)
        max_accel_label = QLabel("mm/s2.  Max. Acceleration: 1.6")
        max_accel_label.setStyleSheet("color: gray;")
        accel_row.addWidget(accel_label)
        accel_row.addWidget(self.accel_input)
        accel_row.addWidget(max_accel_label)
        accel_row.addStretch()
        self.disabled_widgets.extend([accel_label, self.accel_input, max_accel_label])
        self.disabled_section_layout.addLayout(accel_row)

        calibration_section = QVBoxLayout()
        calibrationDescriptionLabel = QLabel("Backlash Calibration")
        calibrationDescriptionLabel.setStyleSheet("font-weight: bold;")
        calibration_section.addWidget(calibrationDescriptionLabel)
        setBacklashOffset_hbox = QHBoxLayout()

        xMotorBLOffsetLabel = QLabel("x-Motor:")
        self.xMotorBLOffsetInput = QLineEdit()
        self.xMotorBLOffsetInput.setFixedWidth(50)
        self.xMotorBLOffsetInput.setPlaceholderText(str(self.controller.backlash[0]))
        xMotorBLOffsetUnitLabel = QLabel("mm")
        yMotorBLOffsetLabel = QLabel("y-Motor:")
        self.yMotorBLOffsetInput = QLineEdit()
        self.yMotorBLOffsetInput.setFixedWidth(50)
        self.yMotorBLOffsetInput.setPlaceholderText(str(self.controller.backlash[1]))
        yMotorBLOffsetUnitLabel = QLabel("mm")
        zMotorBLOffsetLabel = QLabel("z-Motor:")
        self.zMotorBLOffsetInput = QLineEdit()
        self.zMotorBLOffsetInput.setFixedWidth(50)
        self.zMotorBLOffsetInput.setPlaceholderText(str(self.controller.backlash[2]))
        zMotorBLOffsetUnitLabel = QLabel("mm")

        setBacklashOffset_btn = QPushButton("Set Backlash offset")
        setBacklashOffset_btn.setFixedWidth(150)
        setBacklashOffset_btn.clicked.connect(self.setBacklashOffset)
        setBacklashOffset_hbox.addWidget(xMotorBLOffsetLabel)
        setBacklashOffset_hbox.addWidget(self.xMotorBLOffsetInput)
        setBacklashOffset_hbox.addWidget(xMotorBLOffsetUnitLabel)
        setBacklashOffset_hbox.addWidget(yMotorBLOffsetLabel)
        setBacklashOffset_hbox.addWidget(self.yMotorBLOffsetInput)
        setBacklashOffset_hbox.addWidget(yMotorBLOffsetUnitLabel)
        setBacklashOffset_hbox.addWidget(zMotorBLOffsetLabel)
        setBacklashOffset_hbox.addWidget(self.zMotorBLOffsetInput)
        setBacklashOffset_hbox.addWidget(zMotorBLOffsetUnitLabel)
        setBacklashOffset_hbox.addWidget(setBacklashOffset_btn)
        setBacklashOffset_hbox.addStretch()
        calibration_section.addLayout(setBacklashOffset_hbox)
        self.disabled_widgets.extend([calibrationDescriptionLabel, setBacklashOffset_btn, xMotorBLOffsetLabel, yMotorBLOffsetLabel, zMotorBLOffsetLabel, self.xMotorBLOffsetInput, self.yMotorBLOffsetInput, self.zMotorBLOffsetInput, xMotorBLOffsetUnitLabel, yMotorBLOffsetUnitLabel, zMotorBLOffsetUnitLabel])
        self.disabled_section_layout.addLayout(calibration_section)

        # --- Subsection: Joystick Mode ---
        joystick_row = QHBoxLayout()
        joystick_label = QLabel("Joystick Mode")
        joystick_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        self.joystick_switch = GuiHelper.ToggleSwitch(self.controller.joystickMode, "On - Other controlling tools are disabled", "Off - Other controlling tools are enabled")
        self.joystick_switch.valueChanged.connect(lambda val: (self.controller.changeToJoystickMode() if val else self.controller.changeToCommandMode(), self.updateView()))
        self.joystick_switch.setStyleSheet("margin-top: 10px;")
        joystick_row.addWidget(joystick_label)
        joystick_row.addWidget(self.joystick_switch)
        joystick_row.addStretch()
        self.disabled_widgets.extend([joystick_label, self.joystick_switch])
        self.disabled_section_layout.addLayout(joystick_row)

        # --- Subsection: Custom Commands ---
        custom_label = QLabel("Custom Commands")
        custom_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        self.disabled_widgets.append(custom_label)
        self.disabled_section_layout.addWidget(custom_label)
        custom_row = QHBoxLayout()
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("Enter command")
        self.send_button = QPushButton("Send")
        custom_row.addWidget(self.command_input)
        custom_row.addWidget(self.send_button)
        self.disabled_widgets.extend([self.command_input, self.send_button])
        self.disabled_section_layout.addLayout(custom_row)
        response_title = QLabel("Response:")
        self.response_label = QLabel("")
        self.response_label.setStyleSheet("font-size: 10px; color: #333;")
        self.response_label.setWordWrap(True)
        self.disabled_widgets.append(response_title)
        self.disabled_widgets.append(self.response_label)
        self.disabled_section_layout.addWidget(response_title)
        self.disabled_section_layout.addWidget(self.response_label)
        self.send_button.clicked.connect(lambda: (self.sendCustomCommand(), self.updateView()))

        # --- Subsection: Laser --- 
        laser_title = QLabel("Laser Controller")
        laser_title.setStyleSheet("font-weight: bold; font-size: 18px; margin-top: 10px")
        layout.addWidget(laser_title)
        # Connection row
        laser_connection_row = QHBoxLayout()
        self.laser_connection_status_label = QLabel("Connect to Laser in COM")
        laser_connection_row.addWidget(self.laser_connection_status_label)
        self.laser_com_input = QLineEdit()
        self.laser_com_input.setValidator(QIntValidator())
        self.laser_com_input.setFixedWidth(60)
        self.laser_com_input.setPlaceholderText("4")
        laser_connection_row.addWidget(self.laser_com_input)
        self.laser_connect_button = QPushButton("Connect")
        self.laser_connect_button.setFixedWidth(100)
        laser_connection_row.addWidget(self.laser_connect_button)
        self.laser_connect_button.clicked.connect(self.toggleLaserComConnection)
        self.laser_com_type_button = QPushButton("Local mode")
        self.laser_com_type_button.setFixedWidth(100)
        self.laser_com_type_button.clicked.connect(lambda: self.laser.configureRemote(1))
        laser_connection_row.addWidget(self.laser_com_type_button)
        layout.addLayout(laser_connection_row)
        self.laser_disabled_widgets = []
        self.laser_disabled_section_layout = QVBoxLayout()
        self.laser_disabled_section_layout.setSpacing(10)
        self.laser_disabled_section_layout.setContentsMargins(0, 5, 0, 0)
        layout.addLayout(self.laser_disabled_section_layout)

        laser_row = QHBoxLayout()
        self.laser_label = QLabel(f"Current Status: {self.laser.status.value}")
        self.laserTurnOn = QPushButton("Turn ON")
        self.laserTurnOn.clicked.connect(self.activateLaserHandler)
        self.laserTurnOn.setFixedWidth(100)
        self.laserTurnOff = QPushButton("Turn OFF")
        self.laserTurnOff.clicked.connect(lambda: self.activateLaserHandler(True))
        self.laserTurnOff.setFixedWidth(100)
        laser_row.addWidget(self.laser_label)
        laser_row.addWidget(self.laserTurnOn)
        laser_row.addWidget(self.laserTurnOff)
        self.laser_disabled_widgets.extend([self.laser_label, self.laserTurnOn, self.laserTurnOff])
        self.laser_disabled_section_layout.addLayout(laser_row)
        layout.addStretch(5)


    # --- Design Methods ---
    def setDisabledWidgetState(self, enabled: bool):
        for widget in self.disabled_widgets:
            widget.setEnabled(enabled)
            if isinstance(widget, (QPushButton, QLineEdit, QLabel)):
                styleSheet = widget.styleSheet()
                styleSheet +="color: black;" if enabled else "color: gray;"
                widget.setStyleSheet(styleSheet)

    def setLaserDisabledWidgetState(self, enabled: bool):
        for widget in self.laser_disabled_widgets:
            widget.setEnabled(enabled)
            if isinstance(widget, (QPushButton, QLabel)):
                styleSheet = widget.styleSheet()
                styleSheet +="color: black;" if enabled else "color: gray;"
                widget.setStyleSheet(styleSheet)

    def updateDesignItems(self):
        self.designItems = self.cameraView.imageLabel.designItems
        if self.cameraView.imageLabel.goToCoordinates != self.controller.currentPosition and self.cameraView.imageLabel.orderedMoving:
            instruction = f"line;{self.controller.currentPosition[0]};{self.controller.currentPosition[1]};{self.cameraView.imageLabel.goToCoordinates[0]};{self.cameraView.imageLabel.goToCoordinates[1]}"
            self.performDesign([instruction], False)
            self.cameraView.imageLabel.orderedMoving = False
        self.list_widget.clear()
        for idx, item_str in enumerate(self.designItems, 1):
            parts = item_str.split(";")
            type_name = parts[0].strip()
            self.addItemToDesignList(type_name, idx, parts)
        # Entferne letzten Separator falls vorhanden
        count = self.list_widget.count()
        if count > 0:
            last_item = self.list_widget.item(count - 1)
            widget = self.list_widget.itemWidget(last_item)
            if isinstance(widget, QFrame):
                self.list_widget.takeItem(count - 1)
        
        self.updateView()
        self.cameraView.imageLabel.newDrawingType = "line" if self.group_menu_stack.currentIndex() == 1 else "del_rect" if self.group_menu_stack.currentIndex() == 3 else "rect"

    def addItemToDesignList(self, type_name, index, data_parts):
            list_item = QListWidgetItem(self.list_widget)
            def delete_cb(_checked=False, index = index-1):
                self.deleteDesignItem(index)
            convert_cb = None
            update_cb = None
            if type_name == "rect":
                def convert_cb_inner(_checked=False, idx=index-1):
                    self.convertRectToQuadrDesignItem(idx)
                convert_cb = convert_cb_inner
                def update_rect_width_cb(value):
                    try:
                        value = float(value)
                        parts = self.designItems[index-1].split(";")
                        parts[10] = str(int(value/(1000*self.pixel_size)))
                        self.designItems[index-1] = ";".join(parts)
                        widget.width_edit.setPlaceholderText(value)
                    except: 
                        return
                update_cb = update_rect_width_cb
            widget = GuiHelper.ListItem(type_name, index, delete_cb, convert_cb, update_cb, data_parts)
            if type_name == "rect":
                list_item.setSizeHint(QSize(100, 80))
            else:
                list_item.setSizeHint(QSize(100, 60))
            self.list_widget.addItem(list_item)
            self.list_widget.setItemWidget(list_item, widget)
            separator = QFrame()
            separator.setFrameShape(QFrame.HLine)
            separator.setFrameShadow(QFrame.Sunken)
            separator.setStyleSheet("color: #cccccc;")
            separator_item = QListWidgetItem(self.list_widget)
            separator_item.setSizeHint(QSize(100, 2))
            self.list_widget.addItem(separator_item)
            self.list_widget.setItemWidget(separator_item, separator)

    def setBacklashOffset(self):
        try:
            x_backlash = float(self.xMotorBLOffsetInput.text() if self.xMotorBLOffsetInput.text() != "" else self.controller.backlash[0])
            y_backlash = float(self.yMotorBLOffsetInput.text() if self.yMotorBLOffsetInput.text() != "" else self.controller.backlash[1])
            z_backlash = float(self.zMotorBLOffsetInput.text() if self.zMotorBLOffsetInput.text() != "" else self.controller.backlash[2])
        except:
            return
        self.controller.backlash = [x_backlash, y_backlash, z_backlash]
        self.updateView()

    def deleteDesignItem(self, index):
        self.list_widget.takeItem(index)
        # Entferne auch aus items und nummeriere neu
        del self.designItems[index]
        self.updateDesignItems()

    def convertRectToQuadrDesignItem(self, index):
        parts = self.designItems[index].split(";")
        parts[0] = "quadr"
        self.designItems[index] = ";".join(parts)
        self.updateDesignItems()

    def outOfRangeWarning(self):
        QMessageBox.warning(self, "ATTENTION!",
                                         "CONTROLLER OUT OF RANGE!\n\nYou are trying to move the controller out of range. Remember the position range are following:\n\nx-Axis: 0mm -> 12mm \n\ny-Axis: 0mm -> 12mm\n\nz-Axis: 0mm -> 10mm", QMessageBox.Ok, QMessageBox.Ok)

    # --- General Methods ---
    def updateView(self):
        if self.controller.connected:
            self.status_label.setText(f"Connected to COM{self.controller.port}")
            self.com_input.hide()
            self.connect_button.setText("Disconnect")
            self.x_edit.value_label.setText(f"{self.controller.currentPosition[0]:.4f}")
            self.y_edit.value_label.setText(f"{self.controller.currentPosition[1]:.4f}")
            self.z_edit.value_label.setText(f"{self.controller.currentPosition[2]:.4f}")
            self.xMotorBLOffsetInput.setPlaceholderText(f"{self.controller.backlash[0]:.4f}")
            self.yMotorBLOffsetInput.setPlaceholderText(f"{self.controller.backlash[1]:.4f}")
            self.zMotorBLOffsetInput.setPlaceholderText(f"{self.controller.backlash[2]:.4f}")
            self.cameraView.imageLabel.currentPosition = self.controller.currentPosition
            self.cameraView.imageLabel.designItems = self.designItems
            for name in self.group_card_names[1:3]:
                self.input_fields_by_name[name][0].setPlaceholderText(f"{self.controller.currentPosition[0]:.4f}")
                self.input_fields_by_name[name][1].setPlaceholderText(f"{self.controller.currentPosition[1]:.4f}")
            if self.controller.joystickMode or not self.controller.motor or self.controller.status != ESP301Status.READY:
                self.x_edit.value_label.setEnabled(False)
                self.x_edit.value_label.setStyleSheet("color: gray;")
                self.y_edit.value_label.setEnabled(False)
                self.y_edit.value_label.setStyleSheet("color: gray;")
                self.z_edit.value_label.setEnabled(False)
                self.z_edit.value_label.setStyleSheet("color: gray;")
                self.home_button.setEnabled(False)
                self.home_button.setStyleSheet("color: gray;")
                self.perform_gm_btn.setEnabled(False)
                self.perform_gm_btn.setStyleSheet("color: gray;")
                if self.controller.status == ESP301Status.GROUP_MOVING:
                    self.stop_gm_btn.setEnabled(True)
                    self.stop_gm_btn.setStyleSheet("color: black;")
                self.cameraView.imageLabel.interactionEnabled = False
            else:
                self.x_edit.value_label.setEnabled(True)
                self.x_edit.value_label.setStyleSheet("color: black;")
                self.y_edit.value_label.setEnabled(True)
                self.y_edit.value_label.setStyleSheet("color: black;")
                self.z_edit.value_label.setEnabled(True)
                self.z_edit.value_label.setStyleSheet("color: black;")
                self.perform_gm_btn.setEnabled(True)
                self.perform_gm_btn.setStyleSheet("color: black;")
                self.stop_gm_btn.setEnabled(False)
                self.stop_gm_btn.setStyleSheet("color: gray;")
                self.home_button.setEnabled(True)
                self.home_button.setStyleSheet("color: black;")
                self.cameraView.imageLabel.interactionEnabled = True
                if self.laser.status == NPILaserStatus.READY:
                    self.cut_checkbox.setEnabled(True)
                    self.cut_checkbox.setStyleSheet("color: black;")
            if self.controller.status == ESP301Status.OFF:
                self.motor_switch.setCheckState(False)
        else:
            self.status_label.setText("Connect to controller in COM")
            self.com_input.show()
            self.connect_button.setText("Connect")
        self.velocity_input.setPlaceholderText(str(self.controller.velocity))
        self.accel_input.setPlaceholderText(str(self.controller.acceleration))
        self.setLaserDisabledWidgetState(self.laser.connected)
        if self.laser.connected:
            self.laser_connection_status_label.setText(f"Connected to COM{self.laser.port}")
            self.laser_com_input.hide()
            self.laser_connect_button.setText("Disconnect")
            self.laser_label.setText(f"Current Status: {self.laser.status.value}")
            if self.laser.status == NPILaserStatus.ON:
                self.laserTurnOn.setEnabled(False)
                self.laserTurnOn.setStyleSheet("color: gray;")  
                self.laserTurnOff.setText("Turn OFF")
                self.laserTurnOff.setEnabled(True)
                self.laserTurnOff.setStyleSheet("color: black;")
                self.laserSafetyOverlayImage.setHidden(False)
            elif self.laser.status == NPILaserStatus.READY:
                self.laserTurnOn.setText("Turn ON")
                self.laserTurnOn.setEnabled(True)
                self.laserTurnOn.setStyleSheet("color: black;")
                self.laserTurnOff.setText("Turn OFF")
                self.laserTurnOff.setEnabled(True)
                self.laserTurnOff.setStyleSheet("color: black;")
                self.laserSafetyOverlayImage.setHidden(True)
            else: 
                self.laserTurnOn.setEnabled(False)
                self.laserTurnOn.setStyleSheet("color: gray;")
                self.laserTurnOff.setEnabled(False)
                self.laserTurnOff.setStyleSheet("color: gray;")
                self.cut_checkbox.setEnabled(False)
                self.cut_checkbox.setStyleSheet("color: gray;") 
                self.laserSafetyOverlayImage.setHidden(True)      
        else:
            self.laser_connection_status_label.setText("Connect to laser in COM")
            self.laser_com_input.show()
            self.laser_connect_button.setText("Connect")
            self.cut_checkbox.setEnabled(False)
            self.cut_checkbox.setStyleSheet("color: gray;")    
        self.setDisabledWidgetState(self.controller.connected)

    def addDesignShape(self, input_fields, name):
        fields = input_fields[name]
        if fields[0].text() == "": fields[0].setText(f"{self.controller.currentPosition[0]:.5f}")
        if fields[1].text() == "": fields[1].setText(f"{self.controller.currentPosition[1]:.5f}")
        for f in fields:
            try:
                value = float(f.text())
                if name == "arc":
                    startPositionX = fields[0].text()
                    startPositionY = fields[1].text()
                    centerX = fields[2].text()
                    centerY = fields[3].text()
                    degrees = fields[4].text()
                    if not self.controller.checkArcMovementAllowance(f"({float(startPositionX)},{float(startPositionY)})", float(centerX), float(centerY), float(degrees)):
                        self.messageBox("OUT OF RANGE!", "Movement does not fit in range.")
                        return
                if not 0<=value<=12 and name != "arc":
                    self.messageBox("OUT OF RANGE!", "Movement does not fit in range.")
                    return
            except:
                self.messageBox("Invalid Input", "Please complete all coordinates in order to perform a group movement")
                return
        if name == "line" and len(fields) == 4:
            startPositionX = fields[0].text()
            startPositionY = fields[1].text()
            endPositionX = fields[2].text()
            endPositionY = fields[3].text()
            instructions = f"line;{startPositionX};{startPositionY};{endPositionX};{endPositionY}"
        elif name == "quadr" and len(fields) == 8:
            startPositionX = fields[0].text()
            startPositionY = fields[1].text()
            corner2X = fields[2].text()
            corner2Y = fields[3].text()
            corner3X = fields[4].text()
            corner3Y = fields[5].text()
            corner4X = fields[6].text()
            corner4Y = fields[7].text()
            instructions = f"quadr;{startPositionX};{startPositionY};{corner2X};{corner2Y};{corner3X};{corner3Y};{corner4X};{corner4Y};"
        else:
            return
        self.designItems.append(instructions)
        self.updateDesignItems()

    def performDesign(self, instructions, cut):
        allowLaser = False
        if cut and (self.laser.status == NPILaserStatus.READY or self.laser.status == NPILaserStatus.ON):
            replyLaser = QMessageBox.warning(self, "ATTENTION!",
                                         "LASER SAFETY CHECK!\n\nAre all safety precautions in place to interact with the laser?\n\nMake sure to be wearing the LG11 safety glasses at all time, to have turned on the laser warning light and that is safe to operate with the laser.",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if replyLaser == QMessageBox.Yes:
                allowLaser = True
                replyFocus = QMessageBox.information(self, "FOCUS LASER", 
                                                "Due to chromatic aberration if the image is sharp, the laser spot is not. Before performing the laser cutting please focus the laser spot (rather than the image). \n Do you want to continue?", 
                                                QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Yes)
                if replyFocus == QMessageBox.Yes:
                    self.controller.defineGroup(1,2, self.controller.velocity, self.controller.acceleration)
                    self.controller.handleGroupMovement(self.designItems[:], 0, 0, allowLaser, self.laser)
        else:
            self.controller.defineGroup(1,2, self.controller.velocity, self.controller.acceleration)
            self.controller.handleGroupMovement(instructions, 0, 0, allowLaser, self.laser)

    def activateLaserHandler(self, off = False):
        if self.laser.status == NPILaserStatus.READY and not off:
            reply = QMessageBox.warning(self, "ATTENTION!",
                                         "LASER SAFETY CHECK!\n\nAre all safety precautions in place to interact with the laser?\n\n- Have you done the laser safety course? It is mandatory when interacting with the microscope\n\n- Make sure to be wearing the LG11 safety glasses at all time\n\n- Have you turned on the laser warning light and closed the door?\n\n- Do not look into the optical path and remove any reflective or scattering objects of the laser path.\n\n- Turn the laser off as soon as possible, when not in used.",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.laser.turnOn()
                self.laser.status = self.laser.getStatus()
        else:
            self.laser.turnOff()
            self.laser.status = self.laser.getStatus()
        self.updateView()

    # --- Button Methods ---
    def toggleComConnection(self):
        if not self.controller.connected:
            com_port = self.com_input.text().strip()
            self.controller.__init__(self, com_port)
            self.updateView()
        else:
            self.controller.disconnect()
            self.updateView()

    def toggleLaserComConnection(self):
        if not self.laser.connected:
            laser_com_port = self.laser_com_input.text().strip()
            self.laser.__init__(self, laser_com_port)
            self.updateView()
        else:
            self.laser.disconnect()
            self.updateView()

    def sendCustomCommand(self):
        command = self.command_input.text().strip()
        if command and self.controller.connected:
            self.controller.send_command(command)
            response = self.controller.send_command(command)
            self.response_label.setText(response)
            self.command_input.setText("")



if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())