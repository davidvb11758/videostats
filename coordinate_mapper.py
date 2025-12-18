"""
Coordinate Mapper - Maps pixel coordinates to logical coordinates using perspective correction.
Uses OpenCV homography for accurate perspective transformation.
"""

import numpy as np
import cv2
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGraphicsView, QGraphicsScene,
    QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsTextItem, QApplication, QPushButton,
    QFileDialog, QSlider, QComboBox, QMessageBox, QDialog, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt, QPointF, QRectF, Signal, QUrl, QTimer, QPoint
from PySide6.QtGui import QPen, QBrush, QColor, QFont, QPainter
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
from lineup_manager import LineupManager


class CoordinateMapper(QMainWindow):
    """Coordinate mapper widget that maps pixel coordinates to logical coordinates."""
    
    # Signal emitted when a point is mapped to logical coordinates
    # Parameters: (logical_x, logical_y, pixel_x, pixel_y, timecode_ms)
    coordinate_mapped = Signal(float, float, float, float, int)
    
    # Signal emitted when a double-click is detected (for DOWN contact)
    # Parameters: (logical_x, logical_y, pixel_x, pixel_y, timecode_ms)
    double_click_mapped = Signal(float, float, float, float, int)
    
    # Signal emitted when a point is awarded
    # Parameters: (point_winner_id)
    point_awarded = Signal(int)
    
    def __init__(self, parent=None, db=None, game_id=None):
        super().__init__(parent)
        self.setWindowTitle("Coordinate Mapper")
        
        # Store database and game_id for saving court boundaries
        self.db = db
        self.game_id = game_id
        
        # Team IDs and score tracking
        self.team_us_id = None
        self.team_them_id = None
        self.score_us = 0
        self.score_them = 0
        self.current_rally_number = 0
        
        # Load team IDs and score if game_id is available
        if self.db and self.game_id:
            self._load_team_ids()
            self._load_score()
        
        # Initialize LineupManager for substitutions and libero actions
        self.lineup_manager = LineupManager(self.db) if self.db else None
        
        # Track libero replacements: position -> replaced_player_id
        self.libero_replacements = {}  # {position: replaced_player_id}
        
        # Fixed dimensions of the logical plane
        self.plane_width = 300
        self.plane_height = 600
        
        # Canvas/view dimensions
        self.canvas_width = 1500
        self.canvas_height = 600
        
        # Storage for clicks
        self.corner_points = []  # Will store 4 corners + 6 horizontal line points (10 total)
        # Order: [BL, BR, TR, TL, ML(300), MR(300), Y200L(200), Y200R(200), Y400L(400), Y400R(400)]
        self.mapped_points = []  # Will store subsequent points
        
        # Graphics items for drawing
        self.graphics_items = []  # Store all graphics items for easy clearing
        self.point_ellipses = []  # Store ellipse items for the 10 corner/midpoints
        
        # OpenCV homography matrix for perspective transformation
        self.homography_matrix = None
        
        # Interaction modes
        self.mode = 'normal'  # 'normal', 'setup', 'modify'
        self.dragging_point_index = None  # Index of point being dragged
        self.dragging_line = None  # (point1_idx, point2_idx) if dragging a line
        self.dragging_line_point = None  # Which corner point to move when dragging line
        self.drag_start_pos = None
        self.drag_start_corners = None  # Store initial corner positions when dragging line
        self.drag_line_click_fraction = None  # Fraction along line where user clicked (0 to 1)
        
        # Video playback
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        self.video_item = None  # Will be created when video is loaded
        self.video_loaded = False
        self.video_file_path = None  # Store the video file path
        
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
        
        self.load_video_btn = QPushButton("Load Video")
        self.load_video_btn.setFont(QFont('Arial', 12))
        self.load_video_btn.clicked.connect(self.load_video)
        button_layout.addWidget(self.load_video_btn)
        
        self.set_boundaries_btn = QPushButton("Set Court Boundaries")
        self.set_boundaries_btn.setFont(QFont('Arial', 12))
        self.set_boundaries_btn.clicked.connect(self.start_set_boundaries)
        button_layout.addWidget(self.set_boundaries_btn)
        
        self.modify_court_btn = QPushButton("Modify Court")
        self.modify_court_btn.setFont(QFont('Arial', 12))
        self.modify_court_btn.clicked.connect(self.start_modify_court)
        self.modify_court_btn.setEnabled(False)  # Disabled until court is set
        button_layout.addWidget(self.modify_court_btn)
        
        self.store_boundaries_btn = QPushButton("Store Court Boundaries")
        self.store_boundaries_btn.setFont(QFont('Arial', 12))
        self.store_boundaries_btn.clicked.connect(self.store_court_boundaries)
        self.store_boundaries_btn.setEnabled(False)  # Disabled until court is set
        button_layout.addWidget(self.store_boundaries_btn)
        
        self.clear_dots_btn = QPushButton("Clear Dots")
        self.clear_dots_btn.setFont(QFont('Arial', 12))
        self.clear_dots_btn.clicked.connect(self.clear_green_dots)
        self.clear_dots_btn.setEnabled(True)  # Always enabled
        button_layout.addWidget(self.clear_dots_btn)
        
        # Score display and buttons
        button_layout.addSpacing(20)  # Add some space before score section
        
        self.score_label = QLabel("Score: 0 - 0")
        self.score_label.setFont(QFont('Arial', 12, QFont.Weight.Bold))
        self.score_label.setStyleSheet("color: blue; padding: 5px;")
        button_layout.addWidget(self.score_label)
        
        self.award_point_us_btn = QPushButton("+1 Us")
        self.award_point_us_btn.setFont(QFont('Arial', 12))
        self.award_point_us_btn.clicked.connect(lambda: self.award_point('us'))
        self.award_point_us_btn.setEnabled(self.db is not None and self.game_id is not None)
        button_layout.addWidget(self.award_point_us_btn)
        
        self.award_point_them_btn = QPushButton("+1 Them")
        self.award_point_them_btn.setFont(QFont('Arial', 12))
        self.award_point_them_btn.clicked.connect(lambda: self.award_point('them'))
        self.award_point_them_btn.setEnabled(self.db is not None and self.game_id is not None)
        button_layout.addWidget(self.award_point_them_btn)
        
        # Substitution and Libero buttons
        button_layout.addSpacing(20)  # Add some space before substitution section
        
        self.substitution_btn = QPushButton("Substitution")
        self.substitution_btn.setFont(QFont('Arial', 12))
        self.substitution_btn.clicked.connect(self.show_substitution_dialog)
        self.substitution_btn.setEnabled(self.db is not None and self.game_id is not None)
        button_layout.addWidget(self.substitution_btn)
        
        self.libero_in_btn = QPushButton("Libero IN")
        self.libero_in_btn.setFont(QFont('Arial', 12))
        self.libero_in_btn.clicked.connect(self.show_libero_in_dialog)
        self.libero_in_btn.setEnabled(self.db is not None and self.game_id is not None)
        button_layout.addWidget(self.libero_in_btn)
        
        self.libero_out_btn = QPushButton("Libero OUT")
        self.libero_out_btn.setFont(QFont('Arial', 12))
        self.libero_out_btn.clicked.connect(self.show_libero_out_dialog)
        self.libero_out_btn.setEnabled(self.db is not None and self.game_id is not None)
        button_layout.addWidget(self.libero_out_btn)
        
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
        # Remove maximum size constraint to allow scrolling
        self.view.setMaximumSize(16777215, 16777215)  # Qt's maximum size value
        # Enable scrolling
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        layout.addWidget(self.view)
        
        # Coordinate display label
        self.coord_label = QLabel("")
        self.coord_label.setFont(QFont('Arial', 10))
        self.coord_label.setStyleSheet("color: blue;")
        layout.addWidget(self.coord_label)
        
        # Video playback controls
        video_controls_layout = QHBoxLayout()
        
        self.play_pause_btn = QPushButton("Play")
        self.play_pause_btn.setFont(QFont('Arial', 10))
        self.play_pause_btn.clicked.connect(self.toggle_play_pause)
        self.play_pause_btn.setEnabled(False)
        video_controls_layout.addWidget(self.play_pause_btn)
        
        self.video_slider = QSlider(Qt.Orientation.Horizontal)
        self.video_slider.setEnabled(False)
        self.video_slider.sliderMoved.connect(self.seek_video)
        video_controls_layout.addWidget(self.video_slider)
        
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setFont(QFont('Arial', 10))
        video_controls_layout.addWidget(self.time_label)
        
        # Playback speed control
        speed_label = QLabel("Speed:")
        speed_label.setFont(QFont('Arial', 10))
        video_controls_layout.addWidget(speed_label)
        
        self.speed_combo = QComboBox()
        self.speed_combo.setFont(QFont('Arial', 10))
        self.speed_combo.addItems(["0.33x", "0.5x", "0.75x", "0.8x", "0.9x", "1.0x"])
        self.speed_combo.setCurrentText("1.0x")
        self.speed_combo.currentTextChanged.connect(self.change_playback_speed)
        self.speed_combo.setEnabled(False)
        video_controls_layout.addWidget(self.speed_combo)
        
        layout.addLayout(video_controls_layout)
        
        # Connect media player signals
        self.media_player.positionChanged.connect(self.update_position)
        self.media_player.durationChanged.connect(self.update_duration)
        self.media_player.mediaStatusChanged.connect(self.on_media_status_changed)
        
        # Install event filter on the view to capture mouse clicks and key presses
        self.view.viewport().installEventFilter(self)
        self.view.installEventFilter(self)
        self.installEventFilter(self)
        
        # Update score display after UI is set up
        self._update_score_display()
    
    def _load_team_ids(self):
        """Load team_us_id and team_them_id from the game."""
        if not self.db or not self.game_id:
            return
        
        try:
            if not self.db.conn:
                self.db.connect()
            cursor = self.db.conn.cursor()
            cursor.execute(
                "SELECT team_us_id, team_them_id FROM games WHERE game_id = ?",
                (self.game_id,)
            )
            result = cursor.fetchone()
            if result:
                self.team_us_id, self.team_them_id = result
        except Exception as e:
            print(f"Warning: Failed to load team IDs: {e}")
    
    def _load_score(self):
        """Load current score from completed rallies."""
        if not self.db or not self.game_id or not self.team_us_id or not self.team_them_id:
            return
        
        try:
            if not self.db.conn:
                self.db.connect()
            
            cursor = self.db.conn.cursor()
            cursor.execute(
                """SELECT point_winner_id, COUNT(*) 
                   FROM rallies 
                   WHERE game_id = ? AND point_winner_id IS NOT NULL
                   GROUP BY point_winner_id""",
                (self.game_id,)
            )
            results = cursor.fetchall()
            
            self.score_us = 0
            self.score_them = 0
            
            for point_winner_id, count in results:
                if point_winner_id == self.team_us_id:
                    self.score_us = count
                elif point_winner_id == self.team_them_id:
                    self.score_them = count
            
            # Get current rally number
            cursor.execute(
                "SELECT MAX(rally_number) FROM rallies WHERE game_id = ?",
                (self.game_id,)
            )
            result = cursor.fetchone()
            if result and result[0]:
                self.current_rally_number = result[0]
            else:
                self.current_rally_number = 0
        except Exception as e:
            print(f"Warning: Failed to load score: {e}")
    
    def _update_score_display(self):
        """Update the score display label."""
        if not hasattr(self, 'score_label'):
            return
        
        if not self.team_us_id or not self.team_them_id:
            self.score_label.setText("Score: 0 - 0")
            return
        
        try:
            if not self.db.conn:
                self.db.connect()
            
            # Get team names
            cursor = self.db.conn.cursor()
            cursor.execute("SELECT name FROM teams WHERE team_id = ?", (self.team_us_id,))
            result = cursor.fetchone()
            team_us_name = result[0] if result else "Us"
            cursor.execute("SELECT name FROM teams WHERE team_id = ?", (self.team_them_id,))
            result = cursor.fetchone()
            team_them_name = result[0] if result else "Them"
            
            self.score_label.setText(f"Score: {team_us_name} {self.score_us} - {self.score_them} {team_them_name}")
        except Exception as e:
            print(f"Warning: Failed to update score display: {e}")
            self.score_label.setText(f"Score: {self.score_us} - {self.score_them}")
    
    def award_point(self, team: str):
        """Award a point to team_us or team_them by updating the most recent rally.
        
        Does not create a new rally. Instead, finds the most recent rally (the one that
        just ended or was created when "down" was clicked) and updates it with the point_winner_id.
        
        Args:
            team: 'us' to award point to team_us, 'them' to award point to team_them
        """
        if not self.db or not self.game_id:
            self.status_label.setText("Error: No database connection or game selected!")
            return
        
        if team == 'us' and not self.team_us_id:
            self.status_label.setText("Error: team_us_id not loaded!")
            return
        elif team == 'them' and not self.team_them_id:
            self.status_label.setText("Error: team_them_id not loaded!")
            return
        
        try:
            if not self.db.conn:
                self.db.connect()
            
            # Determine point winner
            point_winner_id = self.team_us_id if team == 'us' else self.team_them_id
            
            # Determine serving team (the team that won the point serves next)
            serving_team_id = point_winner_id
            
            # Find the most recent rally (the one that just ended or was created when "down" was clicked)
            cursor = self.db.conn.cursor()
            cursor.execute("""
                SELECT rally_id, rally_number, serving_team_id
                FROM rallies 
                WHERE game_id = ?
                ORDER BY rally_id DESC
                LIMIT 1
            """, (self.game_id,))
            result = cursor.fetchone()
            
            if not result:
                self.status_label.setText("Error: No rally found to update!")
                return
            
            rally_id, rally_number, prev_serving_team_id = result
            
            # Check if team_them served in this rally to determine if rotation is needed
            team_them_served_previous = False
            if prev_serving_team_id == self.team_them_id:
                team_them_served_previous = True
            
            # Update the rally with the point winner (don't create a new one)
            # Use current time for rally_end_time since we don't have the "down" click timecode here
            from datetime import datetime
            self.db.end_rally(rally_id, point_winner_id, datetime.now())
            
            # Update local score
            if team == 'us':
                self.score_us += 1
            else:
                self.score_them += 1
            
            # Update display
            self._update_score_display()
            
            # Emit signal to notify data entry window (include whether team_them served in previous rally)
            # This allows the handler to determine if rotation is needed
            self.point_awarded.emit(point_winner_id)
            
            # Update status
            team_name = "Us" if team == 'us' else "Them"
            self.status_label.setText(f"Point awarded to {team_name}! Score: {self.score_us} - {self.score_them}")
            
            print(f"DEBUG: Point awarded to {team_name} (team_id={point_winner_id}). New score: {self.score_us} - {self.score_them}")
            
        except Exception as e:
            error_msg = f"Error awarding point: {str(e)}"
            self.status_label.setText(error_msg)
            print(f"ERROR: {error_msg}")
    
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
        self.store_boundaries_btn.setEnabled(False)
    
    def start_modify_court(self):
        """Start the process of modifying court boundaries."""
        if len(self.corner_points) < 10:
            return
        
        # Enter modify mode
        self.mode = 'modify'
        self.status_label.setText("Click and drag any point to modify. Click 'Set Court Boundaries' to exit modify mode.")
        
        # Make the points visually distinct (larger and different color)
        for i, ellipse in enumerate(self.point_ellipses):
            ellipse.setBrush(QBrush(QColor(255, 128, 0)))  # Orange color
            ellipse.setCursor(Qt.CursorShape.PointingHandCursor)
    
    def load_video(self):
        """Load a video file via file dialog and display it in the scene."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Video File",
            "",
            "Video Files (*.mp4 *.avi *.mov *.mkv);;All Files (*)"
        )
        
        if file_path:
            self.load_video_from_path(file_path)
    
    def load_video_from_path(self, file_path: str):
        """Load a video file from the given path and display it in the scene.
        
        Args:
            file_path: Path to the video file to load
        """
        if not file_path:
            return
        
        import os
        if not os.path.exists(file_path):
            print(f"Warning: Video file not found: {file_path}")
            self.status_label.setText(f"Video file not found: {file_path}")
            return
        
        # Remove existing video item if present
        if self.video_item:
            self.scene.removeItem(self.video_item)
        
        # Create and add video item to scene
        self.video_item = QGraphicsVideoItem()
        # Initially set to canvas size, will be adjusted when video metadata is available
        self.video_item.setSize(QRectF(0, 0, self.canvas_width, self.canvas_height).size())
        self.scene.addItem(self.video_item)
        
        # Connect to nativeSizeChanged signal to adjust scene size when video size is known
        self.video_item.nativeSizeChanged.connect(self._adjust_scene_to_video_size)
        
        # Set video item to be behind other graphics
        self.video_item.setZValue(-1)
        
        # Set video output
        self.media_player.setVideoOutput(self.video_item)
        
        # Load the video
        self.media_player.setSource(QUrl.fromLocalFile(file_path))
        
        # Store the video file path
        self.video_file_path = file_path
        self.video_loaded = True
        
        # Enable controls when media is ready (will be enabled in on_media_status_changed)
        # Also enable immediately as fallback
        self.enable_video_controls()
        
        # Update status
        self.status_label.setText("Video loaded. Click 'Set Court Boundaries' to start defining the court.")
        print(f"DEBUG: Video loaded from: {file_path}")
    
    def enable_video_controls(self):
        """Enable video playback controls."""
        self.play_pause_btn.setEnabled(True)
        self.video_slider.setEnabled(True)
        self.speed_combo.setEnabled(True)
    
    def _adjust_scene_to_video_size(self):
        """Adjust scene and video item size to match actual video dimensions."""
        if not self.video_item:
            return
        
        # Get video size from the video item
        video_size = self.video_item.nativeSize()
        if video_size.isValid() and video_size.width() > 0 and video_size.height() > 0:
            # Use the actual video dimensions
            video_width = video_size.width()
            video_height = video_size.height()
            
            # Update video item size to match actual video dimensions
            self.video_item.setSize(QRectF(0, 0, video_width, video_height).size())
            
            # Update scene size to accommodate the full video
            # Use the larger of canvas dimensions or video dimensions
            scene_width = max(self.canvas_width, video_width)
            scene_height = max(self.canvas_height, video_height)
            self.scene.setSceneRect(0, 0, scene_width, scene_height)
            
            print(f"DEBUG: Video size: {video_width}x{video_height}, Scene size: {scene_width}x{scene_height}")
        else:
            # Fallback: if video size not available, ensure scene is at least canvas size
            self.scene.setSceneRect(0, 0, self.canvas_width, self.canvas_height)
    
    def on_media_status_changed(self, status):
        """Handle media status changes to enable controls when media is loaded."""
        from PySide6.QtMultimedia import QMediaPlayer
        if status == QMediaPlayer.MediaStatus.LoadedMedia or status == QMediaPlayer.MediaStatus.BufferedMedia:
            self.enable_video_controls()
            print(f"DEBUG: Media status changed to {status}, controls enabled")
            
            # Try to adjust scene and video item size to match actual video dimensions
            # This will also be called by nativeSizeChanged signal when size becomes available
            self._adjust_scene_to_video_size()
    
    def toggle_play_pause(self):
        """Toggle between play and pause."""
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
            self.play_pause_btn.setText("Play")
        else:
            self.media_player.play()
            self.play_pause_btn.setText("Pause")
    
    def keyPressEvent(self, event):
        """Handle key press events."""
        self.handle_key_press(event)
    
    def handle_key_press(self, event):
        """Handle key press - called from keyPressEvent and event filter."""
        if event.key() == Qt.Key.Key_Space:
            # Toggle play/pause on spacebar
            if self.video_loaded:
                self.toggle_play_pause()
            event.accept()
            return True
        elif event.key() == Qt.Key.Key_Right:
            # Fast-forward 5 seconds on right arrow (works when playing or paused)
            if self.video_loaded:
                current_pos = self.media_player.position()
                new_pos = current_pos + 5000  # 5 seconds in milliseconds
                duration = self.media_player.duration()
                if duration > 0 and new_pos > duration:
                    new_pos = duration
                self.media_player.setPosition(new_pos)
                print(f"DEBUG: Fast-forward from {current_pos}ms to {new_pos}ms")
            event.accept()
            return True
        elif event.key() == Qt.Key.Key_Left:
            # Rewind 5 seconds on left arrow (works when playing or paused)
            if self.video_loaded:
                current_pos = self.media_player.position()
                new_pos = max(0, current_pos - 5000)  # 5 seconds in milliseconds
                self.media_player.setPosition(new_pos)
                print(f"DEBUG: Rewind from {current_pos}ms to {new_pos}ms")
            event.accept()
            return True
        return False
    
    def seek_video(self, position):
        """Seek to a specific position in the video."""
        self.media_player.setPosition(position)
    
    def update_position(self, position):
        """Update the slider position as the video plays."""
        if not self.video_slider.isSliderDown():
            self.video_slider.setValue(position)
        
        # Update time label
        current_time = self.format_time(position)
        duration = self.media_player.duration()
        total_time = self.format_time(duration)
        self.time_label.setText(f"{current_time} / {total_time}")
    
    def update_duration(self, duration):
        """Update the slider range when video duration is known."""
        self.video_slider.setRange(0, duration)
    
    def format_time(self, ms):
        """Format milliseconds to MM:SS."""
        seconds = ms // 1000
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes:02d}:{seconds:02d}"
    
    def change_playback_speed(self, speed_text):
        """Change the playback speed of the video."""
        # Extract speed value from text (e.g., "0.5x" -> 0.5)
        speed_value = float(speed_text.replace('x', ''))
        self.media_player.setPlaybackRate(speed_value)
    
    def store_court_boundaries(self):
        """Store the court boundaries to the database and prepare for contact location clicks."""
        if len(self.corner_points) < 10:
            self.status_label.setText("Error: Court boundaries not fully defined!")
            return
        
        # Capture scroll bar values at the time boundaries are stored
        h_scroll_value = self.view.horizontalScrollBar().value()
        v_scroll_value = self.view.verticalScrollBar().value()
        
        # Also capture video item position (should be 0,0 but check to be sure)
        video_x = self.video_item.pos().x() if self.video_item else 0
        video_y = self.video_item.pos().y() if self.video_item else 0
        
        # Capture actual video dimensions and scene size
        video_width = self.video_item.nativeSize().width() if (self.video_item and self.video_item.nativeSize().isValid()) else 0
        video_height = self.video_item.nativeSize().height() if (self.video_item and self.video_item.nativeSize().isValid()) else 0
        scene_rect = self.scene.sceneRect()
        scene_width = scene_rect.width()
        scene_height = scene_rect.height()
        
        # Map corner_points indices to database field names
        # corner_points order: [BL, BR, TR, TL, ML, MR, Y200L, Y200R, Y400L, Y400R]
        # Database expects: corner_tl, corner_tr, corner_bl, corner_br, centerline_top, centerline_bottom
        # Note: Y200 and Y400 points will be stored in additional fields if database supports them
        court_points_dict = {
            'corner_bl': tuple(self.corner_points[0]),  # Bottom-left
            'corner_br': tuple(self.corner_points[1]),  # Bottom-right
            'corner_tr': tuple(self.corner_points[2]),  # Top-right
            'corner_tl': tuple(self.corner_points[3]),  # Top-left
            'centerline_bottom': tuple(self.corner_points[4]),  # Mid-left (left end of centerline)
            'centerline_top': tuple(self.corner_points[5]),  # Mid-right (right end of centerline)
            'y200_left': tuple(self.corner_points[6]),  # Y200L (left point of Y=200 line)
            'y200_right': tuple(self.corner_points[7]),  # Y200R (right point of Y=200 line)
            'y400_left': tuple(self.corner_points[8]),  # Y400L (left point of Y=400 line)
            'y400_right': tuple(self.corner_points[9]),  # Y400R (right point of Y=400 line)
            # Store scroll offsets
            'scroll_offset_x': h_scroll_value,
            'scroll_offset_y': v_scroll_value,
            'video_offset_x': video_x,
            'video_offset_y': video_y,
            # Store video and scene dimensions for proper scaling
            'video_width': video_width,
            'video_height': video_height,
            'scene_width': scene_width,
            'scene_height': scene_height
        }
        
        # Save to database if db and game_id are available
        if self.db and self.game_id:
            try:
                # Debug: Print the game_id being used
                print(f"DEBUG: Storing court boundaries for game_id = {self.game_id}")
                print(f"DEBUG: Scroll offsets - X: {h_scroll_value}, Y: {v_scroll_value}")
                print(f"DEBUG: Video offsets - X: {video_x}, Y: {video_y}")
                print(f"DEBUG: Video dimensions - W: {video_width}, H: {video_height}")
                print(f"DEBUG: Scene dimensions - W: {scene_width}, H: {scene_height}")
                # Save homography matrix along with court boundaries
                self.db.save_game_court_boundaries(self.game_id, court_points_dict, self.homography_matrix)
                
                # Save video file path if available
                if self.video_file_path:
                    try:
                        self.db.update_game_video_path(self.game_id, self.video_file_path)
                        print(f"DEBUG: Video file path stored: {self.video_file_path}")
                    except Exception as e:
                        print(f"Warning: Failed to save video file path: {e}")
                
                status_msg = f"Court boundaries and video path stored to database for game {self.game_id}! Click on contact locations to map coordinates."
            except Exception as e:
                status_msg = f"Error saving to database: {str(e)}"
                print(f"Database error: {e}")
        else:
            status_msg = "Court boundaries set (no database connection). Click on contact locations to map coordinates."
            if not self.db:
                print("Warning: No database connection available")
            if not self.game_id:
                print(f"Warning: No game_id available (current value: {self.game_id})")
        
        # Exit modify mode if active
        self.mode = 'normal'
        
        # Update status
        self.status_label.setText(status_msg)
        
        # Print for debugging
        print("Court boundaries stored:")
        labels = ['BL (0,0)', 'BR (300,0)', 'TR (300,600)', 'TL (0,600)', 'ML (0,300)', 'MR (300,300)',
                 'Y200L (0,200)', 'Y200R (300,200)', 'Y400L (0,400)', 'Y400R (300,400)']
        for i, (label, point) in enumerate(zip(labels, self.corner_points)):
            print(f"  {label}: [{point[0]:.2f}, {point[1]:.2f}]")
    
    def eventFilter(self, obj, event):
        """Handle mouse and key events on the graphics view."""
        # Handle key press events from any child widget
        if event.type() == event.Type.KeyPress:
            if self.handle_key_press(event):
                return True
        
        if obj == self.view.viewport():
            # Handle double-click for DOWN contact
            if event.type() == event.Type.MouseButtonDblClick:
                if event.button() == Qt.MouseButton.LeftButton:
                    # Get click position in scene coordinates
                    scene_pos = self.view.mapToScene(event.position().toPoint())
                    x = scene_pos.x()
                    y = scene_pos.y()
                    
                    # Only handle double-click when court is defined and in normal mode
                    if self.mode == 'normal' and len(self.corner_points) >= 10:
                        self.handle_double_click(x, y)
                        return True
            
            if event.type() == event.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    # Get click position in scene coordinates
                    scene_pos = self.view.mapToScene(event.position().toPoint())
                    x = scene_pos.x()
                    y = scene_pos.y()
                    
                    if self.mode == 'modify':
                        # Check if clicking on a point first
                        self.dragging_point_index = self.find_point_at_position(x, y)
                        if self.dragging_point_index is not None:
                            self.drag_start_pos = [x, y]
                            return True
                        
                        # If not on a point, check if clicking on a line
                        line_result = self.find_line_at_position(x, y)
                        if line_result is not None:
                            self.dragging_line = line_result
                            # Determine which corner point is nearest to click
                            p1_idx, p2_idx = line_result
                            p1 = np.array(self.corner_points[p1_idx])
                            p2 = np.array(self.corner_points[p2_idx])
                            dist1 = np.linalg.norm(np.array([x, y]) - p1)
                            dist2 = np.linalg.norm(np.array([x, y]) - p2)
                            self.dragging_line_point = p1_idx if dist1 < dist2 else p2_idx
                            
                            # Calculate the fraction along the line where user clicked
                            # Fixed point is the one we're not moving
                            fixed_idx = p2_idx if self.dragging_line_point == p1_idx else p1_idx
                            fixed_point = np.array(self.corner_points[fixed_idx])
                            moving_point = np.array(self.corner_points[self.dragging_line_point])
                            click_point = np.array([x, y])
                            
                            # Calculate distances
                            line_vec = moving_point - fixed_point
                            line_len = np.linalg.norm(line_vec)
                            
                            if line_len > 0.001:
                                line_unitvec = line_vec / line_len
                                click_vec = click_point - fixed_point
                                click_dist = np.dot(click_vec, line_unitvec)
                                # Fraction of the line where we clicked (0 = fixed point, 1 = moving point)
                                self.drag_line_click_fraction = click_dist / line_len
                            else:
                                self.drag_line_click_fraction = 0.5
                            
                            self.drag_start_pos = [x, y]
                            # Store initial positions of all corner points
                            self.drag_start_corners = [list(p) for p in self.corner_points]
                            return True
                    elif self.mode == 'setup' or (self.mode == 'normal' and len(self.corner_points) < 6):
                        self.on_click(x, y)
                        return True
                    elif self.mode == 'normal' and len(self.corner_points) >= 10:
                        self.on_click(x, y)
                        return True
            
            elif event.type() == event.Type.MouseMove:
                if self.mode == 'modify':
                    scene_pos = self.view.mapToScene(event.position().toPoint())
                    x = scene_pos.x()
                    y = scene_pos.y()
                    
                    if self.dragging_point_index is not None:
                        # Dragging a point directly
                        self.update_point_position(self.dragging_point_index, x, y)
                        return True
                    elif self.dragging_line is not None:
                        # Dragging a line - move the nearest corner point
                        self.update_line_drag(x, y)
                        return True
            
            elif event.type() == event.Type.MouseButtonRelease:
                if event.button() == Qt.MouseButton.LeftButton:
                    if self.mode == 'modify':
                        if self.dragging_point_index is not None or self.dragging_line is not None:
                            # Finish dragging
                            self.dragging_point_index = None
                            self.dragging_line = None
                            self.dragging_line_point = None
                            self.drag_start_pos = None
                            self.drag_start_corners = None
                            self.drag_line_click_fraction = None
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
    
    def find_line_at_position(self, x, y):
        """Find if there's a line near the given position. Returns (point1_idx, point2_idx) or None."""
        if len(self.corner_points) < 10:
            return None
        
        # Define all the lines as pairs of point indices
        lines = [
            (0, 1),  # bottom edge
            (1, 2),  # right edge
            (2, 3),  # top edge
            (3, 0),  # left edge
            (0, 4),  # bottom-left to mid-left
            (4, 3),  # mid-left to top-left
            (1, 5),  # bottom-right to mid-right
            (5, 2),  # mid-right to top-right
            (4, 5),  # centerline
            (0, 6),  # bottom-left to Y200L
            (6, 4),  # Y200L to mid-left
            (1, 7),  # bottom-right to Y200R
            (7, 5),  # Y200R to mid-right
            (6, 7),  # Y=200 line
            (4, 8),  # mid-left to Y400L
            (8, 3),  # Y400L to top-left
            (5, 9),  # mid-right to Y400R
            (9, 2),  # Y400R to top-right
            (8, 9),  # Y=400 line
        ]
        
        threshold = 15  # pixels - distance from line to be considered "on" it
        
        for p1_idx, p2_idx in lines:
            p1 = np.array(self.corner_points[p1_idx])
            p2 = np.array(self.corner_points[p2_idx])
            point = np.array([x, y])
            
            # Calculate distance from point to line segment
            line_vec = p2 - p1
            line_len = np.linalg.norm(line_vec)
            
            if line_len < 0.001:  # Degenerate line
                continue
            
            line_unitvec = line_vec / line_len
            
            # Project point onto line
            point_vec = point - p1
            proj_length = np.dot(point_vec, line_unitvec)
            
            # Check if projection is within the line segment
            if proj_length < 0 or proj_length > line_len:
                continue
            
            # Calculate perpendicular distance
            proj_point = p1 + proj_length * line_unitvec
            dist = np.linalg.norm(point - proj_point)
            
            if dist < threshold:
                return (p1_idx, p2_idx)
        
        return None
    
    def update_point_position(self, index, x, y):
        """Update the position of a corner point."""
        self.corner_points[index] = [x, y]
        # Recompute homography if we have all 10 points
        if len(self.corner_points) >= 10:
            self._compute_homography()
        self._redraw_plane()
    
    def update_line_drag(self, x, y):
        """Update the position of the nearest corner point when dragging a line.
        The mouse cursor maintains its relative position on the line."""
        if self.dragging_line is None or self.dragging_line_point is None:
            return
        
        if self.drag_start_corners is None or self.drag_line_click_fraction is None:
            return
        
        # Get the line endpoints
        p1_idx, p2_idx = self.dragging_line
        
        # Get the fixed point (the one we're not moving)
        fixed_idx = p1_idx if self.dragging_line_point == p2_idx else p2_idx
        fixed_point = np.array(self.drag_start_corners[fixed_idx])
        
        # Get initial position of the point we're moving
        moving_point_initial = np.array(self.drag_start_corners[self.dragging_line_point])
        
        # Calculate the original line direction
        line_vec = moving_point_initial - fixed_point
        line_len = np.linalg.norm(line_vec)
        
        if line_len < 0.001:
            return
        
        line_unitvec = line_vec / line_len
        
        # Project the current mouse position onto the line direction
        mouse_point = np.array([x, y])
        mouse_vec = mouse_point - fixed_point
        mouse_proj_dist = np.dot(mouse_vec, line_unitvec)
        
        # Calculate where the moving point should be to maintain the click fraction
        # If we clicked at fraction F of the line, and mouse is now at distance D from fixed point,
        # then the moving point should be at distance D/F from fixed point
        if abs(self.drag_line_click_fraction) > 0.01:  # Avoid division by zero
            new_line_length = mouse_proj_dist / self.drag_line_click_fraction
        else:
            # If clicked very close to fixed point, just use mouse projection
            new_line_length = mouse_proj_dist
        
        # Position the moving point
        new_point = fixed_point + new_line_length * line_unitvec
        
        # Update the corner point
        self.corner_points[self.dragging_line_point] = [new_point[0], new_point[1]]
        self._redraw_plane()
    
    def on_click(self, x, y):
        """Handle a click at the given scene coordinates."""
        if len(self.corner_points) < 10 and self.mode == 'setup':
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
            labels = ['BL (0,0)', 'BR (300,0)', 'TR (300,600)', 'TL (0,600)', 'ML (0,300)', 'MR (300,300)', 
                     'Y200L (0,200)', 'Y200R (300,200)', 'Y400L (0,400)', 'Y400R (300,400)']
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
                
                # Centerline - lighter color and 3x wider
                centerline_pen = QPen(QColor(255, 220, 180), 6)  # Lighter orange, 3x wider (2*3=6)
                centerline_pen.setStyle(Qt.PenStyle.DashLine)
                line3 = QGraphicsLineItem(
                    self.corner_points[4][0], self.corner_points[4][1],
                    self.corner_points[5][0], self.corner_points[5][1]
                )
                line3.setPen(centerline_pen)
                self.scene.addItem(line3)
                self.graphics_items.append(line3)
                self.status_label.setText("Click left point of Y=200 line (team_us side)")
            elif len(self.corner_points) == 7:
                # Draw Y=200 line (left point)
                pen = QPen(QColor(0, 255, 0), 2)  # Green for Y=200 line
                pen.setStyle(Qt.PenStyle.DashLine)
                line1 = QGraphicsLineItem(
                    self.corner_points[0][0], self.corner_points[0][1],
                    self.corner_points[6][0], self.corner_points[6][1]
                )
                line1.setPen(pen)
                self.scene.addItem(line1)
                self.graphics_items.append(line1)
                self.status_label.setText("Click right point of Y=200 line (team_us side)")
            elif len(self.corner_points) == 8:
                # Draw Y=200 line (right point) and complete the line
                pen = QPen(QColor(0, 255, 0), 2)  # Green for Y=200 line
                pen.setStyle(Qt.PenStyle.DashLine)
                line1 = QGraphicsLineItem(
                    self.corner_points[6][0], self.corner_points[6][1],
                    self.corner_points[7][0], self.corner_points[7][1]
                )
                line1.setPen(pen)
                self.scene.addItem(line1)
                self.graphics_items.append(line1)
                
                line2 = QGraphicsLineItem(
                    self.corner_points[1][0], self.corner_points[1][1],
                    self.corner_points[7][0], self.corner_points[7][1]
                )
                line2.setPen(pen)
                self.scene.addItem(line2)
                self.graphics_items.append(line2)
                self.status_label.setText("Click left point of Y=400 line (team_them side)")
            elif len(self.corner_points) == 9:
                # Draw Y=400 line (left point)
                pen = QPen(QColor(255, 0, 255), 2)  # Magenta for Y=400 line
                pen.setStyle(Qt.PenStyle.DashLine)
                line1 = QGraphicsLineItem(
                    self.corner_points[4][0], self.corner_points[4][1],
                    self.corner_points[8][0], self.corner_points[8][1]
                )
                line1.setPen(pen)
                self.scene.addItem(line1)
                self.graphics_items.append(line1)
                self.status_label.setText("Click right point of Y=400 line (team_them side)")
            elif len(self.corner_points) == 10:
                # Draw Y=400 line (right point) and complete the line
                pen = QPen(QColor(255, 0, 255), 2)  # Magenta for Y=400 line
                pen.setStyle(Qt.PenStyle.DashLine)
                line1 = QGraphicsLineItem(
                    self.corner_points[8][0], self.corner_points[8][1],
                    self.corner_points[9][0], self.corner_points[9][1]
                )
                line1.setPen(pen)
                self.scene.addItem(line1)
                self.graphics_items.append(line1)
                
                line2 = QGraphicsLineItem(
                    self.corner_points[5][0], self.corner_points[5][1],
                    self.corner_points[9][0], self.corner_points[9][1]
                )
                line2.setPen(pen)
                self.scene.addItem(line2)
                self.graphics_items.append(line2)
                self.status_label.setText("Plane defined! Click 'Store Court Boundaries' to save and start mapping.")
                
                # Enable modify and store buttons, change to normal mode
                self.modify_court_btn.setEnabled(True)
                self.store_boundaries_btn.setEnabled(True)
                self.mode = 'normal'
                
                # Compute homography matrix for perspective transformation
                self._compute_homography()
        elif self.mode == 'normal' and len(self.corner_points) >= 10:
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
                
                # Get current video timecode in milliseconds
                timecode_ms = self.media_player.position()
                
                # Emit signal with mapped coordinates and timecode
                self.coordinate_mapped.emit(logical_coords[0], logical_coords[1], x, y, timecode_ms)
    
    def position_popup_near_click(self, dialog: QDialog, pixel_x: float, pixel_y: float, offset_y: int = 10):
        """Position a popup dialog near the clicked location, ensuring it stays on screen.
        
        Args:
            dialog: The dialog to position
            pixel_x: X coordinate of the click in scene coordinates
            pixel_y: Y coordinate of the click in scene coordinates
            offset_y: Vertical offset above the click location (default: 10 pixels)
        """
        # Get the dialog size
        dialog.adjustSize()  # Ensure dialog has its final size
        dialog_width = dialog.width()
        dialog_height = dialog.height()
        
        # Convert scene coordinates to global screen coordinates
        # Convert scene coordinates to view coordinates
        scene_point = QPointF(pixel_x, pixel_y)
        view_point_f = self.view.mapFromScene(scene_point)
        # Convert QPointF to QPoint explicitly
        view_point = QPoint(int(view_point_f.x()), int(view_point_f.y()))
        # Convert view coordinates to global screen coordinates
        global_point = self.view.mapToGlobal(view_point)
        
        # Calculate initial position: 10 pixels above the click
        dialog_x = global_point.x()
        dialog_y = global_point.y() - dialog_height - offset_y
        
        # Get screen geometry to check boundaries
        screen = self.screen().availableGeometry()
        
        # Check if dialog goes off the left edge
        if dialog_x < screen.left():
            dialog_x = screen.left() + 5  # 5 pixels margin from left edge
        
        # Check if dialog goes off the right edge
        if dialog_x + dialog_width > screen.right():
            dialog_x = screen.right() - dialog_width - 5  # 5 pixels margin from right edge
        
        # Check if dialog goes off the top edge
        if dialog_y < screen.top():
            # If it goes off top, position it below the click instead
            dialog_y = global_point.y() + offset_y
            # But make sure it doesn't go off bottom either
            if dialog_y + dialog_height > screen.bottom():
                dialog_y = screen.bottom() - dialog_height - 5
        
        # Check if dialog goes off the bottom edge
        if dialog_y + dialog_height > screen.bottom():
            dialog_y = screen.bottom() - dialog_height - 5
        
        # Move the dialog to the calculated position
        dialog.move(int(dialog_x), int(dialog_y))
    
    def clear_green_dots(self):
        """Clear all green dots and coordinate text from the canvas."""
        # Remove all graphics items (dots and text) but keep corner points and homography
        for item in self.graphics_items:
            self.scene.removeItem(item)
        self.graphics_items.clear()
        
        # Clear mapped_points list (but keep corner_points for homography)
        self.mapped_points.clear()
        
        # Clear coordinate label
        self.coord_label.setText("")
        
        print("DEBUG: Cleared all green dots and coordinate text from canvas")
    
    # ========== Substitution and Libero Methods ==========
    
    def get_bench_players(self, team_id: int):
        """Get bench players (players in game_players but not in active_lineup).
        
        Args:
            team_id: The team ID to get bench players for
            
        Returns:
            List of (player_id, player_number, player_name) tuples
        """
        if not self.game_id:
            return []
        
        if not self.db or not self.db.conn:
            if self.db:
                self.db.connect()
            else:
                return []
        
        cursor = self.db.conn.cursor()
        
        # Get all players in game_players for this team
        cursor.execute("""
            SELECT p.player_id, 
                   COALESCE(p.jersey, p.player_number) as player_number,
                   p.name
            FROM players p
            INNER JOIN game_players gp ON p.player_id = gp.player_id
            WHERE gp.game_id = ? AND gp.team_id = ?
            ORDER BY CASE 
                WHEN CAST(COALESCE(p.jersey, p.player_number) AS INTEGER) IS NOT NULL 
                THEN CAST(COALESCE(p.jersey, p.player_number) AS INTEGER)
                ELSE 999
            END,
            COALESCE(p.jersey, p.player_number)
        """, (self.game_id, team_id))
        
        all_players = cursor.fetchall()
        
        # Get active players (those in active_lineup) for this specific game
        cursor.execute("""
            SELECT player_id
            FROM active_lineup
            WHERE game_id = ? AND team_id = ?
        """, (self.game_id, team_id))
        
        active_player_ids = {row[0] for row in cursor.fetchall()}
        
        # Filter to get bench players (not in active_lineup)
        bench_players = [(pid, pnum, pname) for pid, pnum, pname in all_players if pid not in active_player_ids]
        
        return bench_players
    
    def get_active_players_with_positions(self, team_id: int):
        """Get active players with their court positions.
        
        Args:
            team_id: The team ID to get active players for
            
        Returns:
            List of (player_id, player_number, player_name, position_number) tuples
        """
        if not self.game_id:
            return []
        
        if not self.db or not self.db.conn:
            if self.db:
                self.db.connect()
            else:
                return []
        
        cursor = self.db.conn.cursor()
        
        cursor.execute("""
            SELECT p.player_id, 
                   COALESCE(p.jersey, p.player_number) as player_number,
                   p.name,
                   al.position_number
            FROM active_lineup al
            INNER JOIN players p ON al.player_id = p.player_id
            WHERE al.game_id = ? AND al.team_id = ?
            ORDER BY al.position_number
        """, (self.game_id, team_id))
        
        return cursor.fetchall()
    
    def get_libero_player_id(self, team_id: int):
        """Get the libero player ID for the team."""
        if not self.game_id:
            return None
        
        if not self.db or not self.db.conn:
            if self.db:
                self.db.connect()
            else:
                return None
        
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT player_id 
            FROM players 
            WHERE team_id = ? AND role_code = 'Lib'
            LIMIT 1
        """, (team_id,))
        
        result = cursor.fetchone()
        return result[0] if result else None
    
    def show_substitution_dialog(self):
        """Show dialog for player substitution."""
        if not self.game_id or not self.team_us_id:
            QMessageBox.warning(self, "No Game", "Please select a game first.")
            return
        
        # Get bench players and active players
        bench_players = self.get_bench_players(self.team_us_id)
        active_players = self.get_active_players_with_positions(self.team_us_id)
        
        if not bench_players:
            QMessageBox.information(self, "No Bench Players", "No bench players available for substitution.")
            return
        
        if not active_players:
            QMessageBox.information(self, "No Active Players", "No active players on court.")
            return
        
        # Create substitution dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Player Substitution")
        dialog.setModal(True)
        dialog.setMinimumSize(500, 400)
        
        layout = QVBoxLayout(dialog)
        
        # Instructions
        instructions = QLabel("Select a bench player to enter and an active player to exit:")
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        # Two column layout for lists
        lists_layout = QHBoxLayout()
        
        # Bench players list (left)
        bench_label = QLabel("Bench Players:")
        bench_label.setFont(QFont('Arial', 10, QFont.Weight.Bold))
        bench_list = QListWidget()
        bench_list.setMinimumWidth(200)
        for player_id, player_number, player_name in bench_players:
            display_text = f"#{player_number} - {player_name}" if player_name else f"#{player_number}"
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, player_id)
            bench_list.addItem(item)
        
        bench_layout = QVBoxLayout()
        bench_layout.addWidget(bench_label)
        bench_layout.addWidget(bench_list)
        lists_layout.addLayout(bench_layout)
        
        # Active players list (right)
        active_label = QLabel("Active Players (on court):")
        active_label.setFont(QFont('Arial', 10, QFont.Weight.Bold))
        active_list = QListWidget()
        active_list.setMinimumWidth(200)
        for player_id, player_number, player_name, position_number in active_players:
            display_text = f"#{player_number} - {player_name} (Pos {position_number})" if player_name else f"#{player_number} (Pos {position_number})"
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, player_id)
            active_list.addItem(item)
        
        active_layout = QVBoxLayout()
        active_layout.addWidget(active_label)
        active_layout.addWidget(active_list)
        lists_layout.addLayout(active_layout)
        
        layout.addLayout(lists_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_btn)
        
        substitute_btn = QPushButton("Substitute")
        substitute_btn.setDefault(True)
        substitute_btn.setEnabled(False)  # Disabled until both are selected
        
        def on_selection_changed():
            """Enable substitute button when both players are selected."""
            bench_selected = bench_list.currentItem() is not None
            active_selected = active_list.currentItem() is not None
            substitute_btn.setEnabled(bench_selected and active_selected)
        
        bench_list.itemSelectionChanged.connect(on_selection_changed)
        active_list.itemSelectionChanged.connect(on_selection_changed)
        
        def perform_substitution():
            """Perform the substitution."""
            bench_item = bench_list.currentItem()
            active_item = active_list.currentItem()
            
            if not bench_item or not active_item:
                return
            
            in_player_id = bench_item.data(Qt.ItemDataRole.UserRole)
            out_player_id = active_item.data(Qt.ItemDataRole.UserRole)
            
            try:
                if not self.lineup_manager:
                    QMessageBox.critical(self, "Error", "LineupManager not initialized.")
                    return
                
                # Perform substitution using LineupManager
                self.lineup_manager.substitution(
                    team_id=self.team_us_id,
                    out_player_id=out_player_id,
                    in_player_id=in_player_id,
                    game_id=self.game_id
                )
                
                QMessageBox.information(self, "Substitution Complete", 
                                      "Player substitution completed successfully.")
                dialog.accept()
            except Exception as e:
                QMessageBox.critical(self, "Substitution Error", 
                                   f"Failed to perform substitution:\n{str(e)}")
        
        substitute_btn.clicked.connect(perform_substitution)
        button_layout.addWidget(substitute_btn)
        
        layout.addLayout(button_layout)
        
        dialog.exec()
    
    def show_libero_in_dialog(self):
        """Show dialog for libero to enter, displaying all positions (1-6) with players."""
        if not self.game_id or not self.team_us_id:
            QMessageBox.warning(self, "No Game", "Please select a game first.")
            return
        
        # Get libero player ID
        libero_id = self.get_libero_player_id(self.team_us_id)
        if not libero_id:
            QMessageBox.warning(self, "No Libero", "No libero player found for this team.")
            return
        
        # Check if libero is already on court
        if not self.db or not self.db.conn:
            if self.db:
                self.db.connect()
            else:
                QMessageBox.warning(self, "Error", "Database connection not available.")
                return
        
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT position_number 
            FROM active_lineup 
            WHERE game_id = ? AND team_id = ? AND player_id = ?
        """, (self.game_id, self.team_us_id, libero_id))
        if cursor.fetchone():
            QMessageBox.warning(self, "Libero Already On Court", "The libero is already on the court.")
            return
        
        # Get all positions in order: 1, 2, 3, 4, 5, 6
        all_positions = [1, 2, 3, 4, 5, 6]
        available_players = []
        
        for pos in all_positions:
            cursor.execute("""
                SELECT p.player_id, 
                       COALESCE(p.jersey, p.player_number) as player_number,
                       p.name
                FROM active_lineup al
                INNER JOIN players p ON al.player_id = p.player_id
                WHERE al.game_id = ? AND al.team_id = ? AND al.position_number = ?
            """, (self.game_id, self.team_us_id, pos))
            result = cursor.fetchone()
            if result:
                player_id, player_number, player_name = result
                # Check if this position already has a libero (shouldn't happen, but check anyway)
                if player_id != libero_id:
                    available_players.append((pos, player_id, player_number, player_name))
        
        if not available_players:
            QMessageBox.warning(self, "No Players Available", "No players available for libero replacement.")
            return
        
        # Create dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Libero IN - Select Position")
        dialog.setModal(True)
        dialog.setMinimumSize(400, 300)
        
        layout = QVBoxLayout(dialog)
        
        # Instructions
        instructions = QLabel("Select a position for the libero to enter:")
        instructions.setWordWrap(True)
        instructions.setFont(QFont('Arial', 10, QFont.Weight.Bold))
        layout.addWidget(instructions)
        
        # List of all positions with players
        positions_list = QListWidget()
        positions_list.setMinimumHeight(200)
        
        for pos, player_id, player_number, player_name in available_players:
            display_text = f"Position {pos}: #{player_number} - {player_name}" if player_name else f"Position {pos}: #{player_number}"
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, (pos, player_id))
            positions_list.addItem(item)
        
        layout.addWidget(positions_list)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_btn)
        
        enter_btn = QPushButton("Enter Libero")
        enter_btn.setDefault(True)
        enter_btn.setEnabled(False)
        
        def on_selection_changed():
            """Enable enter button when position is selected."""
            enter_btn.setEnabled(positions_list.currentItem() is not None)
        
        positions_list.itemSelectionChanged.connect(on_selection_changed)
        
        def perform_libero_enter():
            """Perform the libero enter action."""
            item = positions_list.currentItem()
            if not item:
                return
            
            pos, replaced_player_id = item.data(Qt.ItemDataRole.UserRole)
            
            try:
                if not self.lineup_manager:
                    QMessageBox.critical(self, "Error", "LineupManager not initialized.")
                    return
                
                # Perform libero replacement using LineupManager
                self.lineup_manager.libero_replace(
                    team_id=self.team_us_id,
                    libero_id=libero_id,
                    replaced_player_id=replaced_player_id,
                    replaced_position=pos,
                    action='enter',
                    game_id=self.game_id
                )
                
                # Track the replacement
                self.libero_replacements[pos] = replaced_player_id
                
                QMessageBox.information(self, "Libero Entered", 
                                      f"Libero has entered at position {pos}, replacing player #{replaced_player_id}.")
                dialog.accept()
            except Exception as e:
                QMessageBox.critical(self, "Libero Error", 
                                   f"Failed to enter libero:\n{str(e)}")
        
        enter_btn.clicked.connect(perform_libero_enter)
        button_layout.addWidget(enter_btn)
        
        layout.addLayout(button_layout)
        
        dialog.exec()
    
    def show_libero_out_dialog(self):
        """Show dialog for libero to exit, restoring the original player.
        
        Looks up the most recent row in libero_actions table for this game,
        finds the replaced_player_id, and swaps that player into the position
        where the libero currently is.
        """
        if not self.game_id or not self.team_us_id:
            QMessageBox.warning(self, "No Game", "Please select a game first.")
            return
        
        # Get libero player ID
        libero_id = self.get_libero_player_id(self.team_us_id)
        if not libero_id:
            QMessageBox.warning(self, "No Libero", "No libero player found for this team.")
            return
        
        # Find positions where libero is currently on court
        if not self.db or not self.db.conn:
            if self.db:
                self.db.connect()
            else:
                QMessageBox.warning(self, "Error", "Database connection not available.")
                return
        
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT position_number 
            FROM active_lineup 
            WHERE game_id = ? AND team_id = ? AND player_id = ?
        """, (self.game_id, self.team_us_id, libero_id))
        
        libero_positions = cursor.fetchall()
        if not libero_positions:
            QMessageBox.warning(self, "Libero Not On Court", "The libero is not currently on the court.")
            return
        
        # Get the most recent libero_actions record for this game (regardless of position)
        cursor.execute("""
            SELECT replaced_player_id, replaced_position
            FROM libero_actions 
            WHERE game_id = ? AND team_id = ? AND action = 'enter'
            ORDER BY created_at DESC
            LIMIT 1
        """, (self.game_id, self.team_us_id))
        
        result = cursor.fetchone()
        if not result:
            QMessageBox.warning(self, "Error", 
                               "Could not find libero_actions record for this game.\n"
                               "The libero may not have been entered through the system.")
            return
        
        replaced_player_id, original_position = result
        
        # Get the current position(s) where libero is on court
        current_positions = [pos[0] for pos in libero_positions]
        
        # If libero is in multiple positions, use the position from the most recent libero_actions record
        # Otherwise, use the single position where libero is
        if len(current_positions) == 1:
            target_position = current_positions[0]
        else:
            # Libero is in multiple positions - use the position from the most recent libero_actions record
            # if it matches one of the current positions, otherwise use the first position
            if original_position in current_positions:
                target_position = original_position
            else:
                target_position = current_positions[0]
        
        # Get player info for the replaced player
        cursor.execute("""
            SELECT COALESCE(p.jersey, p.player_number) as player_number, p.name
            FROM players p
            WHERE p.player_id = ?
        """, (replaced_player_id,))
        player_info = cursor.fetchone()
        if not player_info:
            QMessageBox.warning(self, "Error", 
                               f"Could not find player {replaced_player_id} in database.")
            return
        
        player_number, player_name = player_info
        
        # If libero is only in one position, exit directly
        if len(current_positions) == 1:
            self.perform_libero_exit(libero_id, target_position, replaced_player_id)
            return
        
        # If libero is in multiple positions, show dialog to select which one
        # Create dialog to select which position to exit from
        dialog = QDialog(self)
        dialog.setWindowTitle("Libero OUT - Select Position")
        dialog.setModal(True)
        dialog.setMinimumSize(400, 300)
        
        layout = QVBoxLayout(dialog)
        
        # Instructions
        instructions = QLabel(f"Libero is in multiple positions. Select position to exit:\n\n"
                             f"Will restore player #{player_number} - {player_name or 'Unknown'}")
        instructions.setWordWrap(True)
        instructions.setFont(QFont('Arial', 10, QFont.Weight.Bold))
        layout.addWidget(instructions)
        
        # List of positions
        positions_list = QListWidget()
        positions_list.setMinimumHeight(200)
        
        for pos in current_positions:
            display_text = f"Position {pos}"
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, pos)
            positions_list.addItem(item)
            # Pre-select the position from the most recent libero_actions record
            if pos == target_position:
                positions_list.setCurrentItem(item)
        
        layout.addWidget(positions_list)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_btn)
        
        exit_btn = QPushButton("Exit Libero")
        exit_btn.setDefault(True)
        exit_btn.setEnabled(False)
        
        def on_selection_changed():
            """Enable exit button when position is selected."""
            exit_btn.setEnabled(positions_list.currentItem() is not None)
        
        positions_list.itemSelectionChanged.connect(on_selection_changed)
        
        def perform_libero_exit_dialog():
            """Perform the libero exit action from dialog."""
            item = positions_list.currentItem()
            if not item:
                return
            
            pos = item.data(Qt.ItemDataRole.UserRole)
            self.perform_libero_exit(libero_id, pos, replaced_player_id)
            dialog.accept()
        
        exit_btn.clicked.connect(perform_libero_exit_dialog)
        button_layout.addWidget(exit_btn)
        
        layout.addLayout(button_layout)
        
        dialog.exec()
    
    def perform_libero_exit(self, libero_id: int, position: int, replaced_player_id: int):
        """Perform the libero exit action."""
        try:
            if not self.lineup_manager:
                QMessageBox.critical(self, "Error", "LineupManager not initialized.")
                return
            
            # Perform libero replacement using LineupManager
            self.lineup_manager.libero_replace(
                team_id=self.team_us_id,
                libero_id=libero_id,
                replaced_player_id=replaced_player_id,
                replaced_position=position,
                action='exit',
                game_id=self.game_id
            )
            
            # Remove from tracking dict
            if position in self.libero_replacements:
                del self.libero_replacements[position]
            
            QMessageBox.information(self, "Libero Exited", 
                                  f"Libero has exited position {position}. Original player restored.")
        except Exception as e:
            QMessageBox.critical(self, "Libero Error", 
                               f"Failed to exit libero:\n{str(e)}")
    
    def _compute_homography(self):
        """Compute the homography matrix using OpenCV based on the 10 control points."""
        if len(self.corner_points) < 10:
            self.homography_matrix = None
            return
        
        # Define logical coordinates for all 10 control points
        # Order: [BL, BR, TR, TL, ML, MR, Y200L, Y200R, Y400L, Y400R]
        logical_coords = np.array([
            [0, 0],      # BL
            [300, 0],    # BR
            [300, 600],  # TR
            [0, 600],    # TL
            [0, 300],    # ML
            [300, 300],  # MR
            [0, 200],    # Y200L
            [300, 200],  # Y200R
            [0, 400],    # Y400L
            [300, 400]   # Y400R
        ], dtype=np.float32)
        
        # Get pixel coordinates of control points
        pixel_coords = np.array(self.corner_points, dtype=np.float32)
        
        # Compute homography matrix using all 10 points for better accuracy
        # cv2.findHomography uses RANSAC by default for robust estimation
        self.homography_matrix, mask = cv2.findHomography(
            pixel_coords, 
            logical_coords,
            method=cv2.RANSAC,
            ransacReprojThreshold=5.0
        )
        
        if self.homography_matrix is not None:
            print("Homography matrix computed successfully")
            print(f"Matrix:\n{self.homography_matrix}")
        else:
            print("Warning: Failed to compute homography matrix")
    
    def map_point_to_logical(self, x, y):
        """
        Map a pixel coordinate (x, y) to logical coordinates using OpenCV homography.
        
        Uses the homography matrix computed from the 10 control points to transform
        pixel coordinates to logical coordinates. This provides accurate perspective
        correction using all control points including ML, Y200, and Y400 lines.
        
        Returns:
            [logical_x, logical_y] or None if mapping fails
        """
        if self.homography_matrix is None:
            # Try to compute homography if we have enough points
            if len(self.corner_points) >= 10:
                self._compute_homography()
            else:
                return None
        
        if self.homography_matrix is None:
            return None
        
        # Transform pixel coordinate to logical coordinate using homography
        # Convert to homogeneous coordinates
        pixel_point = np.array([x, y, 1.0], dtype=np.float32).reshape(3, 1)
        
        # Apply homography transformation
        mapped = self.homography_matrix @ pixel_point
        
        # Convert back from homogeneous coordinates
        mapped /= mapped[2]
        logical_x = float(mapped[0][0])
        logical_y = float(mapped[1][0])
        
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
    
    def handle_double_click(self, x, y):
        """Handle double-click for DOWN contact."""
        # Map the clicked point to logical coordinates
        logical_coords = self.map_point_to_logical(x, y)
        
        if logical_coords is not None:
            # Display "DOWN" text at the click location
            text_item = QGraphicsTextItem("DOWN")
            text_item.setPos(x - 25, y - 15)  # Center the text roughly on the click
            text_item.setDefaultTextColor(QColor(255, 0, 0))  # Red text
            font = QFont('Arial', 16, QFont.Weight.Bold)
            text_item.setFont(font)
            self.scene.addItem(text_item)
            
            # Remove the text after 1 second
            QTimer.singleShot(1000, lambda: self._remove_down_text(text_item))
            
            # Get current video timecode in milliseconds
            timecode_ms = self.media_player.position()
            
            # Emit double-click signal
            self.double_click_mapped.emit(logical_coords[0], logical_coords[1], x, y, timecode_ms)
    
    def _remove_down_text(self, text_item):
        """Remove the DOWN text from the scene."""
        if text_item in self.scene.items():
            self.scene.removeItem(text_item)
    
    def is_configured(self):
        """Check if the coordinate mapper has been configured with 10 control points."""
        return len(self.corner_points) >= 10
    
    def get_corner_points(self):
        """Get the current corner points (for saving configuration)."""
        return self.corner_points.copy()
    
    def set_corner_points(self, points):
        """Set the corner points (for loading configuration)."""
        if len(points) == 10:
            self.corner_points = [list(p) for p in points]
            self.mode = 'normal'
            self.modify_court_btn.setEnabled(True)
            self.store_boundaries_btn.setEnabled(True)
            self.status_label.setText("Plane defined! Click 'Store Court Boundaries' to save and start mapping.")
            # Compute homography matrix
            self._compute_homography()
            # Redraw the plane
            self._redraw_plane()
        elif len(points) == 6:
            # Backward compatibility: if only 6 points provided, pad with None for Y200 and Y400
            # This allows loading old configurations
            self.corner_points = [list(p) for p in points] + [None] * 4
            self.mode = 'normal'
            self.modify_court_btn.setEnabled(False)  # Can't modify if not fully configured
            self.store_boundaries_btn.setEnabled(False)
            self.status_label.setText("Plane partially defined (6 points). Please set up Y200 and Y400 lines.")
            self.homography_matrix = None  # Can't compute homography without all points
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
            labels = ['BL (0,0)', 'BR (300,0)', 'TR (300,600)', 'TL (0,600)', 'ML (0,300)', 'MR (300,300)',
                     'Y200L (0,200)', 'Y200R (300,200)', 'Y400L (0,400)', 'Y400R (300,400)']
            for i, point in enumerate(self.corner_points):
                if point is None:  # Skip None points (for backward compatibility)
                    continue
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
                
                # Centerline - lighter color and 3x wider
                centerline_pen = QPen(QColor(255, 220, 180), 6)  # Lighter orange, 3x wider (2*3=6)
                centerline_pen.setStyle(Qt.PenStyle.DashLine)
                line3 = QGraphicsLineItem(
                    self.corner_points[4][0], self.corner_points[4][1],
                    self.corner_points[5][0], self.corner_points[5][1]
                )
                line3.setPen(centerline_pen)
                self.scene.addItem(line3)
                self.graphics_items.append(line3)
            
            # Draw Y=200 line if points 6 and 7 exist
            if len(self.corner_points) >= 8 and self.corner_points[6] is not None and self.corner_points[7] is not None:
                pen = QPen(QColor(0, 255, 0), 2)  # Green for Y=200 line
                pen.setStyle(Qt.PenStyle.DashLine)
                # Horizontal line
                line1 = QGraphicsLineItem(
                    self.corner_points[6][0], self.corner_points[6][1],
                    self.corner_points[7][0], self.corner_points[7][1]
                )
                line1.setPen(pen)
                self.scene.addItem(line1)
                self.graphics_items.append(line1)
                # Left edge
                line2 = QGraphicsLineItem(
                    self.corner_points[0][0], self.corner_points[0][1],
                    self.corner_points[6][0], self.corner_points[6][1]
                )
                line2.setPen(pen)
                self.scene.addItem(line2)
                self.graphics_items.append(line2)
                # Right edge
                line3 = QGraphicsLineItem(
                    self.corner_points[1][0], self.corner_points[1][1],
                    self.corner_points[7][0], self.corner_points[7][1]
                )
                line3.setPen(pen)
                self.scene.addItem(line3)
                self.graphics_items.append(line3)
            
            # Draw Y=400 line if points 8 and 9 exist
            if len(self.corner_points) >= 10 and self.corner_points[8] is not None and self.corner_points[9] is not None:
                pen = QPen(QColor(255, 0, 255), 2)  # Magenta for Y=400 line
                pen.setStyle(Qt.PenStyle.DashLine)
                # Horizontal line
                line1 = QGraphicsLineItem(
                    self.corner_points[8][0], self.corner_points[8][1],
                    self.corner_points[9][0], self.corner_points[9][1]
                )
                line1.setPen(pen)
                self.scene.addItem(line1)
                self.graphics_items.append(line1)
                # Left edge
                line2 = QGraphicsLineItem(
                    self.corner_points[4][0], self.corner_points[4][1],
                    self.corner_points[8][0], self.corner_points[8][1]
                )
                line2.setPen(pen)
                self.scene.addItem(line2)
                self.graphics_items.append(line2)
                # Right edge
                line3 = QGraphicsLineItem(
                    self.corner_points[5][0], self.corner_points[5][1],
                    self.corner_points[9][0], self.corner_points[9][1]
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
