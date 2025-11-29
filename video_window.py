"""
Video window for displaying volleyball game video.
Allows selecting a game and loading/playing the associated video file.
"""

import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QComboBox, QLabel, QFileDialog, QMessageBox, QSlider,
    QGroupBox, QCheckBox, QGraphicsView, QGraphicsScene, QGraphicsLineItem, QGraphicsEllipseItem
)
from PySide6.QtCore import Qt, QUrl, QPointF, QRectF, QEvent, QSize
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtGui import QPen, QColor, QBrush, QPainter, QPaintEvent, QPixmap, QImage
from database import VideoStatsDB


class DraggablePoint(QGraphicsEllipseItem):
    """Custom graphics item for draggable court boundary points."""
    
    def __init__(self, point_key, parent_window, parent=None):
        super().__init__(parent)
        self.point_key = point_key
        self.parent_window = parent_window
        point_radius = 20
        # Set rect so center is at (0, 0) in item coordinates
        # This means the ellipse goes from -radius to +radius in both directions
        self.setRect(-point_radius, -point_radius, point_radius * 2, point_radius * 2)
        point_brush = QBrush(QColor(255, 255, 0))  # Yellow points
        point_pen = QPen(QColor(0, 0, 0), 5)  # Thick black outline
        self.setBrush(point_brush)
        self.setPen(point_pen)
        self.setFlag(QGraphicsEllipseItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsEllipseItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsEllipseItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
    
    def itemChange(self, change, value):
        if change == QGraphicsEllipseItem.GraphicsItemChange.ItemPositionHasChanged:
            # Update court_points when item moves
            if self.parent_window and self.point_key and not getattr(self.parent_window, '_updating_lines', False):
                # Get center of ellipse in scene coordinates
                # Since rect is (-point_radius, -point_radius, point_radius*2, point_radius*2),
                # the center in item coordinates is (0, 0)
                # So the center in scene coordinates is just self.pos() + (point_radius, point_radius)
                point_radius = 20
                new_pos = self.pos() + QPointF(point_radius, point_radius)
                self.parent_window.court_points[self.point_key] = new_pos
                # Only update lines, don't recreate points (prevents infinite loop)
                self.parent_window.update_court_lines()
        return super().itemChange(change, value)


class CourtOverlayWidget(QWidget):
    """Custom widget to draw court overlay on top of video."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.court_points = None
        self.show_overlay = True
        self.edit_mode = False
        self.dragging_point = None
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, False)  # Allow system background
        # Ensure the widget is visible and can receive paint events
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        # Make sure widget accepts paint events
        self.setUpdatesEnabled(True)
    
    def set_court_points(self, points):
        """Set the court points to draw."""
        self.court_points = points if points else None
        self.update()
    
    def set_show_overlay(self, show):
        """Set whether to show the overlay."""
        self.show_overlay = show
        self.update()
    
    def set_edit_mode(self, edit):
        """Set whether in edit mode (allows dragging)."""
        self.edit_mode = edit
        self.update()
    
    def paintEvent(self, event: QPaintEvent):
        """Draw the court overlay."""
        painter = QPainter(self)
        if not painter.isActive():
            print("DEBUG: Painter not active!")
            return
        
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Enable composition mode for transparency
        painter.setCompositionMode(QPainter.CompositionMode.SourceOver)
        
        # Fill with completely transparent background
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        
        if not self.show_overlay:
            print("DEBUG: Overlay not shown")
            return
        
        if not self.court_points:
            # Draw a HUGE test rectangle to verify painting works - bright red covering most of screen
            painter.setPen(QPen(QColor(255, 0, 0), 30))
            painter.setBrush(QBrush(QColor(255, 0, 0, 200)))  # More opaque red
            painter.drawRect(50, 50, 500, 500)
            print("DEBUG: Overlay widget paintEvent called - no court points, drawing HUGE test rect")
            return
        
        print(f"DEBUG: Overlay widget paintEvent called - drawing court with {len(self.court_points)} points")
        
        # Draw court outline (4 corners)
        corners = [
            ('corner_tl', 'corner_tr'),
            ('corner_tr', 'corner_br'),
            ('corner_br', 'corner_bl'),
            ('corner_bl', 'corner_tl')
        ]
        
        pen = QPen(QColor(255, 0, 0), 10)  # Red lines - very thick for visibility
        painter.setPen(pen)
        
        for start_key, end_key in corners:
            if start_key in self.court_points and end_key in self.court_points:
                start = self.court_points[start_key]
                end = self.court_points[end_key]
                # Draw thick lines
                painter.drawLine(int(start.x()), int(start.y()), int(end.x()), int(end.y()))
                # Also draw a circle at each endpoint to make sure we see it
                painter.setBrush(QBrush(QColor(255, 0, 0)))
                painter.drawEllipse(int(start.x() - 5), int(start.y() - 5), 10, 10)
                painter.drawEllipse(int(end.x() - 5), int(end.y() - 5), 10, 10)
        
        # Draw centerline
        if 'centerline_top' in self.court_points and 'centerline_bottom' in self.court_points:
            centerline_pen = QPen(QColor(0, 255, 0), 10)  # Green line - very thick for visibility
            painter.setPen(centerline_pen)
            top = self.court_points['centerline_top']
            bottom = self.court_points['centerline_bottom']
            painter.drawLine(int(top.x()), int(top.y()), int(bottom.x()), int(bottom.y()))
            # Also draw circles at endpoints
            painter.setBrush(QBrush(QColor(0, 255, 0)))
            painter.drawEllipse(int(top.x() - 5), int(top.y() - 5), 10, 10)
            painter.drawEllipse(int(bottom.x() - 5), int(bottom.y() - 5), 10, 10)
        
        # Draw draggable points only in edit mode
        if self.edit_mode:
            point_radius = 20  # Even larger for visibility
            point_brush = QBrush(QColor(255, 255, 0))  # Yellow points
            point_pen = QPen(QColor(0, 0, 0), 5)  # Thick black outline
            
            painter.setBrush(point_brush)
            painter.setPen(point_pen)
            
            for point_pos in self.court_points.values():
                painter.drawEllipse(
                    int(point_pos.x() - point_radius),
                    int(point_pos.y() - point_radius),
                    point_radius * 2,
                    point_radius * 2
                )
    
    def get_point_at(self, pos: QPointF):
        """Get the point key at the given position, if any."""
        if not self.court_points:
            return None
        point_radius = 12
        for point_key, point_pos in self.court_points.items():
            dx = pos.x() - point_pos.x()
            dy = pos.y() - point_pos.y()
            if dx * dx + dy * dy <= point_radius * point_radius:
                return point_key
        return None


class VideoWindow(QMainWindow):
    """Main window for video playback."""
    
    def __init__(self, db: VideoStatsDB):
        super().__init__()
        self.db = db
        self.current_game_id = None
        self.current_video_path = None
        
        # Initialize media player
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        self.current_playback_rate = 1.0  # Default playback speed
        
        # Court overlay points (6 points: 4 corners + 2 centerline points)
        self.court_points = None  # Will be set when game is selected or boundaries are created
        self.show_overlay = True
        self.dragging_point = None
        self.edit_mode = False  # True when modifying boundaries
        
        # Setup UI
        self.setup_ui()
        self.connect_signals()
        self.populate_games_dropdown()
        
        # Set window properties (at least 1080x720)
        self.setWindowTitle("Video Stats - Video Player")
        self.setGeometry(100, 100, 1080, 720)
        self.setMinimumSize(1080, 720)
    
    def setup_ui(self):
        """Set up the user interface."""
        # Central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Top control panel
        control_panel = QWidget()
        control_layout = QHBoxLayout(control_panel)
        
        # Game selection
        game_label = QLabel("Select Game:")
        self.game_combo = QComboBox()
        self.game_combo.setMinimumWidth(400)
        
        # View mode buttons (shown after game is selected)
        self.view_png_btn = QPushButton("View PNG")
        self.view_png_btn.setEnabled(False)
        self.view_png_btn.setVisible(False)
        
        self.view_video_btn = QPushButton("View Video")
        self.view_video_btn.setEnabled(False)
        self.view_video_btn.setVisible(False)
        
        # Video file selection
        self.select_video_btn = QPushButton("Select Video File")
        self.select_video_btn.setEnabled(False)
        self.select_video_btn.setVisible(False)
        
        # Capture still image button
        self.capture_still_btn = QPushButton("Capture Still Image")
        self.capture_still_btn.setEnabled(False)
        self.capture_still_btn.setVisible(False)
        
        # Import PNG button
        self.import_png_btn = QPushButton("Import PNG")
        self.import_png_btn.setEnabled(False)
        self.import_png_btn.setVisible(False)
        
        # Current video label
        self.video_path_label = QLabel("No video file selected")
        self.video_path_label.setWordWrap(True)
        
        control_layout.addWidget(game_label)
        control_layout.addWidget(self.game_combo)
        control_layout.addWidget(self.view_png_btn)
        control_layout.addWidget(self.view_video_btn)
        control_layout.addWidget(self.select_video_btn)
        control_layout.addWidget(self.capture_still_btn)
        control_layout.addWidget(self.import_png_btn)
        control_layout.addStretch()
        
        main_layout.addWidget(control_panel)
        main_layout.addWidget(self.video_path_label)
        
        # Video container - will show either live video or captured still image
        video_container = QWidget()
        video_container.setMinimumSize(1080, 720)
        video_container.setMaximumSize(1080, 720)
        
        # Video widget for live playback
        self.video_widget = QVideoWidget(video_container)
        self.video_widget.setMinimumSize(1080, 720)
        self.video_widget.setGeometry(0, 0, 1080, 720)
        self.media_player.setVideoOutput(self.video_widget)
        
        # Label for displaying captured still image
        # Create a custom widget that will definitely paint
        class StillImageWidget(QWidget):
            def __init__(self, parent=None):
                super().__init__(parent)
                self._pixmap = None  # Use _pixmap to avoid conflict with pixmap() method
                self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
            
            def setPixmap(self, pixmap):
                self._pixmap = pixmap
                self.update()
            
            def pixmap(self):
                """Return the current pixmap (for compatibility with QLabel interface)."""
                return self._pixmap
            
            def paintEvent(self, event):
                print(f"DEBUG: StillImageWidget paintEvent called - widget visible: {self.isVisible()}, geometry: {self.geometry()}, size: {self.size()}")
                painter = QPainter(self)
                if not painter.isActive():
                    print("DEBUG: StillImageWidget paintEvent - painter not active!")
                    return
                
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                
                # Fill with blue background for debugging
                painter.fillRect(self.rect(), QColor(0, 0, 255))  # Blue
                print(f"DEBUG: StillImageWidget paintEvent - filled blue background, rect: {self.rect()}")
                
                # Draw red border
                pen = QPen(QColor(255, 0, 0), 5)  # Red, 5px
                painter.setPen(pen)
                border_rect = self.rect().adjusted(2, 2, -2, -2)
                painter.drawRect(border_rect)
                print(f"DEBUG: StillImageWidget paintEvent - drew red border, rect: {border_rect}")
                
                # Draw pixmap if available
                if self._pixmap and not self._pixmap.isNull():
                    # Scale pixmap to fit widget
                    scaled_pixmap = self._pixmap.scaled(
                        self.size(), 
                        Qt.AspectRatioMode.KeepAspectRatio, 
                        Qt.TransformationMode.SmoothTransformation
                    )
                    # Center the pixmap
                    x = (self.width() - scaled_pixmap.width()) // 2
                    y = (self.height() - scaled_pixmap.height()) // 2
                    painter.drawPixmap(x, y, scaled_pixmap)
                    print(f"DEBUG: StillImageWidget paintEvent - drew pixmap at ({x}, {y}), size: {scaled_pixmap.size()}")
                else:
                    print(f"DEBUG: StillImageWidget paintEvent - no pixmap to draw")
                
                painter.end()
                print(f"DEBUG: StillImageWidget paintEvent - finished painting")
        
        self.still_image_label = StillImageWidget(video_container)
        self.still_image_label.setMinimumSize(1080, 720)
        self.still_image_label.setGeometry(0, 0, 1080, 720)
        self.still_image_label.setVisible(False)  # Hidden initially
        self.still_image_pixmap = None
        
        # Graphics overlay for court lines - overlay on top of still image
        self.overlay_scene = QGraphicsScene()
        self.overlay_scene.setSceneRect(0, 0, 1080, 720)
        # CRITICAL: Set scene background to transparent
        from PySide6.QtGui import QBrush
        self.overlay_scene.setBackgroundBrush(QBrush(Qt.GlobalColor.transparent))
        
        self.overlay_view = QGraphicsView(self.overlay_scene, video_container)
        self.overlay_view.setMinimumSize(1080, 720)
        self.overlay_view.setMaximumSize(1080, 720)
        self.overlay_view.setGeometry(0, 0, 1080, 720)
        # CRITICAL: Make viewport transparent - use autoFillBackground False
        self.overlay_view.setAutoFillBackground(False)
        self.overlay_view.setStyleSheet("background: transparent; border: none;")
        self.overlay_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.overlay_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.overlay_view.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.overlay_view.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.overlay_view.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        # CRITICAL: Don't use opaque paint events - allows transparency
        self.overlay_view.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.overlay_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.overlay_view.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        # CRITICAL: Set viewport background to transparent - disable autoFillBackground
        self.overlay_view.viewport().setAutoFillBackground(False)
        self.overlay_view.viewport().setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.overlay_view.viewport().setStyleSheet("background: transparent;")
        self.overlay_view.setVisible(False)  # Hidden until still image is captured
        # Enable mouse tracking for dragging - CRITICAL for move events
        self.overlay_view.setMouseTracking(True)
        
        main_layout.addWidget(video_container)
        
        # Court overlay controls
        overlay_group = QGroupBox("Court Boundaries")
        overlay_layout = QVBoxLayout(overlay_group)
        
        # Button row
        button_row = QWidget()
        button_layout = QHBoxLayout(button_row)
        
        self.set_boundaries_btn = QPushButton("Set Court Boundaries")
        self.set_boundaries_btn.setEnabled(False)  # Enable only when still image is shown
        self.modify_boundaries_btn = QPushButton("Modify Court Boundaries")
        self.modify_boundaries_btn.setEnabled(False)
        self.save_boundaries_btn = QPushButton("Save Court Boundaries")
        self.save_boundaries_btn.setEnabled(False)
        self.back_to_video_btn = QPushButton("Back to Video")
        self.back_to_video_btn.setEnabled(False)
        
        # Store initial state
        self._still_image_captured = False
        
        button_layout.addWidget(self.set_boundaries_btn)
        button_layout.addWidget(self.modify_boundaries_btn)
        button_layout.addWidget(self.save_boundaries_btn)
        button_layout.addWidget(self.back_to_video_btn)
        button_layout.addStretch()
        
        overlay_layout.addWidget(button_row)
        
        # Toggle row
        toggle_row = QWidget()
        toggle_layout = QHBoxLayout(toggle_row)
        
        self.show_overlay_checkbox = QCheckBox("Show Court Boundaries")
        self.show_overlay_checkbox.setChecked(True)
        
        # Toggle button to switch between overlay on top vs still image on top
        self.toggle_overlay_top_btn = QPushButton("Toggle: Overlay on Top")
        self.toggle_overlay_top_btn.setCheckable(True)
        self.toggle_overlay_top_btn.setChecked(True)  # Default: overlay on top
        
        toggle_layout.addWidget(self.show_overlay_checkbox)
        toggle_layout.addWidget(self.toggle_overlay_top_btn)
        toggle_layout.addStretch()
        
        overlay_layout.addWidget(toggle_row)
        
        main_layout.addWidget(overlay_group)
        
        # Position slider
        position_panel = QWidget()
        position_layout = QHBoxLayout(position_panel)
        
        self.position_label = QLabel("00:00")
        self.position_label.setMinimumWidth(60)
        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setEnabled(False)
        self.duration_label = QLabel("00:00")
        self.duration_label.setMinimumWidth(60)
        
        position_layout.addWidget(self.position_label)
        position_layout.addWidget(self.position_slider)
        position_layout.addWidget(self.duration_label)
        
        main_layout.addWidget(position_panel)
        
        # Initialize overlay
        self.setup_court_overlay()
        
        # Install event filter on overlay view for mouse events
        # This must be done after overlay_view is created
        if hasattr(self, 'overlay_view'):
            self.overlay_view.installEventFilter(self)
            # Make sure overlay view accepts mouse events
            self.overlay_view.setAcceptDrops(False)
            self.overlay_view.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
        # Playback controls
        playback_panel = QWidget()
        playback_layout = QHBoxLayout(playback_panel)
        
        self.play_btn = QPushButton("Play")
        self.play_btn.setEnabled(False)
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setEnabled(False)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        
        # Speed control
        speed_label = QLabel("Speed:")
        self.speed_05_btn = QPushButton("0.5x")
        self.speed_075_btn = QPushButton("0.75x")
        self.speed_10_btn = QPushButton("1.0x")
        self.speed_10_btn.setEnabled(False)  # Default speed
        
        playback_layout.addWidget(self.play_btn)
        playback_layout.addWidget(self.pause_btn)
        playback_layout.addWidget(self.stop_btn)
        playback_layout.addStretch()
        playback_layout.addWidget(speed_label)
        playback_layout.addWidget(self.speed_05_btn)
        playback_layout.addWidget(self.speed_075_btn)
        playback_layout.addWidget(self.speed_10_btn)
        
        main_layout.addWidget(playback_panel)
    
    def connect_signals(self):
        """Connect signals to slots."""
        self.game_combo.currentIndexChanged.connect(self.on_game_selected)
        self.view_png_btn.clicked.connect(self.view_png_image)
        self.view_video_btn.clicked.connect(self.view_video)
        self.select_video_btn.clicked.connect(self.select_video_file)
        self.capture_still_btn.clicked.connect(self.capture_still_image)
        self.import_png_btn.clicked.connect(self.import_png_file)
        self.play_btn.clicked.connect(self.play_video)
        self.pause_btn.clicked.connect(self.pause_video)
        self.stop_btn.clicked.connect(self.stop_video)
        
        # Speed control buttons
        self.speed_05_btn.clicked.connect(lambda: self.set_playback_speed(0.5))
        self.speed_075_btn.clicked.connect(lambda: self.set_playback_speed(0.75))
        self.speed_10_btn.clicked.connect(lambda: self.set_playback_speed(1.0))
        
        # Position slider
        self.position_slider.sliderMoved.connect(self.set_position)
        self.position_slider.sliderPressed.connect(self.on_slider_pressed)
        self.position_slider.sliderReleased.connect(self.on_slider_released)
        
        # Overlay controls
        self.set_boundaries_btn.clicked.connect(self.set_court_boundaries)
        self.modify_boundaries_btn.clicked.connect(self.enable_modify_mode)
        self.save_boundaries_btn.clicked.connect(self.save_court_boundaries)
        self.back_to_video_btn.clicked.connect(self.back_to_video)
        self.show_overlay_checkbox.toggled.connect(self.toggle_overlay)
        self.toggle_overlay_top_btn.toggled.connect(self.toggle_overlay_top)
        
        # Media player signals
        self.media_player.playbackStateChanged.connect(self.on_playback_state_changed)
        self.media_player.errorOccurred.connect(self.on_media_error)
        self.media_player.positionChanged.connect(self.update_position)
        self.media_player.durationChanged.connect(self.update_duration)
    
    def populate_games_dropdown(self):
        """Populate the games comboBox with all games from the database."""
        if not self.db.conn:
            self.db.connect()
        
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT g.game_id, g.game_date, 
                   t1.name as team_us_name, t2.name as team_them_name,
                   g.video_file_path
            FROM games g
            INNER JOIN teams t1 ON g.team_us_id = t1.team_id
            INNER JOIN teams t2 ON g.team_them_id = t2.team_id
            ORDER BY g.game_date DESC, g.game_id DESC
        """)
        games = cursor.fetchall()
        
        self.game_combo.clear()
        
        # Add placeholder item
        self.game_combo.addItem("-- Select a Game --", None)
        
        for game in games:
            game_id, game_date, team_us_name, team_them_name, video_file_path = game
            # Format display text
            display_text = f"Game {game_id}: {team_us_name} vs {team_them_name} ({game_date})"
            self.game_combo.addItem(display_text)
            # Get still image path
            still_image_path = self.db.get_game_still_image_path(game_id)
            
            # Store game data in the item
            index = self.game_combo.count() - 1
            self.game_combo.setItemData(index, {
                'game_id': game_id,
                'video_file_path': video_file_path,
                'still_image_path': still_image_path
            }, Qt.UserRole)
        
        # Set to blank selection
        self.game_combo.setCurrentIndex(0)
    
    def on_game_selected(self, index: int):
        """Handle game selection from dropdown."""
        if index <= 0:  # Placeholder or invalid selection
            self.current_game_id = None
            self.current_video_path = None
            self.court_points = None
            self.select_video_btn.setEnabled(False)
            self.modify_boundaries_btn.setEnabled(False)
            self.save_boundaries_btn.setEnabled(False)
            # Don't disable set_boundaries_btn if still image is captured
            if not (hasattr(self, '_still_image_captured') and self._still_image_captured):
                self.set_boundaries_btn.setEnabled(False)
            self.video_path_label.setText("No video file selected")
            self.stop_video()
            self.draw_court_overlay()
            return
        
        # Get game data
        item_data = self.game_combo.itemData(index, Qt.UserRole)
        if not item_data:
            return
        
        self.current_game_id = item_data.get('game_id')
        stored_video_path = item_data.get('video_file_path')
        stored_still_image_path = item_data.get('still_image_path')
        
        # Show view buttons based on what's available
        has_png = stored_still_image_path and Path(stored_still_image_path).exists()
        has_video = stored_video_path and Path(stored_video_path).exists()
        
        self.view_png_btn.setVisible(has_png)
        self.view_png_btn.setEnabled(has_png)
        self.view_video_btn.setVisible(has_video)
        self.view_video_btn.setEnabled(has_video)
        self.select_video_btn.setVisible(True)
        self.select_video_btn.setEnabled(True)
        self.capture_still_btn.setVisible(False)  # Only shown when viewing video
        self.import_png_btn.setVisible(True)
        self.import_png_btn.setEnabled(True)  # Always available when game is selected
        
        # Load court boundaries from database
        boundaries = self.db.get_game_court_boundaries(self.current_game_id)
        if boundaries:
            # Convert tuples to QPointF
            self.court_points = {
                key: QPointF(x, y)
                for key, (x, y) in boundaries.items()
            }
            self.modify_boundaries_btn.setEnabled(True)
            self.save_boundaries_btn.setEnabled(True)
        else:
            self.court_points = None
            self.modify_boundaries_btn.setEnabled(False)
            self.save_boundaries_btn.setEnabled(False)
        
        # Don't auto-load anything - user must choose PNG or Video
        self.video_path_label.setText("Select 'View PNG', 'View Video', or 'Import PNG' to continue")
        self.current_video_path = None
        self.stop_video()
        
        # Update overlay
        self.edit_mode = False
        self.draw_court_overlay()
        
        # Ensure set_boundaries_btn is enabled if still image is captured
        if hasattr(self, '_still_image_captured') and self._still_image_captured:
            self.set_boundaries_btn.setEnabled(True)
    
    def select_video_file(self):
        """Open file dialog to select a video file."""
        if not self.current_game_id:
            QMessageBox.warning(self, "No Game Selected", "Please select a game first!")
            return
        
        # Open file dialog
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Video File",
            "",
            "Video Files (*.mp4 *.avi *.mov *.mkv *.wmv *.flv *.webm);;All Files (*)"
        )
        
        if file_path:
            self.current_video_path = file_path
            video_path_obj = Path(file_path)
            self.video_path_label.setText(f"Video: {video_path_obj.name}")
            
            # Save to database
            self.db.update_game_video_path(self.current_game_id, file_path)
            
            # Update dropdown item data
            current_index = self.game_combo.currentIndex()
            item_data = self.game_combo.itemData(current_index, Qt.UserRole)
            if item_data:
                item_data['video_file_path'] = file_path
                self.game_combo.setItemData(current_index, item_data, Qt.UserRole)
            
            # Load and play video
            self.load_video(file_path)
    
    def import_png_file(self):
        """Import a PNG file to use as the still image for the current game."""
        if not self.current_game_id:
            QMessageBox.warning(self, "No Game Selected", "Please select a game first!")
            return
        
        # Open file dialog to select PNG file
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import PNG Still Image",
            "",
            "PNG Files (*.png);;All Files (*)"
        )
        
        if not file_path:
            return
        
        png_path = Path(file_path)
        if not png_path.exists():
            QMessageBox.warning(self, "File Not Found", f"PNG file not found:\n{file_path}")
            return
        
        # Load PNG file
        pixmap = QPixmap(str(png_path))
        if pixmap.isNull():
            QMessageBox.warning(self, "Load Failed", f"Failed to load PNG file:\n{file_path}")
            return
        
        # Scale to 1080x720 if needed
        if pixmap.width() != 1080 or pixmap.height() != 720:
            pixmap = pixmap.scaled(1080, 720, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        
        # Store the pixmap
        self.still_image_pixmap = pixmap
        
        # Copy to still_images directory and save path in database
        if self.current_game_id:
            # Create still_images directory if it doesn't exist
            still_images_dir = Path("still_images")
            still_images_dir.mkdir(exist_ok=True)
            
            # Copy PNG file to still_images directory
            dest_path = still_images_dir / f"game_{self.current_game_id}_still.png"
            try:
                import shutil
                shutil.copy2(png_path, dest_path)
                # Update database with PNG path
                self.db.update_game_still_image_path(self.current_game_id, str(dest_path))
                print(f"DEBUG: Imported PNG saved to {dest_path}")
                QMessageBox.information(self, "PNG Imported", f"PNG file imported and saved to:\n{dest_path}")
            except Exception as e:
                QMessageBox.warning(self, "Import Failed", f"Failed to copy PNG file:\n{str(e)}")
                return
        
        # Display the imported image
        self.still_image_label.setPixmap(self.still_image_pixmap)
        
        # Hide video widget, show still image
        self.video_widget.setVisible(False)
        self.video_widget.hide()
        
        # Get parent container
        video_container = self.still_image_label.parent()
        if video_container:
            video_container.setVisible(True)
            video_container.show()
        
        self.still_image_label.setVisible(True)
        self.still_image_label.show()
        self.still_image_label.raise_()
        
        # Force update and repaint
        self.still_image_label.update()
        self.still_image_label.repaint()
        if video_container:
            video_container.update()
            video_container.repaint()
        
        # Hide overlay initially
        self.overlay_view.setVisible(False)
        self.overlay_view.hide()
        
        # Enable set boundaries button
        self.set_boundaries_btn.setEnabled(True)
        self._still_image_captured = True
        
        # Update label
        self.video_path_label.setText(f"Still Image: {dest_path.name if self.current_game_id else png_path.name}")
        
        # Process events to ensure display
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()
        
        # Draw overlay if boundaries exist
        self.draw_court_overlay()
    
    def view_png_image(self):
        """Load and display the PNG still image for the current game."""
        if not self.current_game_id:
            QMessageBox.warning(self, "No Game Selected", "Please select a game first!")
            return
        
        # Get still image path from database
        still_image_path = self.db.get_game_still_image_path(self.current_game_id)
        if not still_image_path:
            QMessageBox.warning(self, "No Still Image", "No still image found for this game. Please capture one from video first.")
            return
        
        png_path = Path(still_image_path)
        if not png_path.exists():
            QMessageBox.warning(self, "File Not Found", f"Still image file not found:\n{still_image_path}")
            return
        
        # Load PNG file
        pixmap = QPixmap(str(png_path))
        if pixmap.isNull():
            QMessageBox.warning(self, "Load Failed", f"Failed to load PNG file:\n{still_image_path}")
            return
        
        # Scale to 1080x720 if needed
        if pixmap.width() != 1080 or pixmap.height() != 720:
            pixmap = pixmap.scaled(1080, 720, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        
        # Store and display
        self.still_image_pixmap = pixmap
        self.still_image_label.setPixmap(self.still_image_pixmap)
        
        # Hide video widget, show still image
        self.video_widget.setVisible(False)
        self.video_widget.hide()
        
        # Get parent container
        video_container = self.still_image_label.parent()
        if video_container:
            video_container.setVisible(True)
            video_container.show()
        
        self.still_image_label.setVisible(True)
        self.still_image_label.show()
        self.still_image_label.raise_()
        
        # Force update and repaint
        self.still_image_label.update()
        self.still_image_label.repaint()
        if video_container:
            video_container.update()
            video_container.repaint()
        
        # Hide overlay initially
        self.overlay_view.setVisible(False)
        self.overlay_view.hide()
        
        # Enable set boundaries button
        self.set_boundaries_btn.setEnabled(True)
        self._still_image_captured = True
        
        # Update label
        self.video_path_label.setText(f"Still Image: {png_path.name}")
        
        # Process events to ensure display
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()
        
        # Draw overlay if boundaries exist
        self.draw_court_overlay()
    
    def view_video(self):
        """Load and display the video for the current game."""
        if not self.current_game_id:
            QMessageBox.warning(self, "No Game Selected", "Please select a game first!")
            return
        
        # Get video path from database
        video_path = self.db.get_game_video_path(self.current_game_id)
        if not video_path:
            QMessageBox.warning(self, "No Video", "No video file found for this game. Please select a video file first.")
            return
        
        # Load video
        self.current_video_path = video_path
        self.load_video(video_path)
        
        # Show video widget, hide still image
        self.still_image_label.setVisible(False)
        self.still_image_label.hide()
        self.video_widget.setVisible(True)
        self.video_widget.show()
        self.video_widget.raise_()
        
        # Show overlay
        self.overlay_view.setVisible(True)
        self.overlay_view.show()
        self.overlay_view.raise_()
        
        # Enable capture still button
        self.capture_still_btn.setVisible(True)
        self.capture_still_btn.setEnabled(True)
        
        # Update label
        self.video_path_label.setText(f"Video: {Path(video_path).name}")
        
        print(f"DEBUG: view_video - capture_still_btn visible: {self.capture_still_btn.isVisible()}, enabled: {self.capture_still_btn.isEnabled()}")
    
    def load_video(self, file_path: str):
        """Load a video file into the media player."""
        if not Path(file_path).exists():
            QMessageBox.warning(self, "File Not Found", f"Video file not found:\n{file_path}")
            return
        
        # Enable capture still button when video is loaded
        self.capture_still_btn.setVisible(True)
        self.capture_still_btn.setEnabled(True)
        
        # Set media source
        url = QUrl.fromLocalFile(file_path)
        self.media_player.setSource(url)
        
        # Set playback rate
        self.media_player.setPlaybackRate(self.current_playback_rate)
        
        # Enable playback controls
        self.play_btn.setEnabled(True)
        self.pause_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.position_slider.setEnabled(True)
        self.capture_still_btn.setEnabled(True)  # Enable capture after video is loaded
    
    def play_video(self):
        """Play the video."""
        if self.media_player.source().isEmpty():
            if not self.current_video_path:
                QMessageBox.warning(self, "No Video", "Please select a video file first!")
                return
            self.load_video(self.current_video_path)
        
        self.media_player.play()
    
    def pause_video(self):
        """Pause the video."""
        self.media_player.pause()
    
    def stop_video(self):
        """Stop the video."""
        self.media_player.stop()
        self.play_btn.setEnabled(False)
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.position_slider.setValue(0)
        self.position_label.setText("00:00")
        self.duration_label.setText("00:00")
    
    def set_playback_speed(self, speed: float):
        """Set the playback speed."""
        self.current_playback_rate = speed
        self.media_player.setPlaybackRate(speed)
        
        # Update button states
        self.speed_05_btn.setEnabled(speed != 0.5)
        self.speed_075_btn.setEnabled(speed != 0.75)
        self.speed_10_btn.setEnabled(speed != 1.0)
    
    def format_time(self, milliseconds: int) -> str:
        """Format milliseconds as MM:SS."""
        total_seconds = milliseconds // 1000
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"
    
    def update_position(self, position: int):
        """Update the position slider and label."""
        if not self.position_slider.isSliderDown():  # Only update if user isn't dragging
            self.position_slider.setValue(position)
        self.position_label.setText(self.format_time(position))
    
    def update_duration(self, duration: int):
        """Update the duration label and slider range."""
        self.position_slider.setRange(0, duration)
        self.duration_label.setText(self.format_time(duration))
    
    def set_position(self, position: int):
        """Set the video position."""
        self.media_player.setPosition(position)
    
    def on_slider_pressed(self):
        """Handle slider press - pause video while seeking."""
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
    
    def on_slider_released(self):
        """Handle slider release - resume video if it was playing."""
        # Position is already set by sliderMoved signal
        # Video will resume if it was playing (handled by user)
        pass
    
    def setup_court_overlay(self):
        """Set up the court overlay graphics."""
        self.draw_court_overlay()
    
    def draw_court_overlay(self):
        """Draw the court overlay lines and points using QGraphicsScene."""
        # Prevent infinite recursion
        if getattr(self, '_drawing_overlay', False):
            return
        self._drawing_overlay = True
        
        try:
            # Clear existing items (but preserve draggable points if in edit mode)
            if self.edit_mode:
                # Store existing draggable points and their current positions
                existing_points = {}
                for item in self.overlay_scene.items():
                    if isinstance(item, DraggablePoint):
                        existing_points[item.point_key] = item
                # Remove only non-DraggablePoint items (lines, etc.)
                items_to_remove = [item for item in self.overlay_scene.items() if not isinstance(item, DraggablePoint)]
                for item in items_to_remove:
                    self.overlay_scene.removeItem(item)
            else:
                # Clear all items
                self.overlay_scene.clear()
            
            if not self.show_overlay:
                return
            
            if not self.court_points:
                # Draw a HUGE test rectangle with bright colors
                from PySide6.QtWidgets import QGraphicsRectItem
                # Draw multiple overlapping rectangles to ensure visibility
                test_rect1 = QGraphicsRectItem(10, 10, 300, 300)
                test_rect1.setPen(QPen(QColor(255, 0, 0), 50))  # Very thick red border
                test_rect1.setBrush(QBrush(QColor(255, 0, 0, 255)))  # Fully opaque red
                self.overlay_scene.addItem(test_rect1)
                
                # Also add a bright yellow rectangle
                test_rect2 = QGraphicsRectItem(400, 100, 200, 200)
                test_rect2.setPen(QPen(QColor(255, 255, 0), 50))
                test_rect2.setBrush(QBrush(QColor(255, 255, 0, 255)))
                self.overlay_scene.addItem(test_rect2)
                
                print("DEBUG: Drawing HUGE test rects in graphics scene")
                return
            
            # Draw court outline (4 corners)
            corners = [
                ('corner_tl', 'corner_tr'),
                ('corner_tr', 'corner_br'),
                ('corner_br', 'corner_bl'),
                ('corner_bl', 'corner_tl')
            ]
            
            pen = QPen(QColor(255, 0, 0), 10)  # Red lines - very thick
            
            for start_key, end_key in corners:
                if start_key in self.court_points and end_key in self.court_points:
                    start = self.court_points[start_key]
                    end = self.court_points[end_key]
                    line = QGraphicsLineItem(start.x(), start.y(), end.x(), end.y())
                    line.setPen(pen)
                    self.overlay_scene.addItem(line)
            
            # Draw centerline
            if 'centerline_top' in self.court_points and 'centerline_bottom' in self.court_points:
                centerline_pen = QPen(QColor(0, 255, 0), 10)  # Green line
                top = self.court_points['centerline_top']
                bottom = self.court_points['centerline_bottom']
                centerline = QGraphicsLineItem(top.x(), top.y(), bottom.x(), bottom.y())
                centerline.setPen(centerline_pen)
                self.overlay_scene.addItem(centerline)
            
            # Draw draggable points only in edit mode (if not already created)
            if self.edit_mode:
                point_radius = 20
                
                # Check if points already exist - if they do, update their positions from court_points
                # Don't recreate them to avoid position drift
                existing_points = {}
                for item in self.overlay_scene.items():
                    if isinstance(item, DraggablePoint):
                        existing_points[item.point_key] = item
                
                for point_key, point_pos in self.court_points.items():
                    if point_key in existing_points:
                        # Update existing point position - set top-left of ellipse so center is at point_pos
                        existing_points[point_key].setPos(point_pos.x() - point_radius, point_pos.y() - point_radius)
                    else:
                        # Create new draggable point
                        draggable_point = DraggablePoint(point_key, self)
                        # Set position so center of ellipse is at point_pos
                        draggable_point.setPos(point_pos.x() - point_radius, point_pos.y() - point_radius)
                        self.overlay_scene.addItem(draggable_point)
            
            self.overlay_view.update()
        finally:
            self._drawing_overlay = False
    
    def update_court_lines(self):
        """Update only the court lines without recreating points (prevents infinite loop)."""
        if getattr(self, '_updating_lines', False):
            return
        self._updating_lines = True
        
        try:
            # Remove only line items, keep draggable points
            items_to_remove = []
            for item in self.overlay_scene.items():
                if isinstance(item, QGraphicsLineItem):
                    items_to_remove.append(item)
            for item in items_to_remove:
                self.overlay_scene.removeItem(item)
            
            if not self.show_overlay or not self.court_points:
                return
            
            # Redraw court outline (4 corners)
            corners = [
                ('corner_tl', 'corner_tr'),
                ('corner_tr', 'corner_br'),
                ('corner_br', 'corner_bl'),
                ('corner_bl', 'corner_tl')
            ]
            
            pen = QPen(QColor(255, 0, 0), 10)  # Red lines
            
            for start_key, end_key in corners:
                if start_key in self.court_points and end_key in self.court_points:
                    start = self.court_points[start_key]
                    end = self.court_points[end_key]
                    line = QGraphicsLineItem(start.x(), start.y(), end.x(), end.y())
                    line.setPen(pen)
                    self.overlay_scene.addItem(line)
            
            # Redraw centerline
            if 'centerline_top' in self.court_points and 'centerline_bottom' in self.court_points:
                centerline_pen = QPen(QColor(0, 255, 0), 10)  # Green line
                top = self.court_points['centerline_top']
                bottom = self.court_points['centerline_bottom']
                centerline = QGraphicsLineItem(top.x(), top.y(), bottom.x(), bottom.y())
                centerline.setPen(centerline_pen)
                self.overlay_scene.addItem(centerline)
            
            self.overlay_view.update()
        finally:
            self._updating_lines = False
    
    def back_to_video(self):
        """Switch back to live video view."""
        self.still_image_label.setVisible(False)
        self.overlay_view.setVisible(False)
        self.video_widget.setVisible(True)
        self.set_boundaries_btn.setEnabled(False)
        self.modify_boundaries_btn.setEnabled(False)
        self.save_boundaries_btn.setEnabled(False)
        self.back_to_video_btn.setEnabled(False)
        self.edit_mode = False
        self.show_overlay = False
        # Keep the still image captured flag so user can go back
        # self._still_image_captured = False  # Don't reset this, allow going back
    
    def set_court_boundaries(self):
        """Set initial court boundaries (500x500 in center of screen)."""
        if not self.current_game_id:
            QMessageBox.warning(self, "No Game Selected", "Please select a game first!")
            return
        
        # Check if still image is available (either captured or loaded from PNG)
        if not hasattr(self, '_still_image_captured') or not self._still_image_captured:
            QMessageBox.warning(self, "No Still Image", "Please view the PNG image first using 'View PNG' button!")
            return
        
        if not self.still_image_pixmap:
            QMessageBox.warning(self, "No Still Image", "Still image not loaded. Please view the PNG image first!")
            return
        
        # Make sure still image is visible
        if not self.still_image_label.isVisible():
            self.still_image_label.setPixmap(self.still_image_pixmap)
            self.still_image_label.setVisible(True)
            self.still_image_label.show()
            self.video_widget.setVisible(False)
        
        # Show overlay on top of still image
        self.overlay_view.setVisible(True)
        self.overlay_view.show()
        self.overlay_view.raise_()
        
        # Calculate center position for 500x500 court
        center_x = 1080 / 2
        center_y = 720 / 2
        half_size = 250  # Half of 500
        
        self.court_points = {
            'corner_tl': QPointF(center_x - half_size, center_y - half_size),
            'corner_tr': QPointF(center_x + half_size, center_y - half_size),
            'corner_bl': QPointF(center_x - half_size, center_y + half_size),
            'corner_br': QPointF(center_x + half_size, center_y + half_size),
            'centerline_top': QPointF(center_x, center_y - half_size),
            'centerline_bottom': QPointF(center_x, center_y + half_size)
        }
        
        self.edit_mode = False
        self.modify_boundaries_btn.setEnabled(True)
        self.save_boundaries_btn.setEnabled(True)
        
        # Ensure still image and overlay are visible
        print(f"DEBUG: set_court_boundaries - still_image_pixmap exists: {self.still_image_pixmap is not None}")
        print(f"DEBUG: set_court_boundaries - still_image_label visible before: {self.still_image_label.isVisible()}")
        
        if hasattr(self, 'overlay_view') and hasattr(self, 'still_image_label'):
            # CRITICAL: Restore still image visibility and pixmap
            # Hide video widget first
            self.video_widget.setVisible(False)
            self.video_widget.hide()
            
            # Restore still image pixmap and make it visible
            if self.still_image_pixmap:
                self.still_image_label.setPixmap(self.still_image_pixmap)
                print(f"DEBUG: Restored pixmap to still image label, size: {self.still_image_pixmap.size()}")
            
            # Make sure still image is visible
            self.still_image_label.setVisible(True)
            self.still_image_label.show()
            self.still_image_label.raise_()  # Raise it first
            
            # Show overlay on top
            self.overlay_view.setVisible(True)
            self.overlay_view.show()
            self.still_image_label.lower()  # Put still image below overlay
            self.overlay_view.raise_()  # Put overlay on top
            
            # Force updates - CRITICAL: Update parent container too
            video_container = self.still_image_label.parent()
            if video_container:
                video_container.update()
                video_container.repaint()
            
            self.still_image_label.update()
            self.still_image_label.repaint()
            self.overlay_view.update()
            self.overlay_view.repaint()
            self.overlay_view.viewport().update()
            self.overlay_view.viewport().repaint()
            
            print(f"DEBUG: set_court_boundaries - still_image_label visible after: {self.still_image_label.isVisible()}")
            print(f"DEBUG: set_court_boundaries - still_image_label has pixmap: {self.still_image_label.pixmap() is not None}")
            if self.still_image_label.pixmap():
                print(f"DEBUG: set_court_boundaries - pixmap size: {self.still_image_label.pixmap().size()}")
            print(f"DEBUG: set_court_boundaries - video_widget visible: {self.video_widget.isVisible()}")
            print(f"DEBUG: set_court_boundaries - overlay_view visible: {self.overlay_view.isVisible()}")
            print(f"DEBUG: set_court_boundaries - overlay_view viewport background: {self.overlay_view.viewport().styleSheet()}")
            
            # Ensure still image is visible
            self.still_image_label.setVisible(True)
            self.still_image_label.show()
            self.video_widget.setVisible(False)
            # Show overlay on top of still image
            self.overlay_view.setVisible(True)
            self.overlay_view.show()
            # Ensure proper stacking order - still image must be below overlay
            self.still_image_label.lower()
            self.overlay_view.raise_()
            # Force updates
            self.still_image_label.update()
            self.still_image_label.repaint()
            self.overlay_view.update()
            self.overlay_view.repaint()
            
            print(f"DEBUG: Still image visible: {self.still_image_label.isVisible()}, has pixmap: {self.still_image_label.pixmap() is not None}")
        
        # Update overlay
        self.show_overlay = True
        self.edit_mode = False
        self.draw_court_overlay()
        
        print(f"DEBUG: set_court_boundaries - points set: {self.court_points}")
        if hasattr(self, 'overlay_view'):
            print(f"DEBUG: set_court_boundaries - overlay visible: {self.overlay_view.isVisible()}")
            print(f"DEBUG: set_court_boundaries - overlay geometry: {self.overlay_view.geometry()}")
        
        QMessageBox.information(self, "Court Boundaries Set", 
                                "Court boundaries have been set. Click 'Modify Court Boundaries' to adjust them.")
    
    def enable_modify_mode(self):
        """Enable modification mode for court boundaries."""
        if not self.court_points:
            QMessageBox.warning(self, "No Boundaries", 
                              "Please set court boundaries first!")
            return
        
        self.edit_mode = True
        self.show_overlay = True
        self.draw_court_overlay()
        QMessageBox.information(self, "Modify Mode", 
                               "You can now drag the yellow points to adjust the court boundaries.")
    
    def save_court_boundaries(self):
        """Save court boundaries to database."""
        if not self.current_game_id:
            QMessageBox.warning(self, "No Game Selected", "Please select a game first!")
            return
        
        if not self.court_points:
            QMessageBox.warning(self, "No Boundaries", 
                              "Please set court boundaries first!")
            return
        
        try:
            self.db.save_game_court_boundaries(self.current_game_id, self.court_points)
            self.edit_mode = False
            self.draw_court_overlay()
            QMessageBox.information(self, "Saved", 
                                   "Court boundaries have been saved to the database.")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", 
                               f"Failed to save court boundaries:\n{str(e)}")
    
    def eventFilter(self, obj, event):
        """Event filter to handle mouse events on overlay view."""
        if obj == self.overlay_view and self.show_overlay and self.edit_mode and self.court_points:
            if event.type() == QEvent.Type.MouseButtonPress:
                # Get mouse position in view coordinates
                view_pos = event.position().toPoint()
                # Convert to scene coordinates
                scene_pos = self.overlay_view.mapToScene(view_pos)
                # Find item at this position
                item = self.overlay_scene.itemAt(scene_pos, self.overlay_view.transform())
                
                if item and isinstance(item, QGraphicsEllipseItem):
                    point_key = item.data(0)
                    if point_key:
                        self.dragging_point = point_key
                        print(f"DEBUG: Started dragging point: {point_key} at scene pos: {scene_pos}")
                        # Accept the event to prevent it from propagating
                        event.accept()
                        return True
            
            elif event.type() == QEvent.Type.MouseMove:
                if self.dragging_point:
                    # Get mouse position in view coordinates
                    view_pos = event.position().toPoint()
                    # Convert to scene coordinates
                    scene_pos = self.overlay_view.mapToScene(view_pos)
                    
                    # Constrain to scene bounds
                    x = max(0, min(scene_pos.x(), self.overlay_scene.width()))
                    y = max(0, min(scene_pos.y(), self.overlay_scene.height()))
                    
                    # Update point position
                    self.court_points[self.dragging_point] = QPointF(x, y)
                    
                    # Redraw overlay
                    self.draw_court_overlay()
                    print(f"DEBUG: Moving point {self.dragging_point} to ({x}, {y})")
                    event.accept()
                    return True
            
            elif event.type() == QEvent.Type.MouseButtonRelease:
                if self.dragging_point:
                    print(f"DEBUG: Stopped dragging point: {self.dragging_point}")
                    self.dragging_point = None
                    # Redraw overlay
                    self.draw_court_overlay()
                    event.accept()
                    return True
        
        return super().eventFilter(obj, event)
    
    def toggle_overlay(self, checked: bool):
        """Toggle overlay visibility."""
        self.show_overlay = checked
        self.draw_court_overlay()
    
    def toggle_overlay_top(self, checked: bool):
        """Toggle whether overlay is on top or still image is on top."""
        if checked:
            # Overlay on top (default)
            self.still_image_label.lower()
            self.overlay_view.setVisible(True)
            self.overlay_view.show()
            self.overlay_view.raise_()
            self.toggle_overlay_top_btn.setText("Toggle: Overlay on Top")
            print("DEBUG: Overlay is now on top")
        else:
            # Still image on top - hide overlay completely and show still image
            self.overlay_view.setVisible(False)
            self.overlay_view.hide()
            self.overlay_view.lower()
            
            # CRITICAL: Ensure still image pixmap is set and visible
            if self.still_image_pixmap and not self.still_image_pixmap.isNull():
                # Set pixmap on the custom widget
                if hasattr(self.still_image_label, 'setPixmap'):
                    self.still_image_label.setPixmap(self.still_image_pixmap)
                else:
                    # Fallback for QLabel
                    self.still_image_label.setPixmap(self.still_image_pixmap)
                print(f"DEBUG: toggle_overlay_top - Set pixmap, size: {self.still_image_pixmap.size()}")
                print(f"DEBUG: toggle_overlay_top - Label size: {self.still_image_label.size()}")
                # Force immediate repaint
                self.still_image_label.update()
                self.still_image_label.repaint()
            else:
                print("DEBUG: toggle_overlay_top - WARNING: No valid pixmap!")
            
            # CRITICAL: Ensure widget is properly shown and raised
            video_container = self.still_image_label.parent()
            if video_container:
                # Ensure container is visible and shown first
                video_container.setVisible(True)
                video_container.show()
                video_container.raise_()
            
            self.still_image_label.setVisible(True)
            self.still_image_label.show()
            self.still_image_label.raise_()
            self.still_image_label.activateWindow()  # Try to activate the widget
            
            # Force the widget to be on top by lowering everything else first
            if video_container:
                for child in video_container.findChildren(QWidget):
                    if child != self.still_image_label:
                        child.lower()
                self.still_image_label.raise_()
            
            self.toggle_overlay_top_btn.setText("Toggle: Still Image on Top")
            print("DEBUG: Still image is now on top")
            print(f"DEBUG: Still image label visible: {self.still_image_label.isVisible()}")
            print(f"DEBUG: Still image label has pixmap: {self.still_image_label.pixmap() is not None}")
            if self.still_image_label.pixmap():
                print(f"DEBUG: Still image label pixmap size: {self.still_image_label.pixmap().size()}")
            print(f"DEBUG: Still image label geometry: {self.still_image_label.geometry()}")
            print(f"DEBUG: Still image label size: {self.still_image_label.size()}")
            print(f"DEBUG: Still image label parent: {self.still_image_label.parent()}")
            print(f"DEBUG: Still image label isEnabled: {self.still_image_label.isEnabled()}")
            print(f"DEBUG: Still image label updatesEnabled: {self.still_image_label.updatesEnabled()}")
            
            # List all children of video_container to see stacking order
            if video_container:
                children = video_container.findChildren(QWidget)
                print(f"DEBUG: video_container children: {[type(c).__name__ for c in children]}")
                for child in children:
                    print(f"DEBUG:   - {type(child).__name__}: visible={child.isVisible()}, geometry={child.geometry()}")
        
        # Force updates
        video_container = self.still_image_label.parent()
        if video_container:
            video_container.setVisible(True)
            video_container.show()
            video_container.update()
            video_container.repaint()
        
        self.still_image_label.update()
        self.still_image_label.repaint()
        self.overlay_view.update()
        self.overlay_view.repaint()
        
        # Process events to ensure changes are visible
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()
        
        # Additional forced update after processing events
        if not checked:  # If still image is on top
            self.still_image_label.update()
            self.still_image_label.repaint()
            if video_container:
                video_container.update()
                video_container.repaint()
            QApplication.processEvents()
    
    def on_playback_state_changed(self, state):
        """Handle playback state changes."""
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_btn.setEnabled(False)
            self.pause_btn.setEnabled(True)
            self.stop_btn.setEnabled(True)
        elif state == QMediaPlayer.PlaybackState.PausedState:
            self.play_btn.setEnabled(True)
            self.pause_btn.setEnabled(True)
            self.stop_btn.setEnabled(True)
        elif state == QMediaPlayer.PlaybackState.StoppedState:
            self.play_btn.setEnabled(True)
            self.pause_btn.setEnabled(False)
            self.stop_btn.setEnabled(False)
    
    def capture_still_image(self):
        """Capture the current video frame as a still image and display it with overlay."""
        if not self.current_video_path or self.media_player.source().isEmpty():
            QMessageBox.warning(self, "No Video", "Please load a video first!")
            return
        
        # Pause video to capture current frame (don't auto-play)
        was_playing = self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        was_paused = self.media_player.playbackState() == QMediaPlayer.PlaybackState.PausedState
        
        # If playing, pause it first
        if was_playing:
            self.media_player.pause()
            # Give it a moment to pause and render the frame
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()
            from PySide6.QtCore import QTimer
            QTimer.singleShot(100, lambda: self._do_capture(was_playing, was_paused))
        else:
            # Already paused or stopped, capture immediately
            self._do_capture(was_playing, was_paused)
    
    def _do_capture(self, was_playing: bool, was_paused: bool):
        """Actually perform the frame capture.
        
        Args:
            was_playing: Whether video was playing before capture
            was_paused: Whether video was paused before capture
        """
        # Get the video widget's current frame
        # Note: QVideoWidget doesn't have a direct way to capture frames
        # We'll need to use the video widget's grab() method
        try:
            # CRITICAL: Ensure video widget is visible and has rendered before grabbing
            self.video_widget.setVisible(True)
            self.video_widget.show()
            self.video_widget.raise_()
            self.video_widget.update()
            self.video_widget.repaint()
            from PySide6.QtWidgets import QApplication
            # Process events multiple times to ensure rendering
            for _ in range(5):
                QApplication.processEvents()
            
            # Try multiple times - sometimes first grab is blank
            pixmap = None
            for attempt in range(3):
                pixmap = self.video_widget.grab()
                if pixmap and not pixmap.isNull():
                    # Check if it's not all white/blank
                    image = pixmap.toImage()
                    if not image.isNull():
                        # Sample a few pixels to see if it's not all white
                        sample_x = image.width() // 2
                        sample_y = image.height() // 2
                        pixel = image.pixel(sample_x, sample_y)
                        color = QColor(pixel)
                        # If not white (or very close to white), we have content
                        if color.red() < 250 or color.green() < 250 or color.blue() < 250:
                            print(f"DEBUG: Successfully grabbed frame on attempt {attempt + 1}")
                            break
                QApplication.processEvents()
                from PySide6.QtCore import QThread
                QThread.msleep(50)  # Wait 50ms between attempts
            
            print(f"DEBUG: Grabbed pixmap - isNull: {pixmap.isNull() if pixmap else 'None'}, size: {pixmap.size() if pixmap else 'None'}")
            
            # Verify pixmap has actual content
            if pixmap and not pixmap.isNull():
                # Convert to QImage to verify it has content
                image = pixmap.toImage()
                print(f"DEBUG: Converted to QImage - isNull: {image.isNull()}, size: {image.size()}, format: {image.format()}")
                
                # Check if image has any non-transparent pixels
                if not image.isNull() and image.size().width() > 0 and image.size().height() > 0:
                    # Check if image has actual pixel data (not all white/transparent/black)
                    has_content = False
                    is_all_white = True
                    sample_pixels = 100  # Sample some pixels to check for content
                    step_x = max(1, image.width() // 10)
                    step_y = max(1, image.height() // 10)
                    for y in range(0, image.height(), step_y):
                        for x in range(0, image.width(), step_x):
                            pixel = image.pixel(x, y)
                            color = QColor(pixel)
                            # Check if pixel is not fully transparent
                            if color.alpha() > 0:
                                has_content = True
                                # Check if it's not white (or very close to white)
                                if color.red() < 250 or color.green() < 250 or color.blue() < 250:
                                    is_all_white = False
                                    break
                        if has_content and not is_all_white:
                            break
                    
                    print(f"DEBUG: Image has content: {has_content}, is_all_white: {is_all_white}")
                    
                    # If image is all white, it's likely a blank capture
                    if is_all_white and has_content:
                        print("DEBUG: WARNING - Captured image appears to be all white (blank frame)")
                        QMessageBox.warning(self, "Capture Failed", 
                                          "Captured frame appears to be blank (all white).\n"
                                          "Please ensure the video is playing and has rendered, then try capturing again.")
                        return
                    
                    if has_content:
                        # Convert back to pixmap
                        self.still_image_pixmap = QPixmap.fromImage(image)
                        # Scale to 1080x720 if needed
                        if self.still_image_pixmap.width() != 1080 or self.still_image_pixmap.height() != 720:
                            self.still_image_pixmap = self.still_image_pixmap.scaled(1080, 720, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                        print(f"DEBUG: Final pixmap - isNull: {self.still_image_pixmap.isNull()}, size: {self.still_image_pixmap.size()}")
                        
                        # Save PNG file
                        if self.current_game_id:
                            # Create still_images directory if it doesn't exist
                            still_images_dir = Path("still_images")
                            still_images_dir.mkdir(exist_ok=True)
                            
                            # Save PNG file
                            png_path = still_images_dir / f"game_{self.current_game_id}_still.png"
                            if self.still_image_pixmap.save(str(png_path), "PNG"):
                                # Update database with PNG path
                                self.db.update_game_still_image_path(self.current_game_id, str(png_path))
                                print(f"DEBUG: Saved still image to {png_path}")
                                QMessageBox.information(self, "Image Saved", f"Still image saved to:\n{png_path}")
                            else:
                                print(f"DEBUG: ERROR - Failed to save PNG to {png_path}")
                                QMessageBox.warning(self, "Save Failed", f"Failed to save PNG to:\n{png_path}")
                        
                        # Display the still image (only reached if pixmap is valid)
                        print(f"DEBUG: Setting pixmap, size: {self.still_image_pixmap.size()}")
                        self.still_image_label.setPixmap(self.still_image_pixmap)
                    else:
                        print("DEBUG: ERROR - Grabbed image appears to be empty (all transparent/black)!")
                        QMessageBox.warning(self, "Capture Failed", "Could not capture video frame. The video may not be loaded or rendered yet. Try playing the video first.")
                        return
                else:
                    print("DEBUG: ERROR - Grabbed image is null or has zero size!")
                    QMessageBox.warning(self, "Capture Failed", "Could not capture video frame. The video may not be loaded or rendered yet.")
                    return
            else:
                print("DEBUG: ERROR - Grabbed pixmap is null!")
                QMessageBox.warning(self, "Capture Failed", "Could not capture video frame. The video may not be loaded or rendered yet.")
                return
            
            # Continue with displaying the still image (only reached if pixmap is valid and has content)
            # CRITICAL: Hide video widget first, then show still image
            self.video_widget.setVisible(False)
            self.video_widget.hide()
            
            # CRITICAL: Get parent container first
            video_container = self.still_image_label.parent()
            print(f"DEBUG: video_container: {video_container}")
            print(f"DEBUG: video_container visible: {video_container.isVisible() if video_container else 'N/A'}")
            print(f"DEBUG: video_container geometry: {video_container.geometry() if video_container else 'N/A'}")
            
            # CRITICAL: Hide overlay first, show still image, then show overlay
            self.overlay_view.setVisible(False)
            self.overlay_view.hide()
            
            # Show still image and ensure it's painted
            print(f"DEBUG: Before showing still image - label visible: {self.still_image_label.isVisible()}")
            print(f"DEBUG: Before showing still image - label geometry: {self.still_image_label.geometry()}")
            print(f"DEBUG: Before showing still image - label parent: {self.still_image_label.parent()}")
            print(f"DEBUG: Before showing still image - pixmap valid: {self.still_image_pixmap is not None and not self.still_image_pixmap.isNull()}")
            
            # CRITICAL: Ensure still image is set and visible BEFORE overlay
            self.still_image_label.setPixmap(self.still_image_pixmap)
            self.still_image_label.setVisible(True)
            self.still_image_label.show()
            self.still_image_label.raise_()  # Raise it to top temporarily
            
            # Force immediate paint of still image - CRITICAL: Process events to ensure paint happens
            if video_container:
                video_container.setVisible(True)
                video_container.show()
                video_container.raise_()  # Raise container too
                video_container.update()
                video_container.repaint()
            self.still_image_label.update()
            self.still_image_label.repaint()
            
            # CRITICAL: Process events to ensure still image is painted
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()
            
            print(f"DEBUG: After showing still image - label visible: {self.still_image_label.isVisible()}")
            print(f"DEBUG: After showing still image - label geometry: {self.still_image_label.geometry()}")
            print(f"DEBUG: After showing still image - label has pixmap: {self.still_image_label.pixmap() is not None}")
            
            # Now show overlay on top of still image - but keep still image visible
            self.still_image_label.lower()  # Put still image below overlay
            self.overlay_view.setVisible(True)
            self.overlay_view.show()
            self.overlay_view.raise_()  # Put overlay on top
            
            # CRITICAL: Process events again after overlay is shown
            QApplication.processEvents()
            
            # Force updates - CRITICAL: Update parent container too
            if video_container:
                video_container.update()
                video_container.repaint()
            
            self.still_image_label.update()
            self.still_image_label.repaint()
            self.overlay_view.update()
            self.overlay_view.repaint()
            self.overlay_view.viewport().update()
            self.overlay_view.viewport().repaint()
            
            print(f"DEBUG: Final state - still image visible: {self.still_image_label.isVisible()}")
            print(f"DEBUG: Final state - overlay visible: {self.overlay_view.isVisible()}")
            print(f"DEBUG: Final state - video widget visible: {self.video_widget.isVisible()}")
            
            # CRITICAL: Force still image to be painted again after overlay is raised
            # Use QTimer to ensure still image is painted after overlay
            from PySide6.QtCore import QTimer
            QTimer.singleShot(50, lambda: self._ensure_still_image_visible())
            
            # Mark that still image is captured
            self._still_image_captured = True
            
            # Enable boundary buttons - CRITICAL: must enable set_boundaries_btn
            self.set_boundaries_btn.setEnabled(True)
            self.back_to_video_btn.setEnabled(True)
            
            print(f"DEBUG: Still image captured, set_boundaries_btn enabled: {self.set_boundaries_btn.isEnabled()}")
            print(f"DEBUG: Still image label visible: {self.still_image_label.isVisible()}")
            print(f"DEBUG: Still image label has pixmap: {self.still_image_label.pixmap() is not None}")
            if self.still_image_label.pixmap():
                print(f"DEBUG: Still image pixmap size: {self.still_image_label.pixmap().size()}")
            print(f"DEBUG: Video widget visible: {self.video_widget.isVisible()}")
            print(f"DEBUG: Overlay view visible: {self.overlay_view.isVisible()}")
            print(f"DEBUG: Still image label geometry: {self.still_image_label.geometry()}")
            print(f"DEBUG: Video widget geometry: {self.video_widget.geometry()}")
            print(f"DEBUG: Overlay view geometry: {self.overlay_view.geometry()}")
            print(f"DEBUG: Overlay view viewport background: {self.overlay_view.viewport().styleSheet()}")
            
            # Redraw overlay
            self.draw_court_overlay()
            
            QMessageBox.information(self, "Image Captured", 
                                   "Still image captured! You can now set/modify court boundaries on this image.")
        except Exception as e:
            QMessageBox.critical(self, "Capture Error", f"Error capturing still image:\n{str(e)}")
        
        # Don't auto-resume playback - let user control it
        # if was_playing:
        #     self.media_player.play()
    
    def on_media_error(self, error, error_string):
        """Handle media player errors."""
        QMessageBox.critical(
            self,
            "Media Error",
            f"Error playing video:\n{error_string}\n\nError code: {error}"
        )
    
    def _ensure_still_image_visible(self):
        """Ensure still image is visible and painted."""
        if hasattr(self, 'still_image_label') and self.still_image_pixmap:
            # Force still image to be visible and painted
            self.still_image_label.setPixmap(self.still_image_pixmap)
            self.still_image_label.setVisible(True)
            self.still_image_label.show()
            self.still_image_label.lower()  # Ensure it's below overlay
            self.still_image_label.update()
            self.still_image_label.repaint()
            
            # Force parent container to update
            video_container = self.still_image_label.parent()
            print(f"DEBUG: _ensure_still_image_visible - video_container: {video_container}")
            if video_container:
                video_container.setVisible(True)
                video_container.show()
                video_container.update()
                video_container.repaint()
            
            print(f"DEBUG: _ensure_still_image_visible - still image label visible: {self.still_image_label.isVisible()}")
            print(f"DEBUG: _ensure_still_image_visible - still image has pixmap: {self.still_image_label.pixmap() is not None}")
            print(f"DEBUG: _ensure_still_image_visible - still image label geometry: {self.still_image_label.geometry()}")
            print(f"DEBUG: _ensure_still_image_visible - still image label parent: {self.still_image_label.parent()}")
            print(f"DEBUG: _ensure_still_image_visible - still image label styleSheet: {self.still_image_label.styleSheet()}")
    
    def showEvent(self, event):
        """Handle window show event - ensure overlay is on top."""
        super().showEvent(event)
        # Ensure overlay is raised after window is shown
        if hasattr(self, 'overlay_widget') and hasattr(self, 'video_widget'):
            # Use QTimer to ensure this happens after window is fully shown
            from PySide6.QtCore import QTimer
            QTimer.singleShot(100, lambda: self._raise_overlay())
    
    def _ensure_still_image_visible(self):
        """Ensure still image is visible and painted."""
        if hasattr(self, 'still_image_label') and self.still_image_pixmap:
            # Force still image to be visible and painted
            self.still_image_label.setPixmap(self.still_image_pixmap)
            self.still_image_label.setVisible(True)
            self.still_image_label.show()
            self.still_image_label.lower()  # Ensure it's below overlay
            self.still_image_label.update()
            self.still_image_label.repaint()
            
            # Force parent container to update
            video_container = self.still_image_label.parent()
            if video_container:
                video_container.update()
                video_container.repaint()
            
            print(f"DEBUG: _ensure_still_image_visible - still image label visible: {self.still_image_label.isVisible()}")
            print(f"DEBUG: _ensure_still_image_visible - still image has pixmap: {self.still_image_label.pixmap() is not None}")
    
    def _raise_overlay(self):
        """Raise overlay view after a short delay."""
        if hasattr(self, 'overlay_view') and hasattr(self, 'video_widget'):
            # Ensure video widget is lower
            self.video_widget.lower()
            # Ensure overlay is visible and on top
            self.overlay_view.setVisible(True)
            self.overlay_view.show()
            self.overlay_view.raise_()
            self.overlay_view.activateWindow()
            # Force update
            self.overlay_view.update()
            self.overlay_view.viewport().update()
            self.overlay_view.repaint()
            # Also try updating the scene
            self.overlay_scene.update()
            # Redraw the scene
            self.draw_court_overlay()
            print("DEBUG: _raise_overlay - overlay view raised and shown")
            print(f"DEBUG: Overlay view visible: {self.overlay_view.isVisible()}")
            print(f"DEBUG: Overlay view geometry: {self.overlay_view.geometry()}")
    
    def closeEvent(self, event):
        """Handle window close event."""
        self.media_player.stop()
        if self.db.conn:
            self.db.close()
        event.accept()


if __name__ == "__main__":
    # Test the video window standalone
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # Initialize database
    db = VideoStatsDB()
    db.initialize_database()
    db.connect()
    
    # Create and show window
    window = VideoWindow(db)
    window.show()
    
    sys.exit(app.exec())

