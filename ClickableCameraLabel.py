from PyQt5.QtCore import pyqtSignal, pyqtSlot, Qt
from PyQt5.QtWidgets import QLabel, QApplication
from PyQt5.QtGui import QPixmap, QPainter, QPen, QColor, QTransform, QPolygonF, QPainterPath, QBrush, QFont
from PyQt5.QtCore import Qt, QRectF, QPointF, QLineF, QRectF, QLineF
import math
import sys
import numpy as np

# Class for the Label and the overlay design on top of the camera view
class ClickableCameraLabel(QLabel):
    updated = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.original_pixmap = None
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        self.interactionEnabled = True

        self.currentPosition = [6.5,7.2,0]
        self.pixel_size = 0.000087 #mm
        self.pixmapScreenSizeRatio = 0
        self.designItems = []
        self.drawingType = "rect" # line / rect / del_rect
        self.newDrawingType = "rect" # line / rect / del_rect
        self.pixel_surface_del = 20 #Set Standard value
        self.goToCoordinates = self.currentPosition
        self.orderedMoving = False

        self.drawing = False
        self.start_point = QPointF()
        self.end_point = QPointF()
        self.rectangles = []  # Liste von Rechtecken als dicts mit 'rect': QRectF, 'rotation': float
        self.del_rectangles = []
        self.lines = []
        self.quadr = []
        self.selected_index = -1
        self.preview_draw = None
        self.resizing_corner = None  # 'tl', 'tr', 'bl', 'br'
        self.moving_offset = None
        self.rotating = False

        self.setCursor(Qt.CrossCursor)

    def mousePressEvent(self, event):
        if not self.interactionEnabled:
            return
        if event.button() == Qt.LeftButton:
            handle_size = 6
            rotation_handle_radius = 8
            
            # Check if clicked on any current design elements
            for i, entry in enumerate(self.rectangles):
                rect = entry['rect']
                rotation = entry['rotation']
                center = rect.center()

                # Transformation für Rücktransformation der Mausposition
                transform = QTransform()
                transform.translate(center.x(), center.y())
                transform.rotate(-rotation)
                transform.translate(-center.x(), -center.y())
                local_pos = transform.map(event.pos())

                # Griff für Rotation
                handle_center = QPointF((rect.left() + rect.right()) // 2, rect.top() - 15)
                if (local_pos - handle_center).manhattanLength() <= rotation_handle_radius:
                    self.selected_index = i
                    self.rotating = True
                    self.drawingType = "rect"
                    self.update()
                    self.setCursor(Qt.SizeHorCursor)
                    return

                # Eckgriffe prüfen
                for corner, pt in [('tl', rect.topLeft()), ('tr', rect.topRight()),
                                   ('bl', rect.bottomLeft()), ('br', rect.bottomRight())]:
                    handle_rect = QRectF(pt.x() - handle_size//2, pt.y() - handle_size//2, handle_size, handle_size)
                    if handle_rect.contains(local_pos):
                        self.selected_index = i
                        self.resizing_corner = corner
                        self.drawingType = "rect"
                        self.update()
                        self.setCursor(Qt.SizeBDiagCursor)
                        return

                # Seiten-Interaktion für Bewegung
                if rect.contains(local_pos):
                    self.selected_index = i
                    self.moving_offset = local_pos - rect.topLeft()
                    self.drawingType = "rect"
                    self.update()
                    self.setCursor(Qt.ClosedHandCursor)
                    return

            for i, line in enumerate(self.lines):                
                pos = event.pos()

                # Eckgriffe prüfen
                for corner, pt in [('b', line.p1()), ('t', line.p2())]:
                    handle_rect = QRectF(pt.x() - handle_size//2, pt.y() - handle_size//2, handle_size, handle_size)
                    if handle_rect.contains(pos):
                        self.selected_index = i
                        self.resizing_corner = corner
                        self.drawingType = "line"
                        self.update()
                        self.setCursor(Qt.SizeBDiagCursor)
                        return
        
            for i, quadr in enumerate(self.quadr):
                pos = event.pos()

                # Eckgriffe prüfen
                for cornerIndex in range(quadr.count()):
                        cornerPoint = quadr.at(cornerIndex)
                        handle_rect = QRectF(cornerPoint.x() - handle_size//2, cornerPoint.y() - handle_size//2, handle_size, handle_size)
                        if handle_rect.contains(pos):
                            self.selected_index = i
                            self.resizing_corner = cornerIndex
                            self.drawingType = "quadr"
                            self.update()
                            self.setCursor(Qt.SizeBDiagCursor)
                            return

            for i, entry in enumerate(self.del_rectangles):
                del_rect = entry['rect']
                rotation = entry['rotation']
                center = del_rect.center()

                # Transformation für Rücktransformation der Mausposition
                transform = QTransform()
                transform.translate(center.x(), center.y())
                transform.rotate(-rotation)
                transform.translate(-center.x(), -center.y())
                local_pos = transform.map(event.pos())

                # Griff für Rotation
                handle_center = QPointF((del_rect.left() + del_rect.right()) // 2, del_rect.top() - 15)
                if (local_pos - handle_center).manhattanLength() <= rotation_handle_radius:
                    self.selected_index = i
                    self.rotating = True
                    self.drawingType = "del_rect"
                    self.update()
                    self.setCursor(Qt.SizeHorCursor)
                    return

                # Eckgriffe prüfen
                for corner, pt in [('tl', del_rect.topLeft()), ('tr', del_rect.topRight()),
                                   ('bl', del_rect.bottomLeft()), ('br', del_rect.bottomRight())]:
                    handle_rect = QRectF(pt.x() - handle_size//2, pt.y() - handle_size//2, handle_size, handle_size)
                    if handle_rect.contains(local_pos):
                        self.selected_index = i
                        self.resizing_corner = corner
                        self.drawingType = "del_rect"
                        self.update()
                        self.setCursor(Qt.SizeBDiagCursor)
                        return

                # Seiten-Interaktion für Bewegung
                if del_rect.contains(local_pos):
                    self.selected_index = i
                    self.moving_offset = local_pos - del_rect.topLeft()
                    self.drawingType = "del_rect"
                    self.update()
                    self.setCursor(Qt.ClosedHandCursor)
                    return

            # Did not click on current design elements -> Draw Element
            self.drawing = True
            pos = event.pos()

            # Check if is drawing outside of motors movement range. Transform pixel position into real world position
            dx_px = pos.x() - self.width()//2
            dy_py = pos.y() - self.height()//2

            dx_mm = dx_px*self.pixel_size*self.pixmapScreenSizeRatio
            dy_mm = dy_py*self.pixel_size*self.pixmapScreenSizeRatio
        
            pointX = self.currentPosition[0] + dx_mm
            pointY = self.currentPosition[1] - dy_mm

            if not (0<pointX<12 and 0<pointY<12):
                print("Outside the limits")
                return

            self.start_point = event.pos()
            self.end_point = event.pos()
            if self.newDrawingType == "line":
                self.preview_draw = QLineF(self.start_point, self.end_point)
            else: 
                self.preview_draw = QRectF(self.start_point, self.end_point)
            self.update()
            self.setCursor(Qt.CrossCursor)


    def mouseDoubleClickEvent(self, event): # Perform moving to selected position
        if not self.interactionEnabled:
            return
        
        # Transform pixel position into real world position
        pos = event.pos()

        dx_px = pos.x() - self.width()//2
        dy_py = pos.y() - self.height()//2

        dx_mm = dx_px*self.pixel_size*self.pixmapScreenSizeRatio
        dy_mm = dy_py*self.pixel_size*self.pixmapScreenSizeRatio
      
        pointX = self.currentPosition[0] + dx_mm
        pointY = self.currentPosition[1] - dy_mm

        self.goToCoordinates = (round(float(pointX), 5), round(float(pointY), 5), self.currentPosition[2])

        #print("Go to by double click: ", self.goToCoordinates)
        self.orderedMoving = True
        self.updated.emit(True)

    def mouseMoveEvent(self, event): # Handle moving mouse (while clicked)
        if not self.interactionEnabled:
            return
        if self.drawing: # Show preview drawing shape
            self.end_point = event.pos()
            if self.newDrawingType == "line":
                self.preview_draw = QLineF(self.start_point, self.end_point)
            else:
                self.preview_draw = QRectF(self.start_point, self.end_point) 
            self.update()
    
        elif self.rotating and self.selected_index != -1: # Rotate selected shape
            if self.drawingType == "rect":
                pts = self.rectangles[self.selected_index]['rect']
                center = pts.center()
                vector_start = QPointF(event.pos() - center)
                angle = math.degrees(math.atan2(vector_start.y(), vector_start.x()))
                self.rectangles[self.selected_index]['rotation'] = 90 + angle
            elif self.drawingType == "del_rect":
                pts = self.del_rectangles[self.selected_index]['rect']
                center = pts.center()
                vector_start = QPointF(event.pos() - center)
                angle = math.degrees(math.atan2(vector_start.y(), vector_start.x()))
                self.del_rectangles[self.selected_index]['rotation'] = 90 + angle
            
        elif self.resizing_corner and self.selected_index != -1: # Resize specific selected corner of selected shape
            if self.drawingType == "rect":
                rect = self.rectangles[self.selected_index]['rect']
                opposite = {
                    'tl': rect.bottomRight(),
                    'tr': rect.bottomLeft(),
                    'bl': rect.topRight(),
                    'br': rect.topLeft()
                }[self.resizing_corner]
 
                new_rect = QRectF(opposite, event.pos()).normalized()
 
                if new_rect.width() >= 20 and new_rect.height() >= 20:
                    try:
                        del_size = int(self.rectangles[self.selected_index]['del_size'])
                    except:
                        del_size = self.pixel_surface_del
                    new_outer = new_rect.adjusted(-del_size, -del_size, del_size, del_size)
                    conflict = any(new_outer.intersects(other['rect']) for j, other in enumerate(self.rectangles) if j != self.selected_index)
                    if not conflict:
                        self.rectangles[self.selected_index]['rect'] = new_rect
                        self.rectangles[self.selected_index]['del_rect'] = new_outer
                
            elif self.drawingType == "line": 
                line = self.lines[self.selected_index]
                new_line = line
            
                if self.resizing_corner == 'b':
                    new_line.setP1(event.pos())
                elif self.resizing_corner == 't':
                    new_line.setP2(event.pos())
                
                self.lines[self.selected_index] = new_line
            
            elif self.drawingType == "quadr":
                if 0 <= self.resizing_corner < self.quadr[self.selected_index].count():
                    self.quadr[self.selected_index][self.resizing_corner] = event.pos()
            
            elif self.drawingType == "del_rect":
                del_rect = self.del_rectangles[self.selected_index]['rect']
                opposite = {
                    'tl': del_rect.bottomRight(),
                    'tr': del_rect.bottomLeft(),
                    'bl': del_rect.topRight(),
                    'br': del_rect.topLeft()
                }[self.resizing_corner]
 
                new_rect = QRectF(opposite, event.pos()).normalized()
 
                if new_rect.width() >= 20 and new_rect.height() >= 20:
                    conflict = any(new_rect.intersects(other['rect']) for j, other in enumerate(self.rectangles))
                    if not conflict:
                        self.del_rectangles[self.selected_index]['rect'] = new_rect

        elif self.moving_offset and self.selected_index != -1: # Move selected shape
            if self.drawingType == "rect":
                rect = self.rectangles[self.selected_index]['rect']
                new_top_left = event.pos() - self.moving_offset
 
                # Position Limits of view
                new_top_left.setX(max(0, min(new_top_left.x(), self.width() - rect.width())))
                new_top_left.setY(max(0, min(new_top_left.y(), self.height() - rect.height())))
                delta = new_top_left - rect.topLeft()
                new_rect = rect.translated(delta)
                try:
                    del_size = int(self.rectangles[self.selected_index]['del_size'])
                except:
                    del_size = self.pixel_surface_del
                new_outer = new_rect.adjusted(-del_size, -del_size, del_size, del_size)
                conflict = any(new_outer.intersects(other['rect']) for j, other in enumerate(self.rectangles) if j != self.selected_index)
                if not conflict:
                    self.rectangles[self.selected_index]['rect'] = new_rect
                    self.rectangles[self.selected_index]['del_rect'] = new_outer

            elif self.drawingType == "line":
                line = self.lines[self.selected_index]
                newP1 = event.pos() - self.moving_offset

                newP1.setX(max(0, min(newP1.x(), self.width() - (rect.width()))))
                newP1.setY(max(0, min(newP1.y(), self.height() - (rect.height()))))

                delta = newP1 - line.p1()
                self.lines[self.selected_index] = line.translated(delta)
            
            elif self.drawingType == "quadr":
                quadr = self.quadr[self.selected_index]
                newPoint = event.pos() - self.moving_offset

                newPoint.setX(max(0, min(newPoint.x(), self.width() - (rect.width()))))
                newPoint.setY(max(0, min(newPoint.y(), self.height() - (rect.height()))))

                delta = newPoint - quadr.at(0)
                self.quadr[self.selected_index] = quadr.translated(delta)
            
            elif self.drawingType == "del_rect":
                del_rect = self.del_rectangles[self.selected_index]['rect']
                new_top_left = event.pos() - self.moving_offset
 
                # Begrenzung
                new_top_left.setX(max(0, min(new_top_left.x(), self.width() - del_rect.width())))
                new_top_left.setY(max(0, min(new_top_left.y(), self.height() - del_rect.height())))
                delta = new_top_left - del_rect.topLeft()
                new_rect = del_rect.translated(delta)
                conflict = any(new_rect.intersects(other['rect']) for j, other in enumerate(self.rectangles))
                if not conflict:
                    self.del_rectangles[self.selected_index]['rect'] = new_rect
        
        self.update()

    def mouseReleaseEvent(self, event): # Handle when releasing mouse
        if not self.interactionEnabled:
            return
        self.setCursor(Qt.CrossCursor)
        # Check if was drawing to append shape
        if event.button() == Qt.LeftButton and self.drawing:
            if self.newDrawingType == "rect" or self.newDrawingType == "quadr":
                rect = QRectF(self.start_point, self.end_point)
                if rect.width() > 20 and rect.height() > 20:
                    outer_rect = rect.adjusted(-self.pixel_surface_del, -self.pixel_surface_del, self.pixel_surface_del, self.pixel_surface_del)
                    conflict = any(outer_rect.intersects(existing['rect']) for existing in self.rectangles)
                    if not conflict:
                        self.rectangles.append({'rect': rect, 'rotation': 0, 'del_rect': outer_rect, 'del_size': self.pixel_surface_del})
                self.selected_index = -1
            elif self.newDrawingType == "line":
                line = QLineF(self.start_point, self.end_point)
                if line.length() > 20:
                    self.lines.append(line)
                self.selected_index = -1
            elif self.newDrawingType == "del_rect":
                rect = QRectF(self.start_point, self.end_point)
                if rect.width() > 20 and rect.height() > 20:
                    conflict = any(rect.intersects(existing['rect']) for existing in self.rectangles)
                    if not conflict:
                        self.del_rectangles.append({'rect': rect, 'rotation': 0})
                self.selected_index = -1
        
        # Update all elements and reset editing variables
        self.updateDesignElements()
        self.moving_offset = None
        self.rotating = False
        self.drawing = False
        self.resizing_corner = None
        self.update() 
            

    def paintEvent(self, event): # Software draw the shapes (how the shapes should look like on the overlay view)
        super().paintEvent(event)
        painter = QPainter(self)

        for i, entry in enumerate(self.rectangles):
            rect = entry['rect']
            rotation = entry['rotation']
            outer = entry['del_rect']
            center = rect.center()

            painter.save()
            path = QPainterPath()
            painter.translate(center)
            painter.rotate(rotation)
            painter.translate(-center)
            path.addRect(QRectF(outer))
            path.addRect(QRectF(rect))  # wird aus dem äußeren ausgeschnitten
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, 128))
            painter.drawPath(path)
            painter.restore()

            painter.save()            
            painter.translate(center)
            painter.rotate(rotation)
            painter.translate(-center)
            if self.selected_index == i and self.drawingType == "rect":
                painter.setPen(QPen(QColor(0, 255, 255), 8))
            else: painter.setPen(QPen(QColor(255, 0, 0), 8))
            painter.drawRect(rect)

            # Handles:
            handle_size = 12
            for pt in [rect.topLeft(), rect.topRight(), rect.bottomLeft(), rect.bottomRight()]:
                handle_rect = QRectF(pt.x() - handle_size//2, pt.y() - handle_size//2, handle_size, handle_size)
                painter.fillRect(handle_rect, QColor(0, 0, 255))

            # Rotation handle:
            rot_center = QPointF((rect.left() + rect.right()) // 2, rect.top() - 15)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(255, 165, 0))
            painter.drawEllipse(rot_center, 6, 6)
            painter.restore()
        
        for i, line in enumerate(self.lines):
            painter.save()
            if self.selected_index == i and self.drawingType == "line":
                painter.setPen(QPen(QColor(0, 255, 255), 8))
            else: painter.setPen(QPen(QColor(255, 0, 0), 8))
            painter.drawLine(line)

            # Handles:
            handle_size = 12
            for pt in [line.p1(), line.p2()]:
                handle_rect = QRectF(pt.x() - handle_size//2, pt.y() - handle_size//2, handle_size, handle_size)
                painter.fillRect(handle_rect, QColor(0, 0, 255))
            
            painter.restore()

        for i, quadr in enumerate(self.quadr):
            painter.save()
            if self.selected_index == i and self.drawingType == "quadr":
                painter.setPen(QPen(QColor(0, 255, 255), 8))
            else: painter.setPen(QPen(QColor(255, 0, 0), 8))
            painter.drawPolygon(quadr)

            handle_size = 12
            
            for corner in  [quadr.at(i) for i in range(quadr.count())]:
                handle_rect = QRectF(corner.x() - handle_size//2, corner.y() - handle_size//2, handle_size, handle_size)
                painter.fillRect(handle_rect, QColor(0, 0, 255))

            painter.restore()

        for i, entry in enumerate(self.del_rectangles):
            del_rect = entry['rect']
            rotation = entry['rotation']
            center = del_rect.center()

            painter.save()
            path = QPainterPath()
            painter.translate(center)
            painter.rotate(rotation)
            painter.translate(-center)
            path.addRect(QRectF(del_rect))
            if self.selected_index == i and self.drawingType == "del_rect":
                painter.setPen(QPen(QColor(0, 255, 255), 8))
            else: painter.setPen(QPen(QColor(Qt.lightGray), 8))
            painter.setBrush(QColor(0, 0, 0, 128))
            painter.drawPath(path)
            painter.restore()

            painter.save()            
            painter.translate(center)
            painter.rotate(rotation)
            painter.translate(-center)
            # Handles:
            handle_size = 12
            for pt in [del_rect.topLeft(), del_rect.topRight(), del_rect.bottomLeft(), del_rect.bottomRight()]:
                handle_rect = QRectF(pt.x() - handle_size//2, pt.y() - handle_size//2, handle_size, handle_size)
                painter.fillRect(handle_rect, QColor(0, 0, 255))

            # Rotation handle:
            rot_center = QPointF((del_rect.left() + del_rect.right()) // 2, del_rect.top() - 15)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(255, 165, 0))
            painter.drawEllipse(rot_center, 6, 6)
            painter.restore()

        if self.preview_draw and self.drawing:
            pen = QPen(QColor(0, 255, 0), 1, Qt.DashLine)
            painter.setPen(pen)
            if self.newDrawingType == "rect" or self.newDrawingType == "del_rect":
                painter.drawRect(self.preview_draw)
            elif self.newDrawingType == "line":
                painter.drawLine(QLineF(self.preview_draw))

    def keyPressEvent(self, event): # Handle when pressing some keys
        if not self.interactionEnabled:
            return
        if event.key() == 16777219  or event.key() == Qt.Key_Delete:
            if 0 <= self.selected_index < len(self.rectangles if self.drawingType == "rect" else self.lines if self.drawingType == "line" else self.quadr if self.drawingType == "quadr" else self.del_rectangles):
                if self.drawingType == "rect":
                    del self.rectangles[self.selected_index]
                elif self.drawingType == "line":
                    del self.lines[self.selected_index]
                elif self.drawingType == "quadr":
                    del self.quadr[self.selected_index]
                elif self.drawingType == "del_rect":
                    del self.del_rectangles[self.selected_index]
            self.updated.emit(True)
            self.selected_index = -1
            self.drawing = False

        if event.key() == Qt.Key_Escape:
            self.selected_index = -1
            self.drawing = False
        
        if (event.key() == Qt.Key_Left or event.key() == Qt.Key_Right or event.key() == Qt.Key_Up or event.key() == Qt.Key_Down) and 0 <= self.selected_index < len(self.rectangles if self.drawingType == "rect" else self.lines if self.drawingType == "line" else self.quadr if self.drawingType == "quadr" else self.del_rectangles):
            if self.drawingType == "rect": 
                new_rect = self.rectangles[self.selected_index]['rect'].translated(
                    3 if event.key() == Qt.Key_Right else -3 if event.key() == Qt.Key_Left else 0,
                    -3 if event.key() == Qt.Key_Up else 3 if event.key() == Qt.Key_Down else 0)
                try:
                    del_size = int(self.rectangles[self.selected_index]['del_size'])
                except:
                    del_size = self.pixel_surface_del
                new_outer = new_rect.adjusted(-del_size, -del_size, del_size, del_size)
                conflict = any(new_outer.intersects(other['rect']) for j, other in enumerate(self.rectangles) if j != self.selected_index)
                if not conflict:
                    self.rectangles[self.selected_index]['rect'] = new_rect
                    self.rectangles[self.selected_index]['del_rect'] = new_outer
            elif self.drawingType == "line":
                new_line = self.lines[self.selected_index].translated(3 if event.key() == Qt.Key_Right else -3 if event.key() == Qt.Key_Left else 0, -3 if event.key() == Qt.Key_Up else 3 if event.key() == Qt.Key_Down else 0)
                self.lines[self.selected_index] = new_line
            elif self.drawingType == "quadr":
                new_quadr = self.quadr[self.selected_index].translated(3 if event.key() == Qt.Key_Right else -3 if event.key() == Qt.Key_Left else 0, -3 if event.key() == Qt.Key_Up else 3 if event.key() == Qt.Key_Down else 0)
                self.quadr[self.selected_index] = new_quadr
            elif self.drawingType == "del_rect": 
                new_rect = self.del_rectangles[self.selected_index]['rect'].translated(
                    3 if event.key() == Qt.Key_Right else -3 if event.key() == Qt.Key_Left else 0,
                    -3 if event.key() == Qt.Key_Up else 3 if event.key() == Qt.Key_Down else 0)
                conflict = any(new_rect.intersects(other['rect']) for j, other in enumerate(self.rectangles))
                if not conflict:
                    self.del_rectangles[self.selected_index]['rect'] = new_rect
            self.updated.emit(True)
        self.updateDesignElements()
        self.update()

    def updateDesignElements(self):
        design_elements = []
        #print(f"Rectangles: {self.rectangles}")
        for object in self.rectangles:
            rect = object['rect']
            transform = QTransform()
            rotation = object['rotation']
            del_size = object['del_size']
            center = rect.center()
            transform.translate(center.x(), center.y())
            transform.rotate(rotation)
            transform.translate(-center.x(), -center.y())

            pixelPoints = np.array([transform.map(rect.topLeft()), transform.map(rect.topRight()),
                    transform.map(rect.bottomRight()), transform.map(rect.bottomLeft())])

            dx_px = np.array([e.x() for e in pixelPoints]) - self.width()//2
            dy_py = np.array([e.y() for e in pixelPoints]) - self.height()//2

            dx_mm = dx_px*self.pixel_size*self.pixmapScreenSizeRatio #Check!
            dy_mm = dy_py*self.pixel_size*self.pixmapScreenSizeRatio

            pointsX = np.array([self.currentPosition[0] + dx_mm[i] for i in range(len(dx_mm))])
            pointsY = np.array([self.currentPosition[1] - dy_mm[i] for i in range(len(dy_mm))]) 

            pointsX = np.round(pointsX, 5)
            pointsY = np.round(pointsY, 5)

            design_elements.append(f"rect;{pointsX[0]};{pointsY[0]};{pointsX[1]};{pointsY[1]};{pointsX[2]};{pointsY[2]};{pointsX[3]};{pointsY[3]};{rotation};{del_size}")

        for line in self.lines:
            p1x = line.p1().x()
            p1y = line.p1().y()
            p2x = line.p2().x()
            p2y = line.p2().y()


            dx_px = np.array([p1x, p2x]) - self.width()//2
            dy_py = np.array([p1y, p2y]) - self.height()//2

            dx_mm = dx_px*self.pixel_size*self.pixmapScreenSizeRatio
            dy_mm = dy_py*self.pixel_size*self.pixmapScreenSizeRatio

            pointsX = np.array([self.currentPosition[0] + dx_mm[i] for i in range(len(dx_mm))])
            pointsY = np.array([self.currentPosition[1] - dy_mm[i] for i in range(len(dy_mm))]) 

            pointsX = np.round(pointsX, 5)
            pointsY = np.round(pointsY, 5)

            design_elements.append(f"line;{pointsX[0]};{pointsY[0]};{pointsX[1]};{pointsY[1]}")

        for quadr in self.quadr:
            pixelPoints = [quadr.at(i) for i in range(quadr.count())]

            dx_px = np.array([e.x() for e in pixelPoints]) - self.width()//2
            dy_py = np.array([e.y() for e in pixelPoints]) - self.height()//2

            dx_mm = dx_px*self.pixel_size*self.pixmapScreenSizeRatio
            dy_mm = dy_py*self.pixel_size*self.pixmapScreenSizeRatio

            pointsX = np.array([self.currentPosition[0] + dx_mm[i] for i in range(len(dx_mm))])
            pointsY = np.array([self.currentPosition[1] - dy_mm[i] for i in range(len(dy_mm))]) 

            pointsX = np.round(pointsX, 5)
            pointsY = np.round(pointsY, 5)

            design_elements.append(f"quadr;{pointsX[0]};{pointsY[0]};{pointsX[1]};{pointsY[1]};{pointsX[2]};{pointsY[2]};{pointsX[3]};{pointsY[3]}")

        for del_rect in self.del_rectangles:
            rect = del_rect['rect']
            transform = QTransform()
            rotation = del_rect['rotation']
    
            center = rect.center()
            transform.translate(center.x(), center.y())
            transform.rotate(rotation)
            transform.translate(-center.x(), -center.y())

            pixelPoints = np.array([transform.map(rect.topLeft()), transform.map(rect.topRight()),
                    transform.map(rect.bottomRight()), transform.map(rect.bottomLeft())])

            dx_px = np.array([e.x() for e in pixelPoints]) - self.width()//2
            dy_py = np.array([e.y() for e in pixelPoints]) - self.height()//2

            dx_mm = dx_px*self.pixel_size*self.pixmapScreenSizeRatio
            dy_mm = dy_py*self.pixel_size*self.pixmapScreenSizeRatio

            pointsX = np.array([self.currentPosition[0] + dx_mm[i] for i in range(len(dx_mm))])
            pointsY = np.array([self.currentPosition[1] - dy_mm[i] for i in range(len(dy_mm))]) 

            pointsX = np.round(pointsX, 5)
            pointsY = np.round(pointsY, 5)

            design_elements.append(f"del_rect;{pointsX[0]};{pointsY[0]};{pointsX[1]};{pointsY[1]};{pointsX[2]};{pointsY[2]};{pointsX[3]};{pointsY[3]};{rotation}")


        if self.designItems != design_elements:
            self.designItems = design_elements
            self.updated.emit(True)
    
    def setPixmap(self, pixmap): # Build the whole overlay view on top of the camera view
        painter = QPainter(pixmap)

        width = pixmap.width()
        height = pixmap.height()
        self.pixmapScreenSizeRatio = width/self.width()

        self.centerX = width//2
        self.centerY = height//2

        anzahlStriche = 20

        verticalStepSize = pixmap.width()/anzahlStriche
        horizontalStepSize = height/anzahlStriche

        #print(f"Kästchen Größe: PIXEL({verticalStepSize}, {horizontalStepSize}), ABS({verticalStepSize*self.pixel_size}, {horizontalStepSize*self.pixel_size})")
        for i in range(anzahlStriche):
            painter.setPen(QPen(Qt.red, 0.3, Qt.DashLine))

            drawVertPosition = round(i*verticalStepSize)
            drawHorizPosition = round(i*horizontalStepSize)
            painter.drawLine( #Vertical Lines
                drawVertPosition,0,
                drawVertPosition, height
            )
            painter.drawLine( #Hotizontal Lines
                0,drawHorizPosition,
                width, drawHorizPosition
            )

            painter.setPen(QPen(Qt.red, 2))
            font = painter.font()
            font.setPointSize(12)
            painter.setFont(font)

            vertCoordTextRect = QRectF(
                drawVertPosition+5, 5, 100, 16
            )

            absolutePosition = (
                round(float(self.currentPosition[0]+(i-10)*verticalStepSize*self.pixel_size), 5), 
                round(float(self.currentPosition[1]-(i-10)*horizontalStepSize*self.pixel_size), 5) 
                )
            painter.drawText(vertCoordTextRect, Qt.AlignLeft, f"{absolutePosition[0]}")

            horizCoordTextRect = QRectF(
                5, drawHorizPosition+5, 100, 16
            )
            painter.drawText(horizCoordTextRect, Qt.AlignLeft, f"{absolutePosition[1]}")

        #print(f"GM Items: {self.designItems}")
        rectanglesToAppend = []
        linesToAppend = []
        quadrToAppend = []
        del_rectanglesToAppend = []
        for item in self.designItems:
            elementParts = item.split(";")
            if not self.resizing_corner and not self.rotating and not self.drawing and not self.moving_offset:
                if elementParts[0] == "line":
                    startX = float(elementParts[1])
                    startY = float(elementParts[2])
                    endX = float(elementParts[3])
                    endY = float(elementParts[4])

                    coordinatesX = [startX, endX]
                    coordinatesY = [startY, endY]

                    inVisibleMap = True
                    
                    for e in range(len(coordinatesX)):
                        distanceToAbsCenterPositionX = coordinatesX[e]-self.currentPosition[0]
                        distanceInPixelX = distanceToAbsCenterPositionX/(self.pixel_size*self.pixmapScreenSizeRatio)
                        pixelPositionX = distanceInPixelX+self.width()//2
                        if 0<pixelPositionX<width:
                            coordinatesX[e] = pixelPositionX
                        elif pixelPositionX<0:
                            coordinatesX[e] = 0
                        elif pixelPositionX>width:
                            coordinatesX[e] = width

                        distanceToAbsCenterPositionY = self.currentPosition[1]-coordinatesY[e]
                        distanceInPixelY = distanceToAbsCenterPositionY/(self.pixel_size*self.pixmapScreenSizeRatio)
                        pixelPositionY = distanceInPixelY+self.height()//2
                        if 0<pixelPositionY<height:
                            coordinatesY[e] = pixelPositionY
                        elif pixelPositionY<0:
                            coordinatesY[e] = 0
                        elif pixelPositionY>height:
                            coordinatesY[e] = height

                    if inVisibleMap:
                        p1 = QPointF(coordinatesX[0], coordinatesY[0])
                        p2 = QPointF(coordinatesX[1], coordinatesY[1])
                        linesToAppend.append(QLineF(p1, p2))

                elif elementParts[0] == "quadr":
                    corner1X = float(elementParts[1])
                    corner1Y = float(elementParts[2])
                    corner2X = float(elementParts[3])
                    corner2Y = float(elementParts[4])
                    corner3X = float(elementParts[5])
                    corner3Y = float(elementParts[6])
                    corner4X = float(elementParts[7])
                    corner4Y = float(elementParts[8])

                    coordinatesX = [corner1X, corner2X, corner3X, corner4X]
                    coordinatesY = [corner1Y, corner2Y, corner3Y, corner4Y]

                    inVisibleMap = True
                        
                    for e in range(len(coordinatesX)):
                        distanceToAbsCenterPositionX = coordinatesX[e]-self.currentPosition[0]
                        distanceInPixelX = distanceToAbsCenterPositionX/(self.pixel_size*self.pixmapScreenSizeRatio)
                        pixelPositionX = distanceInPixelX+self.width()//2
                        if 0<pixelPositionX<width:
                            coordinatesX[e] = pixelPositionX
                        elif pixelPositionX<0:
                            coordinatesX[e] = 0
                        elif pixelPositionX>width:
                            coordinatesX[e] = width

                        distanceToAbsCenterPositionY = self.currentPosition[1]-coordinatesY[e]
                        distanceInPixelY = distanceToAbsCenterPositionY/(self.pixel_size*self.pixmapScreenSizeRatio)
                        pixelPositionY = distanceInPixelY+self.height()//2
                        if 0<pixelPositionY<height:
                            coordinatesY[e] = pixelPositionY
                        elif pixelPositionY<0:
                            coordinatesY[e] = 0
                        elif pixelPositionY>height:
                            coordinatesY[e] = height

                    if inVisibleMap:
                        quadr = QPolygonF([
                            QPointF(coordinatesX[0], coordinatesY[0]),
                            QPointF(coordinatesX[1], coordinatesY[1]),
                            QPointF(coordinatesX[2], coordinatesY[2]),
                            QPointF(coordinatesX[3], coordinatesY[3]),
                        ])
                        quadrToAppend.append(quadr)
                               
                                            
                        """elif elementParts[0] == "arc":
                            startX = float(elementParts[1])
                            startY = float(elementParts[2])
                            centerArcX = float(elementParts[3])
                            centerArcY = float(elementParts[4])
                            degrees = float(elementParts[5])
                            #TO DO!
                            if inVisibleMap:
                                painter.setPen(QPen(Qt.black, 8, Qt.RoundCap))"""

                elif elementParts[0] == "rect":
                    corner1X = float(elementParts[1])
                    corner1Y = float(elementParts[2])
                    corner2X = float(elementParts[3])
                    corner2Y = float(elementParts[4])
                    corner3X = float(elementParts[5])
                    corner3Y = float(elementParts[6])
                    corner4X = float(elementParts[7])
                    corner4Y = float(elementParts[8])
                    rotation = float(elementParts[9])
                    del_size = int(elementParts[10])

                    coordinatesX = [corner1X, corner2X, corner3X, corner4X]
                    coordinatesY = [corner1Y, corner2Y, corner3Y, corner4Y]

                    inVisibleMap = True
                        
                    for e in range(len(coordinatesX)):
                        distanceToAbsCenterPositionX = coordinatesX[e]-self.currentPosition[0]
                        distanceInPixelX = distanceToAbsCenterPositionX/(self.pixel_size*self.pixmapScreenSizeRatio)
                        pixelPositionX = distanceInPixelX+self.width()//2
                        if 0<pixelPositionX<width:
                            coordinatesX[e] = pixelPositionX
                        elif pixelPositionX<0:
                            coordinatesX[e] = 0
                        elif pixelPositionX>width:
                            coordinatesX[e] = width

                        distanceToAbsCenterPositionY = self.currentPosition[1]-coordinatesY[e]
                        distanceInPixelY = distanceToAbsCenterPositionY/(self.pixel_size*self.pixmapScreenSizeRatio)
                        pixelPositionY = distanceInPixelY+self.height()//2
                        if 0<pixelPositionY<height:
                            coordinatesY[e] = pixelPositionY
                        elif pixelPositionY<0:
                            coordinatesY[e] = 0
                        elif pixelPositionY>height:
                            coordinatesY[e] = height

                    topLeftPoint = QPointF(coordinatesX[0], coordinatesY[0])
                    bottomRightPoint = QPointF(coordinatesX[2], coordinatesY[2])

                    #print(f"Pixel rücktrafo: ({topLeftPoint}, {bottomRightPoint})")

                    if inVisibleMap:
                        rotatedCorners = [topLeftPoint, bottomRightPoint]
                        rect = QRectF(rotatedCorners[0], rotatedCorners[1])
                        center = rect.center()
                        transform = QTransform()
                        transform.translate(center.x(), center.y())
                        transform.rotate(-rotation)
                        transform.translate(-center.x(), -center.y())

                        originalPoints = [transform.map(pt) for pt in rotatedCorners]
                        originalRect = QRectF(originalPoints[0], originalPoints[1])
                        outer_rect = originalRect.adjusted(-del_size, -del_size, del_size, del_size)
                        rectanglesToAppend.append({'rect': originalRect, 'rotation': rotation, 'del_rect': outer_rect, 'del_size': del_size})

                elif elementParts[0] == "del_rect":
                    corner1X = float(elementParts[1])
                    corner1Y = float(elementParts[2])
                    corner2X = float(elementParts[3])
                    corner2Y = float(elementParts[4])
                    corner3X = float(elementParts[5])
                    corner3Y = float(elementParts[6])
                    corner4X = float(elementParts[7])
                    corner4Y = float(elementParts[8])
                    rotation = float(elementParts[9])

                    coordinatesX = [corner1X, corner2X, corner3X, corner4X]
                    coordinatesY = [corner1Y, corner2Y, corner3Y, corner4Y]

                    inVisibleMap = True
                        
                    for e in range(len(coordinatesX)):
                        distanceToAbsCenterPositionX = coordinatesX[e]-self.currentPosition[0]
                        distanceInPixelX = distanceToAbsCenterPositionX/(self.pixel_size*self.pixmapScreenSizeRatio)
                        pixelPositionX = distanceInPixelX+self.width()//2
                        if 0<pixelPositionX<width:
                            coordinatesX[e] = pixelPositionX
                        elif pixelPositionX<0:
                            coordinatesX[e] = 0
                        elif pixelPositionX>width:
                            coordinatesX[e] = width

                        distanceToAbsCenterPositionY = self.currentPosition[1]-coordinatesY[e]
                        distanceInPixelY = distanceToAbsCenterPositionY/(self.pixel_size*self.pixmapScreenSizeRatio)
                        pixelPositionY = distanceInPixelY+self.height()//2
                        if 0<pixelPositionY<height:
                            coordinatesY[e] = pixelPositionY
                        elif pixelPositionY<0:
                            coordinatesY[e] = 0
                        elif pixelPositionY>height:
                            coordinatesY[e] = height

                    topLeftPoint = QPointF(coordinatesX[0], coordinatesY[0])
                    bottomRightPoint = QPointF(coordinatesX[2], coordinatesY[2])

                    if inVisibleMap:
                        rotatedCorners = [topLeftPoint, bottomRightPoint]
                        rect = QRectF(rotatedCorners[0], rotatedCorners[1])
                        center = rect.center()
                        transform = QTransform()
                        transform.translate(center.x(), center.y())
                        transform.rotate(-rotation)
                        transform.translate(-center.x(), -center.y())

                        originalPoints = [transform.map(pt) for pt in rotatedCorners]
                        originalRect = QRectF(originalPoints[0], originalPoints[1])
                        del_rectanglesToAppend.append({'rect': originalRect, 'rotation': rotation})


            #print(f"Rectangles from GMItems {rectanglesToAppend}")
        if not self.resizing_corner and not self.rotating and not self.drawing and not self.moving_offset:
            if self.rectangles != rectanglesToAppend:
                self.rectangles = rectanglesToAppend
            if self.del_rectangles != del_rectanglesToAppend:
                self.del_rectangles = del_rectanglesToAppend
            if self.lines != linesToAppend:
                self.lines = linesToAppend
            if self.quadr != quadrToAppend:
                self.quadr = quadrToAppend


        boldPen = QPen(Qt.darkRed, 3)
        painter.setPen(boldPen)

        painter.drawLine(self.centerX-6, self.centerY, self.centerX+6, self.centerY)
        painter.drawLine(self.centerX, self.centerY-6, self.centerX, self.centerY+6)

        font = painter.font()
        font.setPointSize(14)
        painter.setFont(font)

        currentPositionRect = QRectF(
            self.centerX+10, self.centerY+10, 200, 20
        )

        painter.drawText(currentPositionRect, Qt.AlignLeft, f"({self.currentPosition[0]:.4f}, {self.currentPosition[1]:.4f})")

        #Scale bar
        scale_bar_rect_width = 180
        scale_bar_rect_height = 80
        scale_bar_rect_margin = 30

        scale_bar_x = pixmap.width() - scale_bar_rect_width-scale_bar_rect_margin
        scale_bar_y = pixmap.height() - scale_bar_rect_height-scale_bar_rect_margin

        painter.setBrush(QBrush(QColor(255, 255, 255, 200)))
        painter.setPen(QPen(Qt.black, 1))
        painter.drawRect(scale_bar_x, scale_bar_y, scale_bar_rect_width, scale_bar_rect_height)

        line_length = round(0.01/self.pixel_size)
        line_x1 = scale_bar_x + (scale_bar_rect_width-line_length)//2
        line_y = scale_bar_y + 20
        painter.setPen(QPen(Qt.black, 5))
        painter.drawLine(line_x1, line_y, line_x1+line_length, line_y)

        font = QFont("Arial", 18)
        painter.setFont(font)
        painter.drawText(scale_bar_x, scale_bar_y+40, scale_bar_rect_width, 22, Qt.AlignCenter, "10 µm")


        super().setPixmap(pixmap)
        self.update()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = ClickableCameraLabel()
    win.setPixmap(QPixmap(2048, 1536))
    win.show()
    sys.exit(app.exec_())
