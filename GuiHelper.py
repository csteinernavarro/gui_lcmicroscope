from PyQt5.QtCore import pyqtSignal, pyqtSlot, Qt
from PyQt5.QtWidgets import QLabel, QWidget, QCheckBox, QVBoxLayout, QPushButton, QLineEdit, QHBoxLayout
from PyQt5.QtGui import QPixmap, QPainter, QColor
from PyQt5.QtCore import Qt, QPoint

#Custom label with textfield to change
class EditableLabel(QWidget):
    valueChanged = pyqtSignal(float)

    def __init__(self, label, value=0.0):
        super().__init__()
        self.label = QLabel(label)
        self.value_label = QLabel(str(value))
        self.value_label.setFixedWidth(100)
        self.value_label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextEditable)
        self.value_label.mousePressEvent = self.editValue
        self.value_label.setAlignment(Qt.AlignLeft)

        layout = QHBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.value_label)
        self.setLayout(layout)   


    def editValue(self, event):
        try:
            self.editLine.setText(self.value_label.text())
        except AttributeError:
            self.editLine = QLineEdit(self.value_label.text())
            self.editLine.setFixedWidth(100)
            self.editLine.editingFinished.connect(self.finishEditing)
            layout = self.layout()
            layout.replaceWidget(self.value_label, self.editLine)
            self.value_label.hide()
            self.editLine.setFocus()
        else:
            self.editLine.show()
            layout = self.layout()
            layout.replaceWidget(self.value_label, self.editLine)
            self.value_label.hide()
            self.editLine.setFocus()

    def finishEditing(self):
        text = self.editLine.text()
        if not text == "":
            try:
                self.editLine.clearFocus()
                value = float(text)
                if self.value_label.text() != text:
                    self.valueChanged.emit(value) 
                self.value_label.setText(text)

            except ValueError:
                pass

        self.value_label.show()
        self.editLine.hide()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.editLine.clearFocus()
            self.value_label.show()
            self.editLine.hide()

# Custom toggle switch
class ToggleSwitch(QCheckBox):
    valueChanged = pyqtSignal(bool)

    def __init__(self, state=False, label_on="On", label_off="Off"):
        super().__init__()
        self.setChecked(state)
        self.setText(label_on if state else label_off)
        self.stateChanged.connect(self.toggle_text)
        self.label_on = label_on
        self.label_off = label_off

    def toggle_text(self):
        self.setText(self.label_on if self.isChecked() else self.label_off)
        self.valueChanged.emit(self.isChecked())


# Item of Design List in GUI
class ListItem(QWidget):
    def __init__(self, type_name, index, delete_callback, convert_callback=None, update_callback=None, data_parts=None):
        super().__init__()
        self.type_name = type_name
        self.index = index
        self.delete_callback = delete_callback
        self.updateWidth_callback = update_callback
        self.convert_callback = convert_callback
        self.pixel_size = 0.000089 #mm

        layout = QHBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignLeft)
        self.setLayout(layout)

        # Erstelle Pixmap je nach Typ
        pixmap = QPixmap(20, 20)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)

        if type_name == "line":
            painter.setPen(QColor(100, 100, 255))
            painter.drawLine(0, 10, 20, 10)
        elif type_name == "rect":
            painter.setPen(QColor(100, 255, 100))
            painter.drawRect(2, 2, 16, 16)
        elif type_name == "quadr":
            painter.setPen(QColor(255, 100, 100))
            # Unregelmäßiges Rechteck zeichnen
            points = [ (2,2), (18,4), (16,18), (4,16) ]
            painter.drawPolygon(*[QPoint(p[0], p[1]) for p in points])
        elif type_name == "del_rect":
            painter.setBrush(QColor(200, 0, 0))
            painter.drawRect(2, 2, 16, 16)

        painter.end()

        self.icon_label = QLabel()
        self.icon_label.setPixmap(pixmap)
        layout.addWidget(self.icon_label)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)
        text_layout.setAlignment(Qt.AlignLeft)

        self.title_label = QLabel(f"{type_name.capitalize()} {index}")
        text_layout.addWidget(self.title_label)

        # Subtitle je nach Typ und data_parts
        if data_parts:
            if type_name == "line":
                subtitle_text = ""
                if len(data_parts) >= 5:
                    subtitle_text = f"Start: ({data_parts[1]}, {data_parts[2]}), End: ({data_parts[3]}, {data_parts[4]})"
                self.subtitle_label = QLabel(subtitle_text)
                self.subtitle_label.setStyleSheet("color: #999999; font-size: 9px; background: transparent;")
                text_layout.addWidget(self.subtitle_label)
            elif type_name in ["rect", "quadr", "del_rect"]:
                if len(data_parts) >= 9:
                    # Split corners into two lines:
                    line1 = f"Corner 1: ({data_parts[1]}, {data_parts[2]}), Corner 2: ({data_parts[3]}, {data_parts[4]})"
                    line2 = f"Corner 3: ({data_parts[5]}, {data_parts[6]}), Corner 4: ({data_parts[7]}, {data_parts[8]})"
                else:
                    line1 = ""
                    line2 = ""
                self.subtitle_label1 = QLabel(line1)
                self.subtitle_label1.setStyleSheet("color: #999999; font-size: 9px; background: transparent;")
                self.subtitle_label2 = QLabel(line2)                
                self.subtitle_label2.setStyleSheet("color: #999999; font-size: 9px; background: transparent;")
                text_layout.addWidget(self.subtitle_label1)
                text_layout.addWidget(self.subtitle_label2)
                # For rect: add extra line with width input
                if type_name == "rect":
                    width_layout = QHBoxLayout()
                    width_layout.setSpacing(5)
                    width_layout.setAlignment(Qt.AlignLeft)
                    width_label = QLabel("Width Surface to Burn")
                    self.width_edit = QLineEdit()
                    self.width_edit.setFixedWidth(50)
                    self.width_edit.setPlaceholderText(str(round(float(data_parts[10])*self.pixel_size*1000, 2)))
                    self.width_edit.setAlignment(Qt.AlignRight)
                    width_unit = QLabel("µm")
                    width_layout.addWidget(width_label)
                    width_layout.addWidget(self.width_edit)
                    width_layout.addWidget(width_unit)
                    self.width_edit.editingFinished.connect(lambda :self.updateWidth_callback(self.width_edit.text()))
                    text_layout.addLayout(width_layout)
        else:
            # default: empty subtitle
            self.subtitle_label = QLabel("")
            self.subtitle_label.setStyleSheet("color: #999999; font-size: 9px; background: transparent;")
            text_layout.addWidget(self.subtitle_label)

        layout.addLayout(text_layout)

        if type_name == "rect" and self.convert_callback is not None:
            self.convert_button = QPushButton("Convert to Quadr")
            self.convert_button.clicked.connect(self.convert_callback)
            layout.addWidget(self.convert_button)

        # Spacer, damit der Delete-Button rechts sitzt
        layout.addStretch()

        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self.delete_callback)
        layout.addWidget(self.delete_button, alignment=Qt.AlignRight)