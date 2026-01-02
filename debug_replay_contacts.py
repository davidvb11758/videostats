"""
Debug Replay Contacts - Replays video with contact visualization for debugging.
Draws contacts in contact_id order, highlighting out-of-sequence contacts in red.
"""

import numpy as np
from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGraphicsView, QGraphicsScene,
    QGraphicsEllipseItem, QGraphicsLineItem, QPushButton, QSlider, QComboBox, QMessageBox,
    QTextEdit
)
from PySide6.QtCore import Qt, QPointF, QUrl, QTimer, QRectF
from PySide6.QtGui import QPen, QBrush, QColor, QFont, QPainter, QPolygonF
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
from database import VideoStatsDB


class DebugReplayContactsWindow(QMainWindow):
    """Debug window for replaying video with contact visualization."""
    
    def __init__(self, db: VideoStatsDB, game_id: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Debug Replay Contacts - Game {game_id}")
        self.resize(1400, 800)
        
        # Set window flags to ensure it stays open and is a top-level window
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        # Make it a standalone window (not a child that closes with parent)
        if parent is None:
            self.setWindowFlags(Qt.WindowType.Window)
        
        self.db = db
        self.game_id = game_id
        
        print(f"DEBUG: Creating DebugReplayContactsWindow for game {game_id}")
        
        # Video playback
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        self.video_item = None
        self.video_loaded = False
        
        # Graphics scene and view
        self.scene = QGraphicsScene(0, 0, 1200, 666)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Contact data
        self.contacts = []  # List of contact dicts ordered by contact_id
        self.drawn_items = []  # List of graphics items for clearing
        self.homography_matrix = None
        self.court_boundaries = None
        
        # Track which contacts have been drawn
        self.drawn_contact_ids = set()
        
        # Track the last processed contact's timecode to detect out-of-sequence
        self.last_processed_timecode = None
        
        # Setup UI
        self.setup_ui()
        
        # Timer for checking contacts as video plays
        self.contact_check_timer = QTimer()
        self.contact_check_timer.timeout.connect(self.check_and_draw_contacts)
        self.contact_check_timer.start(100)  # Check every 100ms
        
        # Load game data (after UI is set up)
        try:
            print(f"DEBUG: About to load game data for game {self.game_id}")
            self.load_game_data()
            print(f"DEBUG: Game data loaded successfully")
        except Exception as e:
            import traceback
            error_msg = f"Error loading game data:\n{str(e)}\n\n{traceback.format_exc()}"
            print(f"ERROR in load_game_data: {error_msg}")
            QMessageBox.critical(self, "Error", error_msg)
    
    def setup_ui(self):
        """Set up the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Graphics view for video
        layout.addWidget(self.view)
        
        # Video controls
        controls_layout = QHBoxLayout()
        
        self.play_pause_btn = QPushButton("Play")
        self.play_pause_btn.setFont(QFont('Arial', 10))
        self.play_pause_btn.clicked.connect(self.toggle_play_pause)
        self.play_pause_btn.setEnabled(False)
        controls_layout.addWidget(self.play_pause_btn)
        
        self.video_slider = QSlider(Qt.Orientation.Horizontal)
        self.video_slider.setEnabled(False)
        self.video_slider.sliderMoved.connect(self.seek_video)
        controls_layout.addWidget(self.video_slider, stretch=2)
        
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setFont(QFont('Arial', 10))
        controls_layout.addWidget(self.time_label)
        
        # Playback speed control
        speed_label = QLabel("Speed:")
        speed_label.setFont(QFont('Arial', 10))
        controls_layout.addWidget(speed_label)
        
        self.speed_combo = QComboBox()
        self.speed_combo.setFont(QFont('Arial', 10))
        self.speed_combo.addItems(["0.33x", "0.5x", "0.75x", "0.8x", "0.9x", "1.0x"])
        self.speed_combo.setCurrentText("1.0x")
        self.speed_combo.currentTextChanged.connect(self.change_playback_speed)
        self.speed_combo.setEnabled(False)
        controls_layout.addWidget(self.speed_combo)
        
        layout.addLayout(controls_layout)
        
        # Clear dots button
        clear_layout = QHBoxLayout()
        self.clear_btn = QPushButton("Clear Dots")
        self.clear_btn.setFont(QFont('Arial', 10))
        self.clear_btn.clicked.connect(self.clear_dots)
        clear_layout.addWidget(self.clear_btn)
        clear_layout.addStretch()
        layout.addLayout(clear_layout)
        
        # Message area for contact info
        message_label = QLabel("Contact Info:")
        message_label.setFont(QFont('Arial', 10))
        layout.addWidget(message_label)
        
        self.message_area = QTextEdit()
        self.message_area.setFont(QFont('Courier', 9))
        self.message_area.setMaximumHeight(150)
        self.message_area.setReadOnly(True)
        layout.addWidget(self.message_area)
        
        # Connect media player signals
        self.media_player.positionChanged.connect(self.update_position)
        self.media_player.durationChanged.connect(self.update_duration)
        self.media_player.mediaStatusChanged.connect(self.on_media_status_changed)
    
    def load_game_data(self):
        """Load game data including video path and contacts."""
        if not self.db.conn:
            self.db.connect()
        
        cursor = self.db.conn.cursor()
        
        # Get video file path using database method
        video_path = self.db.get_game_video_path(self.game_id)
        if not video_path:
            QMessageBox.warning(self, "No Video", f"Game {self.game_id} does not have a video file path.")
            # Don't return - still show window even without video
            return
        
        # Convert to absolute path if needed
        try:
            video_path = str(Path(video_path).resolve())
        except Exception as e:
            QMessageBox.warning(self, "Invalid Path", f"Could not resolve video path: {video_path}\nError: {e}")
            return
        
        # Get court boundaries and homography matrix
        self.court_boundaries = self.db.get_game_court_boundaries(self.game_id)
        if self.court_boundaries and self.court_boundaries.get('homography_matrix') is not None:
            self.homography_matrix = self.court_boundaries['homography_matrix']
        else:
            QMessageBox.warning(self, "No Homography", 
                              f"Game {self.game_id} does not have homography matrix. Cannot draw contacts.")
            # Still load video but contacts won't be drawn
        
        # Load video
        try:
            self.load_video(video_path)
        except Exception as e:
            import traceback
            error_msg = f"Error loading video:\n{str(e)}\n\n{traceback.format_exc()}"
            QMessageBox.critical(self, "Video Load Error", error_msg)
            print(f"ERROR loading video: {error_msg}")
        
        # Draw court boundaries after video is loaded
        if self.court_boundaries:
            # Use QTimer to draw after video is loaded
            QTimer.singleShot(500, self.draw_court_boundaries)
        
        print(f"DEBUG: Loaded {len(self.contacts)} contacts, homography_matrix: {self.homography_matrix is not None}")
        
        # Load contacts ordered by contact_id
        cursor.execute("""
            SELECT 
                c.contact_id,
                c.rally_id,
                c.sequence_number,
                c.player_id,
                c.contact_type,
                c.team_id,
                c.x,
                c.y,
                c.timecode,
                c.outcome,
                c.rating,
                p.player_number,
                p.name as player_name
            FROM contacts c
            INNER JOIN rallies r ON c.rally_id = r.rally_id
            LEFT JOIN players p ON c.player_id = p.player_id
            WHERE r.game_id = ?
              AND c.x IS NOT NULL
              AND c.y IS NOT NULL
              AND c.timecode IS NOT NULL
            ORDER BY c.contact_id
        """, (self.game_id,))
        
        contacts = cursor.fetchall()
        self.contacts = []
        for contact in contacts:
            self.contacts.append({
                'contact_id': contact[0],
                'rally_id': contact[1],
                'sequence_number': contact[2],
                'player_id': contact[3],
                'contact_type': contact[4],
                'team_id': contact[5],
                'x': contact[6],
                'y': contact[7],
                'timecode': contact[8],
                'outcome': contact[9],
                'rating': contact[10],
                'player_number': contact[11],
                'player_name': contact[12]
            })
        
        # Find next contact for each contact (for drawing arrows)
        for i, contact in enumerate(self.contacts):
            if i < len(self.contacts) - 1:
                next_contact = self.contacts[i + 1]
                if next_contact['x'] is not None and next_contact['y'] is not None:
                    contact['next_x'] = next_contact['x']
                    contact['next_y'] = next_contact['y']
                else:
                    contact['next_x'] = None
                    contact['next_y'] = None
            else:
                contact['next_x'] = None
                contact['next_y'] = None
        
        self.message_area.append(f"Loaded {len(self.contacts)} contacts for game {self.game_id}")
    
    def load_video(self, file_path: str):
        """Load video file into the player."""
        if not file_path:
            QMessageBox.warning(self, "Video Not Found", "No video file path provided.")
            return
        
        # Convert to absolute path and check existence
        video_path_abs = Path(file_path).resolve()
        if not video_path_abs.exists():
            QMessageBox.warning(self, "Video Not Found", f"Video file not found: {video_path_abs}")
            return
        
        # Remove existing video item if present
        if self.video_item:
            self.scene.removeItem(self.video_item)
            self.video_item = None
        
        # Create and add video item to scene
        self.video_item = QGraphicsVideoItem()
        # Initially set to default size, will be adjusted when video metadata is available
        self.video_item.setSize(QRectF(0, 0, 1200, 666).size())
        self.scene.addItem(self.video_item)
        
        # Connect to nativeSizeChanged signal BEFORE setting source
        self.video_item.nativeSizeChanged.connect(self._adjust_scene_to_video_size)
        
        # Set video item to be behind other graphics
        self.video_item.setZValue(-1)
        
        # Set video output
        self.media_player.setVideoOutput(self.video_item)
        
        # Load the video using absolute path
        self.media_player.setSource(QUrl.fromLocalFile(str(video_path_abs)))
        
        self.video_loaded = True
        # Controls will be enabled when media is loaded (in on_media_status_changed)
    
    def _adjust_scene_to_video_size(self):
        """Adjust scene and video item size to match actual video dimensions."""
        if not self.video_item:
            return
        
        video_size = self.video_item.nativeSize()
        if video_size.isValid() and video_size.width() > 0 and video_size.height() > 0:
            video_width = video_size.width()
            video_height = video_size.height()
            
            # Only update if size has changed to avoid repeated calls
            current_size = self.video_item.size()
            if current_size.width() != video_width or current_size.height() != video_height:
                self.video_item.setSize(video_size)
                self.scene.setSceneRect(0, 0, video_width, video_height)
                print(f"DEBUG: Adjusted scene to video size: {video_width}x{video_height}")
    
    def enable_video_controls(self):
        """Enable video playback controls."""
        self.play_pause_btn.setEnabled(True)
        self.video_slider.setEnabled(True)
        self.speed_combo.setEnabled(True)
    
    def on_media_status_changed(self, status):
        """Handle media status changes."""
        from PySide6.QtMultimedia import QMediaPlayer
        if status == QMediaPlayer.MediaStatus.LoadedMedia or status == QMediaPlayer.MediaStatus.BufferedMedia:
            self.enable_video_controls()
            self._adjust_scene_to_video_size()
            # Check for contacts that should be drawn at current position
            QTimer.singleShot(200, self.check_and_draw_contacts)
    
    def toggle_play_pause(self):
        """Toggle between play and pause."""
        from PySide6.QtMultimedia import QMediaPlayer
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
            self.play_pause_btn.setText("Play")
        else:
            self.media_player.play()
            self.play_pause_btn.setText("Pause")
    
    def seek_video(self, position):
        """Seek to a specific position in the video."""
        self.media_player.setPosition(position)
        # Clear drawn contacts and redraw up to current position
        self.clear_dots()
        self.drawn_contact_ids.clear()
        self.last_processed_timecode = None  # Reset when seeking
        # Use QTimer to ensure position is updated before checking contacts
        QTimer.singleShot(100, self.check_and_draw_contacts)
    
    def update_position(self, position):
        """Update the slider position as the video plays."""
        if not self.video_slider.isSliderDown():
            self.video_slider.setValue(position)
        
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
        speed_value = float(speed_text.replace('x', ''))
        self.media_player.setPlaybackRate(speed_value)
    
    def clear_dots(self):
        """Clear all drawn contact dots and lines."""
        for item in self.drawn_items:
            if item.scene() == self.scene:
                self.scene.removeItem(item)
        self.drawn_items.clear()
    
    def check_and_draw_contacts(self):
        """Check current video position and draw contacts that should be visible."""
        if not self.video_loaded or not self.contacts:
            return
        
        # Check if homography matrix exists (it's a numpy array, so check for None)
        if self.homography_matrix is None:
            return
        
        current_position = self.media_player.position()
        
        # Debug: Print first few contacts and current position occasionally
        if len(self.drawn_contact_ids) == 0 and len(self.contacts) > 0:
            print(f"DEBUG: Current video position: {current_position}ms, First contact timecode: {self.contacts[0].get('timecode')}ms")
        
        # Check each contact in contact_id order
        for contact in self.contacts:
            contact_id = contact['contact_id']
            
            # Skip if already drawn
            if contact_id in self.drawn_contact_ids:
                continue
            
            timecode = contact.get('timecode')
            if timecode is None:
                continue
            
            # Determine if contact is out of sequence
            # A contact is out of sequence if its timecode is LESS than the previous contact's timecode
            # (meaning it should have been processed earlier in contact_id order)
            is_out_of_sequence = False
            if self.last_processed_timecode is not None:
                if timecode < self.last_processed_timecode:
                    is_out_of_sequence = True
                    print(f"DEBUG: Contact {contact_id} is OUT OF SEQUENCE: timecode {timecode}ms < previous {self.last_processed_timecode}ms")
            
            # Draw if timecode has been reached
            if timecode <= current_position:
                print(f"DEBUG: Drawing contact {contact_id} at timecode {timecode}ms (current: {current_position}ms, out_of_seq: {is_out_of_sequence})")
                self.draw_contact(contact, is_out_of_sequence)
                self.drawn_contact_ids.add(contact_id)
                # Update last processed timecode (use max to handle same timecode case)
                if self.last_processed_timecode is None or timecode >= self.last_processed_timecode:
                    self.last_processed_timecode = timecode
    
    def draw_contact(self, contact, is_out_of_sequence=False):
        """Draw a single contact (source dot and arrow to destination)."""
        if self.homography_matrix is None:
            print(f"DEBUG: Cannot draw contact {contact.get('contact_id')} - no homography matrix")
            return
        
        x = contact.get('x')
        y = contact.get('y')
        if x is None or y is None:
            print(f"DEBUG: Cannot draw contact {contact.get('contact_id')} - missing coordinates")
            return
        
        # Determine color (red if out of sequence, green otherwise)
        color = QColor(255, 0, 0) if is_out_of_sequence else QColor(0, 255, 0)
        
        try:
            # Get inverse homography
            inv_homography = np.linalg.inv(self.homography_matrix)
        except np.linalg.LinAlgError:
            return
        
        # Get court boundaries for scaling
        if not self.court_boundaries:
            return
        
        video_offset_x = self.court_boundaries.get('video_offset_x', 0)
        video_offset_y = self.court_boundaries.get('video_offset_y', 0)
        source_video_width = self.court_boundaries.get('video_width', 0)
        source_video_height = self.court_boundaries.get('video_height', 0)
        source_scene_width = self.court_boundaries.get('scene_width', 0)
        source_scene_height = self.court_boundaries.get('scene_height', 0)
        
        # Get actual video size
        if self.video_item:
            video_size = self.video_item.nativeSize()
            if video_size.isValid():
                target_scene_width = video_size.width()
                target_scene_height = video_size.height()
            else:
                target_scene_width = 1200.0
                target_scene_height = 666.0
        else:
            target_scene_width = 1200.0
            target_scene_height = 666.0
        
        # Calculate scaling factors
        if source_video_width > 0 and source_video_height > 0:
            scale_x = target_scene_width / source_video_width
            scale_y = target_scene_height / source_video_height
        elif source_scene_width > 0 and source_scene_height > 0:
            scale_x = target_scene_width / source_scene_width
            scale_y = target_scene_height / source_scene_height
        else:
            scale_x = target_scene_width / 1500.0
            scale_y = target_scene_height / 600.0
        
        # Transform source coordinates (logical to pixel)
        try:
            logical_point = np.array([x, y, 1.0], dtype=np.float32).reshape(3, 1)
            pixel_point = inv_homography @ logical_point
            pixel_point /= pixel_point[2]
            
            source_px = int((pixel_point[0][0] - video_offset_x) * scale_x)
            source_py = int((pixel_point[1][0] - video_offset_y) * scale_y)
            
            # Draw source dot
            dot_radius = 5
            source_dot = self.scene.addEllipse(
                0, 0,
                dot_radius * 2, dot_radius * 2,
                QPen(color, 2),
                QBrush(color)
            )
            source_dot.setPos(source_px - dot_radius, source_py - dot_radius)
            source_dot.setZValue(1000)
            self.drawn_items.append(source_dot)
            
            # Draw arrow to destination if available
            next_x = contact.get('next_x')
            next_y = contact.get('next_y')
            if next_x is not None and next_y is not None:
                logical_point_dest = np.array([next_x, next_y, 1.0], dtype=np.float32).reshape(3, 1)
                pixel_point_dest = inv_homography @ logical_point_dest
                pixel_point_dest /= pixel_point_dest[2]
                
                dest_px = int((pixel_point_dest[0][0] - video_offset_x) * scale_x)
                dest_py = int((pixel_point_dest[1][0] - video_offset_y) * scale_y)
                
                # Draw destination dot
                dest_dot = self.scene.addEllipse(
                    0, 0,
                    dot_radius * 2, dot_radius * 2,
                    QPen(color, 2),
                    QBrush(color)
                )
                dest_dot.setPos(dest_px - dot_radius, dest_py - dot_radius)
                dest_dot.setZValue(1000)
                self.drawn_items.append(dest_dot)
                
                # Draw arrow line
                source_center = QPointF(source_px, source_py)
                dest_center = QPointF(dest_px, dest_py)
                
                arrow_line = self.scene.addLine(
                    source_center.x(), source_center.y(),
                    dest_center.x(), dest_center.y(),
                    QPen(color, 2)
                )
                arrow_line.setZValue(999)
                self.drawn_items.append(arrow_line)
                
                # Draw arrowhead (simple triangle)
                self.draw_arrowhead(source_center, dest_center, color)
            
            # Update message area with contact info
            self.display_contact_info(contact, is_out_of_sequence)
            print(f"DEBUG: Drew contact {contact['contact_id']} at ({source_px}, {source_py}) from logical ({x}, {y})")
            
        except Exception as e:
            import traceback
            print(f"ERROR drawing contact {contact['contact_id']}: {e}\n{traceback.format_exc()}")
    
    def draw_arrowhead(self, start: QPointF, end: QPointF, color: QColor):
        """Draw an arrowhead at the end of the line."""
        # Calculate arrow direction
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        length = np.sqrt(dx*dx + dy*dy)
        
        if length < 1:
            return
        
        # Normalize
        dx /= length
        dy /= length
        
        # Arrowhead size
        arrow_size = 8
        
        # Perpendicular vector for arrowhead base
        perp_x = -dy
        perp_y = dx
        
        # Arrowhead points
        tip = end
        base1 = QPointF(end.x() - arrow_size * dx + arrow_size * 0.5 * perp_x,
                       end.y() - arrow_size * dy + arrow_size * 0.5 * perp_y)
        base2 = QPointF(end.x() - arrow_size * dx - arrow_size * 0.5 * perp_x,
                       end.y() - arrow_size * dy - arrow_size * 0.5 * perp_y)
        
        # Draw arrowhead as polygon
        arrowhead = QPolygonF([tip, base1, base2])
        arrowhead_item = self.scene.addPolygon(arrowhead, QPen(color, 1), QBrush(color))
        arrowhead_item.setZValue(1000)
        self.drawn_items.append(arrowhead_item)
    
    def draw_court_boundaries(self):
        """Draw court boundary corners and lines on the video."""
        if not self.court_boundaries:
            print("DEBUG: No court boundaries to draw")
            return
        
        # Get the 4 corners
        corner_bl = self.court_boundaries.get('corner_bl')
        corner_br = self.court_boundaries.get('corner_br')
        corner_tr = self.court_boundaries.get('corner_tr')
        corner_tl = self.court_boundaries.get('corner_tl')
        
        if not all([corner_bl, corner_br, corner_tr, corner_tl]):
            print("DEBUG: Missing corner points, cannot draw court boundaries")
            return
        
        # Get video dimensions and offsets
        video_offset_x = self.court_boundaries.get('video_offset_x', 0)
        video_offset_y = self.court_boundaries.get('video_offset_y', 0)
        source_video_width = self.court_boundaries.get('video_width', 0)
        source_video_height = self.court_boundaries.get('video_height', 0)
        source_scene_width = self.court_boundaries.get('scene_width', 0)
        source_scene_height = self.court_boundaries.get('scene_height', 0)
        
        # Get actual video size
        if self.video_item:
            video_size = self.video_item.nativeSize()
            if video_size.isValid():
                target_scene_width = video_size.width()
                target_scene_height = video_size.height()
            else:
                target_scene_width = 1200.0
                target_scene_height = 666.0
        else:
            target_scene_width = 1200.0
            target_scene_height = 666.0
        
        # Calculate scaling factors
        if source_video_width > 0 and source_video_height > 0:
            scale_x = target_scene_width / source_video_width
            scale_y = target_scene_height / source_video_height
        elif source_scene_width > 0 and source_scene_height > 0:
            scale_x = target_scene_width / source_scene_width
            scale_y = target_scene_height / source_scene_height
        else:
            scale_x = target_scene_width / 1500.0
            scale_y = target_scene_height / 600.0
        
        # Convert corner coordinates to target scene coordinates
        bl_x = (corner_bl[0] - video_offset_x) * scale_x
        bl_y = (corner_bl[1] - video_offset_y) * scale_y
        br_x = (corner_br[0] - video_offset_x) * scale_x
        br_y = (corner_br[1] - video_offset_y) * scale_y
        tr_x = (corner_tr[0] - video_offset_x) * scale_x
        tr_y = (corner_tr[1] - video_offset_y) * scale_y
        tl_x = (corner_tl[0] - video_offset_x) * scale_x
        tl_y = (corner_tl[1] - video_offset_y) * scale_y
        
        # Draw 4 corners as circles
        corner_radius = 5
        corner_pen = QPen(QColor(255, 0, 0), 2)
        corner_brush = QBrush(QColor(255, 0, 0, 180))
        
        corner_items = []
        corner_items.append(self.scene.addEllipse(bl_x - corner_radius, bl_y - corner_radius,
                                                  corner_radius * 2, corner_radius * 2,
                                                  corner_pen, corner_brush))
        corner_items.append(self.scene.addEllipse(br_x - corner_radius, br_y - corner_radius,
                                                  corner_radius * 2, corner_radius * 2,
                                                  corner_pen, corner_brush))
        corner_items.append(self.scene.addEllipse(tr_x - corner_radius, tr_y - corner_radius,
                                                  corner_radius * 2, corner_radius * 2,
                                                  corner_pen, corner_brush))
        corner_items.append(self.scene.addEllipse(tl_x - corner_radius, tl_y - corner_radius,
                                                  corner_radius * 2, corner_radius * 2,
                                                  corner_pen, corner_brush))
        
        for item in corner_items:
            item.setZValue(100)
            self.drawn_items.append(item)
        
        # Draw 4 boundary lines
        line_pen = QPen(QColor(0, 255, 0), 2)
        line_pen.setStyle(Qt.PenStyle.DashLine)
        
        line_items = []
        line_items.append(self.scene.addLine(bl_x, bl_y, br_x, br_y, line_pen))  # Bottom
        line_items.append(self.scene.addLine(br_x, br_y, tr_x, tr_y, line_pen))  # Right
        line_items.append(self.scene.addLine(tr_x, tr_y, tl_x, tl_y, line_pen))  # Top
        line_items.append(self.scene.addLine(tl_x, tl_y, bl_x, bl_y, line_pen))  # Left
        
        for item in line_items:
            item.setZValue(99)
            self.drawn_items.append(item)
        
        print(f"DEBUG: Court boundaries drawn - BL:({bl_x:.1f},{bl_y:.1f}), BR:({br_x:.1f},{br_y:.1f}), TR:({tr_x:.1f},{tr_y:.1f}), TL:({tl_x:.1f},{tl_y:.1f})")
    
    def display_contact_info(self, contact, is_out_of_sequence):
        """Display contact information in the message area."""
        contact_id = contact['contact_id']
        timecode = contact.get('timecode', 0)
        player_id = contact.get('player_id')
        player_number = contact.get('player_number', 'N/A')
        player_name = contact.get('player_name', 'N/A')
        contact_type = contact.get('contact_type', 'N/A')
        outcome = contact.get('outcome', 'N/A')
        rating = contact.get('rating')
        
        time_str = self.format_time(timecode)
        rating_str = f", Rating: {rating}" if rating is not None else ""
        
        # Format: Player_id, PlayerName (jersey number), contact type
        player_info = f"Player {player_id}" if player_id else "No Player"
        if player_name and player_name != 'N/A':
            if player_number and player_number != 'N/A':
                player_info = f"{player_name} ({player_number})"
            else:
                player_info = player_name
        elif player_number and player_number != 'N/A':
            player_info = f"Player {player_number}"
        
        if is_out_of_sequence:
            info = f"<span style='color: red;'>[OUT OF SEQUENCE] Contact {contact_id}: {time_str}, {player_info}, {contact_type}, Outcome: {outcome}{rating_str}</span>"
        else:
            info = f"<span style='color: green;'>Contact {contact_id}: {time_str}, {player_info}, {contact_type}, Outcome: {outcome}{rating_str}</span>"
        
        self.message_area.append(info)
        
        # Auto-scroll to bottom
        scrollbar = self.message_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def closeEvent(self, event):
        """Handle window close event."""
        self.contact_check_timer.stop()
        self.media_player.stop()
        event.accept()

