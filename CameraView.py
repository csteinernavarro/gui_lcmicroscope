import sys, amcam
from PyQt5.QtCore import pyqtSignal, pyqtSlot, Qt, QRect, QPoint, QPointF
from PyQt5.QtGui import QPixmap, QImage, QPainter, QPen
from PyQt5.QtWidgets import QLabel, QApplication, QWidget, QDesktopWidget, QCheckBox, QMessageBox
from ClickableCameraLabel import ClickableCameraLabel 

class CameraView(QWidget):
    eventImage = pyqtSignal()
    clicked = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.hcam = None
        self.buf = None      # video buffer
        self.w = 0           # video width
        self.h = 0           # video height
        self.total = 0

        screen_size = QApplication.primaryScreen().availableGeometry()
        max_height = int(screen_size.height()*0.93)
        aspect_ratio = 1.333333
        self.setFixedSize(int(max_height*aspect_ratio), max_height)

        qtRectangle = self.frameGeometry()
        centerPoint = QDesktopWidget().availableGeometry().center()
        qtRectangle.moveCenter(centerPoint)
        self.move(qtRectangle.topLeft())
        self.initUI()
        self.initCamera()

    def initUI(self):
        self.cb = QCheckBox('Auto Exposure', self)
        self.cb.stateChanged.connect(self.changeAutoExposure)
        self.imageLabel = ClickableCameraLabel(self)
        self.imageLabel.setScaledContents(True)
        self.imageLabel.move(0, 0)
        self.imageLabel.resize(self.geometry().width(), self.geometry().height())

# the vast majority of callbacks come from amcam.dll/so/dylib internal threads, so we use qt signal to post this event to the UI thread  
    @staticmethod
    def cameraCallback(nEvent, ctx):
        if nEvent == amcam.AMCAM_EVENT_IMAGE:
            ctx.eventImage.emit()

# run in the UI thread
    @pyqtSlot()
    def eventImageSignal(self):
        if self.hcam is not None:
            try:
                self.hcam.PullImageV2(self.buf, 24, None)
                self.total += 1
            except amcam.HRESULTException as ex:
                QMessageBox.warning(self, '', 'pull image failed, hr=0x{:x}'.format(ex.hr), QMessageBox.Ok)
            else:
                self.setWindowTitle('{}: {}'.format(self.camname, self.total))
                img = QImage(self.buf, self.w, self.h, (self.w * 24 + 31) // 32 * 4, QImage.Format_RGB888)
                
                pixmap = QPixmap.fromImage(img)
                self.imageLabel.setPixmap(pixmap)

    def initCamera(self):
        a = amcam.Amcam.EnumV2()
        if len(a) <= 0:
            self.setWindowTitle('No camera found')
            self.cb.setEnabled(False)
        else:
            self.camname = a[0].displayname
            self.setWindowTitle(self.camname)
            self.eventImage.connect(self.eventImageSignal)
            try:
                self.hcam = amcam.Amcam.Open(a[0].id)
            except amcam.HRESULTException as ex:
                QMessageBox.warning(self, '', 'failed to open camera, hr=0x{:x}'.format(ex.hr), QMessageBox.Ok)
            else:
                self.w, self.h = self.hcam.get_Size()
                bufsize = ((self.w * 24 + 31) // 32 * 4) * self.h
                self.buf = bytes(bufsize)
                self.cb.setChecked(self.hcam.get_AutoExpoEnable())            
                try:
                    if sys.platform == 'win32':
                        self.hcam.put_Option(amcam.AMCAM_OPTION_BYTEORDER, 0) # QImage.Format_RGB888
                    self.hcam.StartPullModeWithCallback(self.cameraCallback, self)
                    self.hcam.put_TempTint(14976, 860)
                except amcam.HRESULTException as ex:
                    QMessageBox.warning(self, '', 'failed to start camera, hr=0x{:x}'.format(ex.hr), QMessageBox.Ok)

    def changeAutoExposure(self, state):
        if self.hcam is not None:
            self.hcam.put_AutoExpoEnable(state == Qt.Checked)

    def closeEvent(self, event):
        if self.hcam is not None:
            self.hcam.Close()
            self.hcam = None

    
if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = CameraView()
    win.show()
    sys.exit(app.exec_())