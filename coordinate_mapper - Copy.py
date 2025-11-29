"""
Coordinate Mapper - Maps pixel coordinates to logical coordinates using perspective correction.
Ported from Tkinter to PySide6/Qt for integration with the volleyball stats application.
"""

import numpy as np
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGraphicsView, QGraphicsScene,
    QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsTextItem, QApplication, QPushButton
)
from PySide6.QtCore import Qt, QPointF, QRectF, Signal
from PySide6.QtGui import QPen, QBrush, QColor, QFont, QPainter


class CoordinateMapper(QMainWindow):
    """Coordinate mapper widget that maps pixel coordinates to logical coordinates."""
    
    # Signal emitted when a point is mapped to logical coordinates
    # Parameters: (logical_x, logical_y, pixel_x, pixel_y)
    coordinate_mapped = Signal(float, float, float, float)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Coordinate Mapper")
        
        # Fixed dimensions of the logical plane
        self.plane_width = 300
        self.plane_height = 600
        
        # Canvas/view dimensions
        self.canvas_width = 1800
        self.canvas_height = 1000
        
        # Storage for clicks
        self.corner_points = []  # Will store 4 corners + 2 midpoints (6 total)
        self.mapped_points = []  # Will store subsequent points
        
        # Graphics items for drawing
        self.graphics_items = []  # Store all graphics items for easy clearing
        self.point_ellipses = []  # Store ellipse items for the 6 corner/midpoints
        
        # Interaction modes
        self.mode = 'normal'  # 'normal', 'setup', 'modify'
        self.dragging_point_index = None  # Index of point being dragged
        self.drag_start_pos = None
        
        # Setup UI
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Reduce margins and spacing to minimize unused space
        layout.setContentsMargins(5, 5, 5, 5)  # left, top, right, bottom
        layout.setSpacing(5)  # Spacing between widgets
        
        # Button bar at the top
        button_layout = QHBoxLayout()
        
        self.set_boundaries_btn = QPushButton("Set Court Boundaries")
        self.set_boundaries_btn.setFont(QFont('Arial', 12))
        self.set_boundaries_btn.clicked.connect(self.start_set_boundaries)
        button_layout.addWidget(self.set_boundaries_btn)
        
        self.modify_court_btn = QPushButton("Modify Court")
        self.modify_court_btn.setFont(QFont('Arial', 12))
        self.modify_court_btn.clicked.connect(self.start_modify_court)
        self.modify_court_btn.setEnabled(False)  # Disabled until court is set
        button_layout.addWidget(self.modify_court_btn)
        
        button_layout.addStretch()  # Push buttons to the left
        layout.addLayout(button_layout)
        
        # Status label
        self.status_label = QLabel("Click 'Set Court Boundaries' to start")
        self.status_label.setFont(QFont('Arial', 12))
        layout.addWidget(self.status_label)
        
        # Graphics view for drawing
        self.scene = QGraphicsScene(0, 0, self.canvas_width, self.canvas_height)
        self.scene.setBackgroundBrush(QBrush(QColor(255, 255, 255)))  # White background
        
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setMinimumSize(self.canvas_width, self.canvas_height)
        self.view.setMaximumSize(self.canvas_width, self.canvas_height)
        layout.addWidget(self.view)
        
        # Coordinate display label
        self.coord_label = QLabel("")
        self.coord_label.setFont(QFont('Arial', 10))
        self.coord_label.setStyleSheet("color: blue;")
        layout.addWidget(self.coord_label)
        
        # Install event filter on the view to capture mouse clicks
        self.view.viewport().installEventFilter(self)
    
    def start_set_boundaries(self):
        """Start the process of setting court boundaries."""
        # Clear existing points and graphics
        self.corner_points.clear()
        self.mapped_points.clear()
        self.point_ellipses.clear()
        for item in self.graphics_items:
            self.scene.removeItem(item)
        self.graphics_items.clear()
        
        # Enter setup mode
        self.mode = 'setup'
        self.status_label.setText("Click to define bottom-left corner of the plane")
        self.coord_label.setText("")
        self.modify_court_btn.setEnabled(False)
    
    def start_modify_court(self):
        """Start the process of modifying court boundaries."""
        if len(self.corner_points) < 6:
            return
        
        # Enter modify mode
        self.mode = 'modify'
        self.status_label.setText("Click and drag any point to modify. Click 'Set Court Boundaries' to exit modify mode.")
        
        # Make the points visually distinct (larger and different color)
        for i, ellipse in enumerate(self.point_ellipses):
            ellipse.setBrush(QBrush(QColor(255, 128, 0)))  # Orange color
            ellipse.setCursor(Qt.CursorShape.PointingHandCursor)
    
    def eventFilter(self, obj, event):
        """Handle mouse events on the graphics view."""
        if obj == self.view.viewport():
            if event.type() == event.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    # Get click position in scene coordinates
                    scene_pos = self.view.mapToScene(event.position().toPoint())
                    x = scene_pos.x()
                    y = scene_pos.y()
                    
                    if self.mode == 'modify':
                        # Check if clicking on a point
                        self.dragging_point_index = self.find_point_at_position(x, y)
                        if self.dragging_point_index is not None:
                            self.drag_start_pos = [x, y]
                            return True
                    elif self.mode == 'setup' or (self.mode == 'normal' and len(self.corner_points) < 6):
                        self.on_click(x, y)
                        return True
                    elif self.mode == 'normal' and len(self.corner_points) >= 6:
                        self.on_click(x, y)
                        return True
            
            elif event.type() == event.Type.MouseMove:
                if self.mode == 'modify' and self.dragging_point_index is not None:
                    # Dragging a point
                    scene_pos = self.view.mapToScene(event.position().toPoint())
                    x = scene_pos.x()
                    y = scene_pos.y()
                    self.update_point_position(self.dragging_point_index, x, y)
                    return True
            
            elif event.type() == event.Type.MouseButtonRelease:
                if event.button() == Qt.MouseButton.LeftButton:
                    if self.mode == 'modify' and self.dragging_point_index is not None:
                        # Finish dragging
                        self.dragging_point_index = None
                        self.drag_start_pos = None
                        return True
        
        return super().eventFilter(obj, event)
    
    def find_point_at_position(self, x, y):
        """Find if there's a corner point near the given position."""
        threshold = 10  # pixels
        for i, point in enumerate(self.corner_points):
            px, py = point
            dist = ((x - px) ** 2 + (y - py) ** 2) ** 0.5
            if dist < threshold:
                return i
        return None
    
    def update_point_position(self, index, x, y):
        """Update the position of a corner point."""
        self.corner_points[index] = [x, y]
        self._redraw_plane()
    
    def on_click(self, x, y):
        """Handle a click at the given scene coordinates."""
        if len(self.corner_points) < 6 and self.mode == 'setup':
            # Still defining the corners and midpoints
            self.corner_points.append([x, y])
            
            # Draw a circle at the point
            radius = 5
            ellipse = QGraphicsEllipseItem(x - radius, y - radius, radius * 2, radius * 2)
            ellipse.setBrush(QBrush(QColor(255, 0, 0)))  # Red fill
            ellipse.setPen(QPen(QColor(0, 0, 0), 2))  # Black outline
            self.scene.addItem(ellipse)
            self.graphics_items.append(ellipse)
            self.point_ellipses.append(ellipse)  # Store reference
            
            # Label the point
            labels = ['BL (0,0)', 'BR (300,0)', 'TR (300,600)', 'TL (0,600)', 'ML (0,300)', 'MR (300,300)']
            text_item = QGraphicsTextItem(labels[len(self.corner_points) - 1])
            text_item.setPos(x, y - 15)
            text_item.setDefaultTextColor(QColor(0, 0, 0))
            font = QFont('Arial', 10)
            font.setBold(True)
            text_item.setFont(font)
            self.scene.addItem(text_item)
            self.graphics_items.append(text_item)
            
            # Update status and draw lines
            if len(self.corner_points) == 1:
                self.status_label.setText("Click to define bottom-right corner (300, 0)")
            elif len(self.corner_points) == 2:
                # Draw line between first two points
                line = QGraphicsLineItem(
                    self.corner_points[0][0], self.corner_points[0][1],
                    self.corner_points[1][0], self.corner_points[1][1]
                )
                line.setPen(QPen(QColor(0, 0, 255), 2))  # Blue line
                self.scene.addItem(line)
                self.graphics_items.append(line)
                self.status_label.setText("Click to define top-right corner (300, 600)")
            elif len(self.corner_points) == 3:
                # Draw line from second to third point
                line = QGraphicsLineItem(
                    self.corner_points[1][0], self.corner_points[1][1],
                    self.corner_points[2][0], self.corner_points[2][1]
                )
                line.setPen(QPen(QColor(0, 0, 255), 2))  # Blue line
                self.scene.addItem(line)
                self.graphics_items.append(line)
                self.status_label.setText("Click to define top-left corner (0, 600)")
            elif len(self.corner_points) == 4:
                # Complete the quadrilateral
                line1 = QGraphicsLineItem(
                    self.corner_points[2][0], self.corner_points[2][1],
                    self.corner_points[3][0], self.corner_points[3][1]
                )
                line1.setPen(QPen(QColor(0, 0, 255), 2))  # Blue line
                self.scene.addItem(line1)
                self.graphics_items.append(line1)
                
                line2 = QGraphicsLineItem(
                    self.corner_points[3][0], self.corner_points[3][1],
                    self.corner_points[0][0], self.corner_points[0][1]
                )
                line2.setPen(QPen(QColor(0, 0, 255), 2))  # Blue line
                self.scene.addItem(line2)
                self.graphics_items.append(line2)
                self.status_label.setText("Click left edge midpoint (0, 300)")
            elif len(self.corner_points) == 5:
                # Draw lines to left midpoint
                line1 = QGraphicsLineItem(
                    self.corner_points[0][0], self.corner_points[0][1],
                    self.corner_points[4][0], self.corner_points[4][1]
                )
                pen = QPen(QColor(255, 165, 0), 2)  # Orange
                pen.setStyle(Qt.PenStyle.DashLine)
                line1.setPen(pen)
                self.scene.addItem(line1)
                self.graphics_items.append(line1)
                
                line2 = QGraphicsLineItem(
                    self.corner_points[4][0], self.corner_points[4][1],
                    self.corner_points[3][0], self.corner_points[3][1]
                )
                line2.setPen(pen)
                self.scene.addItem(line2)
                self.graphics_items.append(line2)
                self.status_label.setText("Click right edge midpoint (300, 300)")
            elif len(self.corner_points) == 6:
                # Draw lines to right midpoint and center line
                pen = QPen(QColor(255, 165, 0), 2)  # Orange
                pen.setStyle(Qt.PenStyle.DashLine)
                
                line1 = QGraphicsLineItem(
                    self.corner_points[1][0], self.corner_points[1][1],
                    self.corner_points[5][0], self.corner_points[5][1]
                )
                line1.setPen(pen)
                self.scene.addItem(line1)
                self.graphics_items.append(line1)
                
                line2 = QGraphicsLineItem(
                    self.corner_points[5][0], self.corner_points[5][1],
                    self.corner_points[2][0], self.corner_points[2][1]
                )
                line2.setPen(pen)
                self.scene.addItem(line2)
                self.graphics_items.append(line2)
                
                line3 = QGraphicsLineItem(
                    self.corner_points[4][0], self.corner_points[4][1],
                    self.corner_points[5][0], self.corner_points[5][1]
                )
                line3.setPen(pen)
                self.scene.addItem(line3)
                self.graphics_items.append(line3)
                self.status_label.setText("Plane defined! Click anywhere inside to get coordinates")
                
                # Enable modify button and change to normal mode
                self.modify_court_btn.setEnabled(True)
                self.mode = 'normal'
        elif self.mode == 'normal' and len(self.corner_points) >= 6:
            # Map the clicked point to logical coordinates
            logical_coords = self.map_point_to_logical(x, y)
            
            if logical_coords is not None:
                # Draw a small point
                radius = 3
                ellipse = QGraphicsEllipseItem(x - radius, y - radius, radius * 2, radius * 2)
                ellipse.setBrush(QBrush(QColor(0, 255, 0)))  # Green fill
                ellipse.setPen(QPen(QColor(0, 0, 0), 1))  # Black outline
                self.scene.addItem(ellipse)
                self.graphics_items.append(ellipse)
                
                # Display coordinates
                coord_text = f"({logical_coords[0]:.2f}, {logical_coords[1]:.2f})"
                text_item = QGraphicsTextItem(coord_text)
                text_item.setPos(x, y + 15)
                text_item.setDefaultTextColor(QColor(0, 255, 0))  # Green text
                font = QFont('Arial', 9)
                text_item.setFont(font)
                self.scene.addItem(text_item)
                self.graphics_items.append(text_item)
                
                # Update label with latest coordinates
                self.coord_label.setText(
                    f"Latest point: [{logical_coords[0]:.2f}, {logical_coords[1]:.2f}]"
                )
                
                self.mapped_points.append([x, y, logical_coords[0], logical_coords[1]])
                
                # Emit signal with mapped coordinates
                self.coordinate_mapped.emit(logical_coords[0], logical_coords[1], x, y)
    
    def map_point_to_logical(self, x, y):
        """
        Map a pixel coordinate (x, y) to logical coordinates within the defined plane.
        Uses bilinear interpolation based on the 6 control points (4 corners + 2 midpoints).
        
        The control points are:
        0: bottom-left (0, 0)
        1: bottom-right (300, 0)
        2: top-right (300, 600)
        3: top-left (0, 600)
        4: mid-left (0, 300)
        5: mid-right (300, 300)
        
        The plane is divided into two halves for better perspective handling.
        
        Returns:
            [logical_x, logical_y] or None if mapping fails
        """
        if len(self.corner_points) < 6:
            return None
        
        # Get all control points
        bl = np.array(self.corner_points[0])  # bottom-left (0, 0)
        br = np.array(self.corner_points[1])  # bottom-right (300, 0)
        tr = np.array(self.corner_points[2])  # top-right (300, 600)
        tl = np.array(self.corner_points[3])  # top-left (0, 600)
        ml = np.array(self.corner_points[4])  # mid-left (0, 300)
        mr = np.array(self.corner_points[5])  # mid-right (300, 300)
        
        # Point to map
        p = np.array([x, y])
        
        # Try both halves and pick the one with better convergence
        results = []
        
        # Bottom half: BL, BR, MR, ML
        result_bottom = self._map_to_quad(p, bl, br, mr, ml)
        if result_bottom is not None:
            u, v, residual = result_bottom
            # Map to logical coords: bottom half has y from 0 to 300
            logical_x = u * self.plane_width
            logical_y = v * (self.plane_height / 2)  # v goes from 0 to 1, map to 0 to 300
            results.append((logical_x, logical_y, residual))
        
        # Top half: ML, MR, TR, TL
        result_top = self._map_to_quad(p, ml, mr, tr, tl)
        if result_top is not None:
            u, v, residual = result_top
            # Map to logical coords: top half has y from 300 to 600
            logical_x = u * self.plane_width
            logical_y = 300 + v * (self.plane_height / 2)  # v goes from 0 to 1, map to 300 to 600
            results.append((logical_x, logical_y, residual))
        
        # Pick the result with smaller residual (better fit)
        if not results:
            return None
        
        results.sort(key=lambda r: r[2])
        logical_x, logical_y, _ = results[0]
        
        return [logical_x, logical_y]
    
    def _map_to_quad(self, p, c0, c1, c2, c3):
        """
        Map point p to a quadrilateral defined by corners c0, c1, c2, c3.
        Returns (u, v, residual) or None if mapping fails.
        
        The quad mapping is: P(u,v) = (1-v)[(1-u)*c0 + u*c1] + v[(1-u)*c3 + u*c2]
        where c0=bottom-left, c1=bottom-right, c2=top-right, c3=top-left of the quad
        """
        # Use inverse bilinear interpolation to find (u, v) parameters
        u, v = 0.5, 0.5  # Initial guess
        
        for _ in range(30):  # Newton-Raphson iterations
            # Current position estimate
            P = (1-v)*((1-u)*c0 + u*c1) + v*((1-u)*c3 + u*c2)
            
            # Residual
            residual = P - p
            residual_norm = np.linalg.norm(residual)
            
            # Jacobian
            dP_du = (1-v)*(c1 - c0) + v*(c2 - c3)
            dP_dv = -((1-u)*c0 + u*c1) + ((1-u)*c3 + u*c2)
            
            # Jacobian matrix
            J = np.column_stack([dP_du, dP_dv])
            
            # Try to solve J * delta = -residual
            try:
                delta = np.linalg.solve(J, -residual)
                u += delta[0]
                v += delta[1]
                
                # Check convergence
                if residual_norm < 0.01:
                    break
            except np.linalg.LinAlgError:
                # Singular matrix
                return None
        
        # Calculate final residual
        final_P = (1-v)*((1-u)*c0 + u*c1) + v*((1-u)*c3 + u*c2)
        final_residual = np.linalg.norm(final_P - p)
        
        # Check if u and v are within reasonable bounds
        # Allow some tolerance outside [0,1] for numerical precision
        if u < -0.2 or u > 1.2 or v < -0.2 or v > 1.2:
            # Way outside bounds - probably wrong quadrant
            # Add large penalty to residual
            final_residual += 1000.0
        elif u < -0.05 or u > 1.05 or v < -0.05 or v > 1.05:
            # Slightly outside bounds - add smaller penalty
            out_of_bounds = max(0, -u, u-1, -v, v-1)
            final_residual += out_of_bounds * 100.0
        
        return (u, v, final_residual)
    
    def is_configured(self):
        """Check if the coordinate mapper has been configured with 6 control points."""
        return len(self.corner_points) >= 6
    
    def get_corner_points(self):
        """Get the current corner points (for saving configuration)."""
        return self.corner_points.copy()
    
    def set_corner_points(self, points):
        """Set the corner points (for loading configuration)."""
        if len(points) == 6:
            self.corner_points = [list(p) for p in points]
            self.mode = 'normal'
            self.modify_court_btn.setEnabled(True)
            self.status_label.setText("Plane defined! Click anywhere inside to get coordinates")
            # Redraw the plane
            self._redraw_plane()
    
    def _redraw_plane(self):
        """Redraw the plane based on current corner points."""
        # Clear existing graphics items
        for item in self.graphics_items:
            self.scene.removeItem(item)
        self.graphics_items.clear()
        self.point_ellipses.clear()
        
        # Redraw all points and lines
        if len(self.corner_points) >= 1:
            # Draw all points
            labels = ['BL (0,0)', 'BR (300,0)', 'TR (300,600)', 'TL (0,600)', 'ML (0,300)', 'MR (300,300)']
            for i, point in enumerate(self.corner_points):
                x, y = point
                radius = 5
                ellipse = QGraphicsEllipseItem(x - radius, y - radius, radius * 2, radius * 2)
                
                # Color based on mode
                if self.mode == 'modify':
                    ellipse.setBrush(QBrush(QColor(255, 128, 0)))  # Orange in modify mode
                else:
                    ellipse.setBrush(QBrush(QColor(255, 0, 0)))  # Red otherwise
                
                ellipse.setPen(QPen(QColor(0, 0, 0), 2))
                self.scene.addItem(ellipse)
                self.graphics_items.append(ellipse)
                self.point_ellipses.append(ellipse)  # Store reference
                
                if i < len(labels):
                    text_item = QGraphicsTextItem(labels[i])
                    text_item.setPos(x, y - 15)
                    text_item.setDefaultTextColor(QColor(0, 0, 0))
                    font = QFont('Arial', 10)
                    font.setBold(True)
                    text_item.setFont(font)
                    self.scene.addItem(text_item)
                    self.graphics_items.append(text_item)
            
            # Draw lines based on how many points we have
            if len(self.corner_points) >= 2:
                line = QGraphicsLineItem(
                    self.corner_points[0][0], self.corner_points[0][1],
                    self.corner_points[1][0], self.corner_points[1][1]
                )
                line.setPen(QPen(QColor(0, 0, 255), 2))
                self.scene.addItem(line)
                self.graphics_items.append(line)
            
            if len(self.corner_points) >= 3:
                line = QGraphicsLineItem(
                    self.corner_points[1][0], self.corner_points[1][1],
                    self.corner_points[2][0], self.corner_points[2][1]
                )
                line.setPen(QPen(QColor(0, 0, 255), 2))
                self.scene.addItem(line)
                self.graphics_items.append(line)
            
            if len(self.corner_points) >= 4:
                line1 = QGraphicsLineItem(
                    self.corner_points[2][0], self.corner_points[2][1],
                    self.corner_points[3][0], self.corner_points[3][1]
                )
                line1.setPen(QPen(QColor(0, 0, 255), 2))
                self.scene.addItem(line1)
                self.graphics_items.append(line1)
                
                line2 = QGraphicsLineItem(
                    self.corner_points[3][0], self.corner_points[3][1],
                    self.corner_points[0][0], self.corner_points[0][1]
                )
                line2.setPen(QPen(QColor(0, 0, 255), 2))
                self.scene.addItem(line2)
                self.graphics_items.append(line2)
            
            if len(self.corner_points) >= 5:
                pen = QPen(QColor(255, 165, 0), 2)
                pen.setStyle(Qt.PenStyle.DashLine)
                line1 = QGraphicsLineItem(
                    self.corner_points[0][0], self.corner_points[0][1],
                    self.corner_points[4][0], self.corner_points[4][1]
                )
                line1.setPen(pen)
                self.scene.addItem(line1)
                self.graphics_items.append(line1)
                
                line2 = QGraphicsLineItem(
                    self.corner_points[4][0], self.corner_points[4][1],
                    self.corner_points[3][0], self.corner_points[3][1]
                )
                line2.setPen(pen)
                self.scene.addItem(line2)
                self.graphics_items.append(line2)
            
            if len(self.corner_points) >= 6:
                pen = QPen(QColor(255, 165, 0), 2)
                pen.setStyle(Qt.PenStyle.DashLine)
                line1 = QGraphicsLineItem(
                    self.corner_points[1][0], self.corner_points[1][1],
                    self.corner_points[5][0], self.corner_points[5][1]
                )
                line1.setPen(pen)
                self.scene.addItem(line1)
                self.graphics_items.append(line1)
                
                line2 = QGraphicsLineItem(
                    self.corner_points[5][0], self.corner_points[5][1],
                    self.corner_points[2][0], self.corner_points[2][1]
                )
                line2.setPen(pen)
                self.scene.addItem(line2)
                self.graphics_items.append(line2)
                
                line3 = QGraphicsLineItem(
                    self.corner_points[4][0], self.corner_points[4][1],
                    self.corner_points[5][0], self.corner_points[5][1]
                )
                line3.setPen(pen)
                self.scene.addItem(line3)
                self.graphics_items.append(line3)
                
                self.status_label.setText("Plane defined! Click anywhere inside to get coordinates")


def main():
    """Main function to run the coordinate mapper as a standalone application."""
    import sys
    app = QApplication(sys.argv)
    window = CoordinateMapper()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
