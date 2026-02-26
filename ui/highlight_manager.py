"""
PySide6 UI for Highlight Collection Manager.
Main window for managing video clip collections and generating highlight videos.
"""

import sys
import os
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict
from PySide6.QtWidgets import (
    QMainWindow, QMessageBox, QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QCheckBox, QLabel, QGroupBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QPushButton, QProgressDialog, QDialog,
    QLineEdit, QTextEdit, QComboBox, QAbstractItemView
)
from PySide6.QtCore import Qt, QPoint, QMimeData, Signal
from PySide6.QtGui import QFont, QDrag
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
from PySide6.QtCore import QUrl, QRectF
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView, QSlider

from dbstuff.database import VideoStatsDB
from models.clip_models import VideoClip, ClipCollection
from services.clip_service import ClipService
from services.collection_service import CollectionService
from services.filter_service import FilterService
from services.video_service import VideoService
from utils import get_ffmpeg_path, resource_path, get_user_data_dir


class StarRatingWidget(QWidget):
    """Widget for displaying and editing star ratings (1-5 stars)."""
    
    rating_changed = Signal(int, int, int)  # contact_id, game_id, rating
    
    def __init__(self, contact_id: int, game_id: int, initial_rating: Optional[int] = None, parent=None):
        super().__init__(parent)
        self.contact_id = contact_id
        self.game_id = game_id
        self.current_rating = initial_rating or 0
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        
        self.star_labels = []
        for i in range(5):
            label = QLabel("☆")
            label.setFont(QFont('Arial', 16))
            label.setStyleSheet("color: #ccc;")
            label.mousePressEvent = lambda event, idx=i+1: self._on_star_clicked(idx)
            self.star_labels.append(label)
            layout.addWidget(label)
        
        self.update_display()
    
    def _on_star_clicked(self, rating: int):
        """Handle star click - cycle through ratings."""
        if self.current_rating == rating:
            # Clicking same rating clears it
            self.current_rating = 0
        else:
            self.current_rating = rating
        
        self.update_display()
        self.rating_changed.emit(self.contact_id, self.game_id, self.current_rating)
    
    def update_display(self):
        """Update star display based on current rating."""
        for i, label in enumerate(self.star_labels):
            if i < self.current_rating:
                label.setText("★")
                label.setStyleSheet("color: #ffd700;")
            else:
                label.setText("☆")
                label.setStyleSheet("color: #ccc;")
    
    def set_rating(self, rating: Optional[int]):
        """Set rating programmatically."""
        self.current_rating = rating or 0
        self.update_display()


class DragHandleLabel(QLabel):
    """Custom QLabel for hamburger icon that initiates drag operations."""
    
    def __init__(self, row_index: int, parent_table, parent=None):
        super().__init__(parent)
        self.row_index = row_index
        self.parent_table = parent_table
        self.drag_start_position = None
        self.setText("☰")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFont(QFont('Arial', 14))
        self.setStyleSheet("color: #666;")
    
    def mousePressEvent(self, event):
        """Start drag operation when clicking on hamburger icon."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_position = event.position().toPoint()
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Handle mouse move to initiate drag."""
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        
        if self.drag_start_position is None:
            return
        
        # Check if mouse has moved enough to start drag
        if (event.position().toPoint() - self.drag_start_position).manhattanLength() < 5:
            return
        
        # Create drag object
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(str(self.row_index))
        drag.setMimeData(mime_data)
        
        pixmap = self.grab()
        drag.setPixmap(pixmap)
        drag.setHotSpot(event.position().toPoint())
        
        drag.exec(Qt.DropAction.MoveAction)
        self.drag_start_position = None


class DraggableClipTable(QTableWidget):
    """Custom QTableWidget that handles row drag-and-drop for clips."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
    
    def dragEnterEvent(self, event):
        """Handle drag enter event."""
        if event.mimeData().hasText():
            try:
                row_index = int(event.mimeData().text())
                if 0 <= row_index < self.rowCount():
                    event.acceptProposedAction()
                    return
            except ValueError:
                pass
        event.ignore()
    
    def dragMoveEvent(self, event):
        """Handle drag move event."""
        if event.mimeData().hasText():
            try:
                row_index = int(event.mimeData().text())
                if 0 <= row_index < self.rowCount():
                    event.acceptProposedAction()
                    return
            except ValueError:
                pass
        event.ignore()
    
    def dropEvent(self, event):
        """Handle drop event to reorder rows."""
        if not event.mimeData().hasText():
            event.ignore()
            return
        
        try:
            source_row = int(event.mimeData().text())
        except ValueError:
            event.ignore()
            return
        
        drop_position = event.position().toPoint()
        target_row = self.rowAt(drop_position.y())
        
        if target_row < 0:
            target_row = self.rowCount() - 1
        
        if source_row == target_row:
            event.acceptProposedAction()
            return
        
        self.move_row(source_row, target_row)
        
        # Update hamburger labels with new row indices
        for row in range(self.rowCount()):
            hamburger_widget = self.cellWidget(row, 0)
            if isinstance(hamburger_widget, DragHandleLabel):
                hamburger_widget.row_index = row
        
        # Notify parent of reorder
        if hasattr(self.parent(), 'on_clip_reordered'):
            self.parent().on_clip_reordered()
        
        event.acceptProposedAction()
    
    def move_row(self, source_row: int, target_row: int):
        """Move a row from source_row to target_row."""
        if source_row == target_row:
            return
        
        # Store all data from source row
        source_data = {}
        for col in range(self.columnCount()):
            source_item = self.item(source_row, col)
            if source_item:
                source_data[col] = ('item', QTableWidgetItem(source_item))
            
            source_widget = self.cellWidget(source_row, col)
            if source_widget:
                if isinstance(source_widget, QCheckBox):
                    source_data[col] = ('checkbox', {
                        'checked': source_widget.isChecked(),
                        'clip_data': source_widget.property("clip_data")
                    })
                elif isinstance(source_widget, DragHandleLabel):
                    source_data[col] = ('hamburger', None)
                elif isinstance(source_widget, StarRatingWidget):
                    source_data[col] = ('star_rating', {
                        'contact_id': source_widget.contact_id,
                        'game_id': source_widget.game_id,
                        'rating': source_widget.current_rating
                    })
                elif isinstance(source_widget, QPushButton):
                    btn_text = source_widget.text()
                    widget_data = {
                        'text': btn_text,
                        'font': source_widget.font(),
                        'timecode_ms': source_widget.property("timecode_ms"),
                        'video_path': source_widget.property("video_path")
                    }
                    source_data[col] = ('button', widget_data)
        
        # Remove source row
        self.removeRow(source_row)
        
        # Adjust target_row if needed
        if source_row < target_row:
            insert_row = target_row - 1
        else:
            insert_row = target_row
        
        # Insert new row
        self.insertRow(insert_row)
        
        # Copy data to new row
        for col, (data_type, data) in source_data.items():
            if data_type == 'item':
                self.setItem(insert_row, col, data)
            elif data_type == 'checkbox':
                new_checkbox = QCheckBox()
                new_checkbox.setChecked(data['checked'])
                new_checkbox.setProperty("clip_data", data['clip_data'])
                self.setCellWidget(insert_row, col, new_checkbox)
            elif data_type == 'hamburger':
                new_label = DragHandleLabel(insert_row, self)
                self.setCellWidget(insert_row, col, new_label)
            elif data_type == 'star_rating':
                new_widget = StarRatingWidget(data['contact_id'], data['game_id'], data['rating'], self)
                if hasattr(self.parent(), 'on_star_rating_changed'):
                    new_widget.rating_changed.connect(self.parent().on_star_rating_changed)
                self.setCellWidget(insert_row, col, new_widget)
            elif data_type == 'button':
                new_btn = QPushButton(data['text'])
                new_btn.setFont(data['font'])
                if data['text'] == "View":
                    new_btn.setProperty("timecode_ms", data['timecode_ms'])
                    new_btn.setProperty("video_path", data['video_path'])
                    new_btn.clicked.connect(lambda checked=False, tc=data['timecode_ms'], vp=data['video_path']: 
                                         self.parent().open_video_player(vp, tc))
                self.setCellWidget(insert_row, col, new_btn)


class VideoPlayerWindow(QMainWindow):
    """Separate window for video playback."""
    
    def __init__(self, video_path: str, contact_timecode_ms: int = 0, contact_info: str = "", parent=None, is_clip: bool = False):
        super().__init__(parent)
        window_title = f"Video Player - {contact_info}" if contact_info else "Video Player"
        self.setWindowTitle(window_title)
        self.resize(1000, 600)
        
        self.is_clip = is_clip
        self.contact_timecode_ms = contact_timecode_ms if contact_timecode_ms else 0
        
        if is_clip:
            # For extracted clips, clip starts at 0:00 and is 6 seconds long
            self.start_time_ms = 0
            self.end_time_ms = 6000
        else:
            # For full videos, seek to 3 seconds before contact
            self.start_time_ms = max(0, self.contact_timecode_ms - 3000)
            self.end_time_ms = self.contact_timecode_ms + 3000
        
        self.auto_started = False
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        self.scene = QGraphicsScene(0, 0, 1000, 600)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        layout.addWidget(self.view)
        
        controls_layout = QHBoxLayout()
        
        self.play_pause_btn = QPushButton("Pause")
        self.play_pause_btn.setFont(QFont('Arial', 10))
        self.play_pause_btn.clicked.connect(self.toggle_play_pause)
        controls_layout.addWidget(self.play_pause_btn)
        
        self.video_slider = QSlider(Qt.Orientation.Horizontal)
        self.video_slider.sliderMoved.connect(self.seek_video)
        controls_layout.addWidget(self.video_slider)
        
        self.time_label = QLabel("00:00:00 / 00:00:00")
        self.time_label.setFont(QFont('Arial', 10))
        controls_layout.addWidget(self.time_label)
        
        contact_time_formatted = self.format_time(contact_timecode_ms)
        self.contact_indicator = QLabel(f"Contact @ {contact_time_formatted}")
        self.contact_indicator.setFont(QFont('Arial', 10, QFont.Weight.Bold))
        self.contact_indicator.setStyleSheet("color: red;")
        controls_layout.addWidget(self.contact_indicator)
        
        layout.addLayout(controls_layout)
        
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        
        self.video_item = QGraphicsVideoItem()
        self.video_item.setSize(QRectF(0, 0, 1000, 600).size())
        self.scene.addItem(self.video_item)
        
        self.media_player.setVideoOutput(self.video_item)
        self.media_player.positionChanged.connect(self.update_position)
        self.media_player.durationChanged.connect(self.update_duration)
        
        self.media_player.setSource(QUrl.fromLocalFile(video_path))
        self.media_player.mediaStatusChanged.connect(self.on_media_status_changed)
    
    def on_media_status_changed(self, status):
        """Handle media status changes."""
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            if not self.is_clip:
                # Only seek for full videos, clips start at 0:00
                self.media_player.setPosition(self.start_time_ms)
            self.media_player.play()
            self.play_pause_btn.setText("Pause")
            self.auto_started = True
            self.media_player.mediaStatusChanged.disconnect(self.on_media_status_changed)
    
    def toggle_play_pause(self):
        """Toggle between play and pause."""
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
            self.play_pause_btn.setText("Play")
        else:
            self.media_player.play()
            self.play_pause_btn.setText("Pause")
    
    def seek_video(self, position):
        """Seek to a specific position."""
        self.media_player.setPosition(position)
    
    def update_position(self, position):
        """Update the slider position."""
        if not self.video_slider.isSliderDown():
            self.video_slider.setValue(position)
        
        current_time = self.format_time(position)
        if self.is_clip:
            # For clips, duration is always 6 seconds
            total_time = self.format_time(6000)
        else:
            duration = self.media_player.duration()
            total_time = self.format_time(duration)
        self.time_label.setText(f"{current_time} / {total_time}")
        
        if not self.is_clip:
            # Only show contact indicator for full videos
            if abs(position - self.contact_timecode_ms) < 500:
                self.contact_indicator.setStyleSheet("color: white; background-color: red; padding: 2px;")
            else:
                self.contact_indicator.setStyleSheet("color: red;")
        
        # Auto-pause at end time
        if position >= self.end_time_ms and self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
            self.play_pause_btn.setText("Play")
    
    def update_duration(self, duration):
        """Update the slider range."""
        if self.is_clip:
            # For clips, duration is always 6 seconds
            self.video_slider.setRange(0, 6000)
        else:
            self.video_slider.setRange(0, duration)
    
    def format_time(self, ms):
        """Format milliseconds to HH:MM:SS."""
        total_seconds = ms // 1000
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


class HighlightCollectionManager(QMainWindow):
    """Main window for highlight collection manager."""
    
    def __init__(self, db: VideoStatsDB, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Highlight Collection Manager")
        self.resize(1400, 900)
        
        self.db = db
        self.clip_service = ClipService(db)
        self.collection_service = CollectionService(db)
        self.filter_service = FilterService()
        self.video_service = VideoService()
        
        self.selected_game_ids = []
        self.current_clips = []
        self.current_collection = None
        self.team_us_id = None
        self.team_them_id = None
        self.games_data = {}  # Store game data for team IDs
        
        # Setup temp clip directory and caching for efficient clip retrieval
        self.process_id = os.getpid()
        try:
            self.user_id = os.getlogin() if hasattr(os, 'getlogin') else str(os.getuid())
        except (OSError, AttributeError):
            self.user_id = 'unknown'
        
        self.temp_clip_dir = get_user_data_dir() / "temp_clips" / f"process_{self.process_id}"
        self.temp_clip_dir.mkdir(parents=True, exist_ok=True)
        self.temp_clip_files = []  # Track all temp clip files for cleanup
        self.clip_cache = {}  # Cache: (video_path, timecode_ms) -> temp_file_path
        
        # Setup UI
        self.setup_ui()
        self.populate_games_list()
        self.populate_collections_list()
    
    def setup_ui(self):
        """Setup the main UI."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Left panel: Filters and controls
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(5, 5, 5, 5)
        left_layout.setSpacing(10)
        
        # Game selection
        game_group = QGroupBox("Select Games (Multi-select)")
        game_layout = QVBoxLayout(game_group)
        self.game_list_widget = QListWidget()
        self.game_list_widget.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        # Make it 70% taller (set fixed height)
        self.game_list_widget.setMinimumHeight(250)
        game_layout.addWidget(self.game_list_widget)
        left_layout.addWidget(game_group)
        
        # Collection management
        collection_group = QGroupBox("Collections")
        collection_layout = QVBoxLayout(collection_group)
        
        self.collection_combo = QComboBox()
        collection_layout.addWidget(QLabel("Current Collection:"))
        collection_layout.addWidget(self.collection_combo)
        
        collection_buttons = QHBoxLayout()
        self.new_collection_btn = QPushButton("New")
        self.save_collection_btn = QPushButton("Save")
        self.load_collection_btn = QPushButton("Load")
        self.delete_collection_btn = QPushButton("Delete")
        collection_buttons.addWidget(self.new_collection_btn)
        collection_buttons.addWidget(self.save_collection_btn)
        collection_buttons.addWidget(self.load_collection_btn)
        collection_buttons.addWidget(self.delete_collection_btn)
        collection_layout.addLayout(collection_buttons)
        
        left_layout.addWidget(collection_group)
        
        # Filters (reuse from view_paths.py structure)
        self.setup_filters(left_layout)
        
        # Display button
        self.display_btn = QPushButton("Apply Filters")
        self.display_btn.setFont(QFont('Arial', 12, QFont.Weight.Bold))
        self.display_btn.clicked.connect(self.on_display_clips)
        left_layout.addWidget(self.display_btn)
        
        left_layout.addStretch()
        
        main_layout.addWidget(left_panel, 1)
        
        # Right panel: Clip table
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(5, 5, 5, 5)
        right_layout.setSpacing(10)
        
        # Clip table
        self.clip_table = DraggableClipTable()
        self.clip_table.setColumnCount(11)  # 11 columns including Rating and View button
        self.clip_table.setHorizontalHeaderLabels([
            "",  # Column 0: Drag handle
            "",  # Column 1: Checkbox
            "Game",  # Column 2
            "Stars",  # Column 3
            "Rally",  # Column 4
            "Seq",  # Column 5
            "Player",  # Column 6
            "Type",  # Column 7
            "Rating",  # Column 8: Rating (only for Receive)
            "Outcome",  # Column 9
            "View"  # Column 10: View button
        ])
        self.clip_table.horizontalHeader().setStretchLastSection(True)
        self.clip_table.setAlternatingRowColors(True)
        right_layout.addWidget(self.clip_table)
        
        # Highlight video controls
        highlight_group = QGroupBox("Highlight Video")
        highlight_layout = QVBoxLayout(highlight_group)
        
        highlight_buttons = QHBoxLayout()
        self.create_highlight_btn = QPushButton("Create Highlight Video")
        self.include_title_checkbox = QCheckBox("Include Title Screen")
        self.configure_title_btn = QPushButton("Configure Title Screen")
        highlight_buttons.addWidget(self.create_highlight_btn)
        highlight_buttons.addWidget(self.include_title_checkbox)
        highlight_buttons.addWidget(self.configure_title_btn)
        highlight_layout.addLayout(highlight_buttons)
        
        right_layout.addWidget(highlight_group)
        
        main_layout.addWidget(right_panel, 2)
        
        # Connect signals
        self.game_list_widget.itemSelectionChanged.connect(self.on_games_selected)
        self.new_collection_btn.clicked.connect(self.on_new_collection)
        self.save_collection_btn.clicked.connect(self.on_save_collection)
        self.load_collection_btn.clicked.connect(self.on_load_collection)
        self.delete_collection_btn.clicked.connect(self.on_delete_collection)
        self.create_highlight_btn.clicked.connect(self.on_create_highlight)
        self.configure_title_btn.clicked.connect(self.on_configure_title)
    
    def setup_filters(self, parent_layout):
        """Setup filter widgets."""
        filters_group = QGroupBox("Filters")
        filters_layout = QVBoxLayout(filters_group)
        
        # Player filter - moved to top, in its own groupbox
        player_group = QGroupBox("Players")
        player_group_layout = QVBoxLayout(player_group)
        self.player_list_widget = QListWidget()
        self.player_list_widget.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        # Set height to show ~4-5 players with scrolling
        self.player_list_widget.setFixedHeight(120)  # ~30px per item * 4 = 120px
        player_group_layout.addWidget(self.player_list_widget)
        filters_layout.addWidget(player_group)
        
        # Contact types - 3 columns with tight spacing
        contact_group = QGroupBox("Contact Types")
        contact_layout = QVBoxLayout(contact_group)
        contact_layout.setContentsMargins(5, 5, 5, 5)
        contact_layout.setSpacing(2)
        contact_grid = QWidget()
        contact_grid_layout = QHBoxLayout(contact_grid)
        contact_grid_layout.setContentsMargins(0, 0, 0, 0)
        contact_grid_layout.setSpacing(5)
        
        # Create 3 columns
        col1 = QVBoxLayout()
        col1.setSpacing(1)
        col2 = QVBoxLayout()
        col2.setSpacing(1)
        col3 = QVBoxLayout()
        col3.setSpacing(1)
        
        self.contact_checkboxes = {}
        contact_types = ['serve', 'receive', 'pass', 'set', 'attack', 'freeball', 'block', 'down']
        for i, ct in enumerate(contact_types):
            cb = QCheckBox(ct.capitalize())
            cb.setChecked(False)  # Default to unchecked
            self.contact_checkboxes[ct] = cb
            # Distribute across 3 columns
            if i < 3:
                col1.addWidget(cb)
            elif i < 6:
                col2.addWidget(cb)
            else:
                col3.addWidget(cb)
        
        contact_grid_layout.addLayout(col1)
        contact_grid_layout.addLayout(col2)
        contact_grid_layout.addLayout(col3)
        contact_layout.addWidget(contact_grid)
        filters_layout.addWidget(contact_group)
        
        # Outcomes - 4 columns with tight spacing
        outcome_group = QGroupBox("Outcomes")
        outcome_layout = QVBoxLayout(outcome_group)
        outcome_layout.setContentsMargins(5, 5, 5, 5)
        outcome_layout.setSpacing(2)
        outcome_grid = QWidget()
        outcome_grid_layout = QHBoxLayout(outcome_grid)
        outcome_grid_layout.setContentsMargins(0, 0, 0, 0)
        outcome_grid_layout.setSpacing(5)
        
        # Create 4 columns
        col1 = QVBoxLayout()
        col1.setSpacing(1)
        col2 = QVBoxLayout()
        col2.setSpacing(1)
        col3 = QVBoxLayout()
        col3.setSpacing(1)
        col4 = QVBoxLayout()
        col4.setSpacing(1)
        
        self.outcome_checkboxes = {}
        outcomes = ['continue', 'ace', 'kill', 'stuff', 'error', 'down', 'assist']
        for i, oc in enumerate(outcomes):
            cb = QCheckBox(oc.capitalize())
            cb.setChecked(False)  # Default to unchecked
            self.outcome_checkboxes[oc] = cb
            # Distribute across 4 columns
            if i < 2:
                col1.addWidget(cb)
            elif i < 4:
                col2.addWidget(cb)
            elif i < 6:
                col3.addWidget(cb)
            else:
                col4.addWidget(cb)
        
        outcome_grid_layout.addLayout(col1)
        outcome_grid_layout.addLayout(col2)
        outcome_grid_layout.addLayout(col3)
        outcome_grid_layout.addLayout(col4)
        outcome_layout.addWidget(outcome_grid)
        filters_layout.addWidget(outcome_group)
        
        # Rating filter
        rating_group = QGroupBox("Ratings Filter")
        rating_layout = QHBoxLayout(rating_group)
        self.rating_checkboxes = {}
        for rating in [0, 1, 2, 3]:
            cb = QCheckBox(str(rating))
            cb.setFont(QFont('Arial', 9))
            cb.setChecked(False)  # Default to unchecked
            self.rating_checkboxes[rating] = cb
            rating_layout.addWidget(cb)
        rating_layout.addStretch()
        filters_layout.addWidget(rating_group)
        
        # Team filters with tight spacing
        team_group = QGroupBox("Team Filters")
        team_layout = QVBoxLayout(team_group)
        team_layout.setContentsMargins(5, 5, 5, 5)
        team_layout.setSpacing(1)
        self.team_filter_checkbox_a = QCheckBox("Show Team A")
        self.team_filter_checkbox_a.setChecked(True)
        self.team_filter_checkbox_b = QCheckBox("Show Team B")
        self.team_filter_checkbox_b.setChecked(True)
        team_layout.addWidget(self.team_filter_checkbox_a)
        team_layout.addWidget(self.team_filter_checkbox_b)
        filters_layout.addWidget(team_group)
        
        parent_layout.addWidget(filters_group)
    
    def populate_games_list(self):
        """Populate the games list widget."""
        games = self.clip_service.get_games_list()
        self.game_list_widget.clear()
        self.games_data = {}
        
        for game in games:
            date_str = str(game['game_date'])[:10] if game['game_date'] else "Unknown"
            item_text = f"Game {game['game_id']}: {game['game_alias']} ({date_str})"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, game['game_id'])
            self.game_list_widget.addItem(item)
            # Store game data
            self.games_data[game['game_id']] = game
    
    def populate_collections_list(self):
        """Populate the collections combo box."""
        collections = self.collection_service.list_collections()
        self.collection_combo.clear()
        self.collection_combo.addItem("-- No Collection --", None)
        
        for collection in collections:
            self.collection_combo.addItem(collection.name, collection.collection_id)
    
    def on_games_selected(self):
        """Handle game selection change."""
        selected_items = self.game_list_widget.selectedItems()
        self.selected_game_ids = [item.data(Qt.UserRole) for item in selected_items]
        
        # Set team IDs from first selected game (for filter compatibility)
        if self.selected_game_ids and self.selected_game_ids[0] in self.games_data:
            first_game = self.games_data[self.selected_game_ids[0]]
            self.team_us_id = first_game['team_us_id']
            self.team_them_id = first_game['team_them_id']
        
        # Populate player list for selected games
        self.populate_player_list()
        print(f"Selected games: {self.selected_game_ids}")
    
    def populate_player_list(self):
        """Populate player list for selected games."""
        if not self.selected_game_ids or not self.team_us_id:
            return
        
        self.player_list_widget.clear()
        
        # Get players from all selected games
        all_players = set()
        for game_id in self.selected_game_ids:
            players = self.db.game_players.get_game_players(game_id, self.team_us_id)
            for player in players:
                player_id = player['player_id']
                player_number = player['player_number']
                player_name = player.get('name')
                all_players.add((player_id, player_number, player_name))
        
        # Add "All Players" option (don't auto-select - user must choose)
        all_item = QListWidgetItem("All Players")
        all_item.setData(Qt.UserRole, None)
        self.player_list_widget.addItem(all_item)
        # Don't auto-select - let user explicitly choose
        
        # Add players
        for player_id, player_number, player_name in sorted(all_players, key=lambda x: (x[2] or "").lower()):
            display_text = f"{player_name or 'Unknown'} ({player_number})" if player_name else f"Player ({player_number})"
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, player_id)
            self.player_list_widget.addItem(item)
    
    def on_display_clips(self):
        """Display clips based on current filters."""
        if not self.selected_game_ids:
            QMessageBox.warning(self, "No Games Selected", "Please select at least one game.")
            return
        
        # Get filters from UI
        filters = self.filter_service.parse_filters_from_ui(self)
        
        # Get clips
        self.current_clips = self.clip_service.get_filtered_clips(self.selected_game_ids, filters)
        
        # Populate table
        self.populate_clip_table()
    
    def populate_clip_table(self):
        """Populate the clip table with current clips."""
        self.clip_table.setRowCount(len(self.current_clips))
        self.clip_table.clearContents()
        
        for row_idx, clip in enumerate(self.current_clips):
            # Column 0: Drag handle
            hamburger = DragHandleLabel(row_idx, self.clip_table)
            self.clip_table.setCellWidget(row_idx, 0, hamburger)
            
            # Column 1: Checkbox
            checkbox = QCheckBox()
            checkbox.setProperty("clip_data", clip.to_dict())
            self.clip_table.setCellWidget(row_idx, 1, checkbox)
            
            # Column 2: Game alias
            self.clip_table.setItem(row_idx, 2, QTableWidgetItem(clip.game_alias))
            
            # Column 3: Star rating
            star_widget = StarRatingWidget(clip.contact_id, clip.game_id, clip.star_rating, self.clip_table)
            star_widget.rating_changed.connect(self.on_star_rating_changed)
            self.clip_table.setCellWidget(row_idx, 3, star_widget)
            
            # Column 4: Rally
            self.clip_table.setItem(row_idx, 4, QTableWidgetItem(str(clip.rally_number)))
            
            # Column 5: Sequence
            self.clip_table.setItem(row_idx, 5, QTableWidgetItem(str(clip.sequence_number)))
            
            # Column 6: Player
            player_text = f"{clip.player_name or 'Unknown'} ({clip.player_number or 'N/A'})"
            self.clip_table.setItem(row_idx, 6, QTableWidgetItem(player_text))
            
            # Column 7: Type
            self.clip_table.setItem(row_idx, 7, QTableWidgetItem(clip.contact_type))
            
            # Column 8: Rating (only show for Receive contact type)
            if clip.contact_type == 'receive' and clip.rating is not None:
                rating_item = QTableWidgetItem(str(clip.rating))
            else:
                rating_item = QTableWidgetItem("")
            self.clip_table.setItem(row_idx, 8, rating_item)
            
            # Column 9: Outcome
            self.clip_table.setItem(row_idx, 9, QTableWidgetItem(clip.outcome))
            
            # Column 10: View button
            view_btn = QPushButton("View")
            view_btn.setProperty("timecode_ms", clip.timecode_ms)
            view_btn.setProperty("video_path", clip.video_file_path)
            view_btn.clicked.connect(lambda checked=False, vp=clip.video_file_path, tc=clip.timecode_ms: 
                                   self.open_video_player(vp, tc))
            self.clip_table.setCellWidget(row_idx, 10, view_btn)
        
        # Resize columns
        self.clip_table.resizeColumnsToContents()
    
    def on_star_rating_changed(self, contact_id: int, game_id: int, rating: int):
        """Handle star rating change."""
        self.clip_service.update_clip_star_rating(contact_id, game_id, rating)
        # Update clip in current_clips
        for clip in self.current_clips:
            if clip.contact_id == contact_id and clip.game_id == game_id:
                clip.star_rating = rating
                break
    
    def on_clip_reordered(self):
        """Handle clip table reordering."""
        # Update order_index in current_clips
        for row in range(self.clip_table.rowCount()):
            checkbox = self.clip_table.cellWidget(row, 1)
            if checkbox:
                clip_data = checkbox.property("clip_data")
                if clip_data:
                    for clip in self.current_clips:
                        if (clip.contact_id == clip_data['contact_id'] and 
                            clip.game_id == clip_data['game_id']):
                            clip.order_index = row
                            break
    
    def on_view_selected_clip(self):
        """View the currently selected clip in the table."""
        current_row = self.clip_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a clip from the table.")
            return
        
        # Get clip data from checkbox
        checkbox = self.clip_table.cellWidget(current_row, 1)
        if not checkbox:
            QMessageBox.warning(self, "Error", "Could not find clip data.")
            return
        
        clip_data = checkbox.property("clip_data")
        if not clip_data:
            QMessageBox.warning(self, "Error", "Clip data not found.")
            return
        
        video_path = clip_data.get('video_file_path')
        timecode_ms = clip_data.get('timecode_ms', 0)
        
        self.open_video_player(video_path, timecode_ms)
    
    def _get_cache_key(self, video_path: str, timecode_ms: int) -> tuple:
        """Generate unique cache key for a clip."""
        return (video_path, timecode_ms)
    
    def _get_temp_filename(self, video_path: str, timecode_ms: int) -> str:
        """Generate unique temp filename for this process."""
        # Create hash of video path for uniqueness
        path_hash = hashlib.md5(video_path.encode()).hexdigest()[:8]
        return f"clip_{self.process_id}_{self.user_id}_{path_hash}_{timecode_ms}.mp4"
    
    def _extract_clip(self, video_path: str, timecode_ms: int, temp_file: Path) -> bool:
        """Extract 6-second clip with progress dialog."""
        start_ms = max(0, timecode_ms - 3000)
        duration_ms = 6000
        
        # Show progress dialog
        progress = QProgressDialog("Extracting video clip...", "Cancel", 0, 0, self)
        progress.setWindowTitle("Extracting Clip")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setCancelButton(None)  # No cancel for now
        progress.show()
        QApplication.processEvents()
        
        # Extract clip using VideoService
        success = self.video_service.extract_clip(
            video_path,
            start_ms,
            duration_ms,
            str(temp_file)
        )
        
        progress.close()
        return success
    
    def open_video_player(self, video_path: str, timecode_ms: int):
        """Open video player window with efficient clip extraction."""
        if not video_path or not Path(video_path).exists():
            QMessageBox.warning(self, "Video Not Found", f"Video file not found:\n{video_path}")
            return
        
        cache_key = self._get_cache_key(video_path, timecode_ms)
        
        # Check cache first
        if cache_key in self.clip_cache:
            temp_file = self.clip_cache[cache_key]
            if Path(temp_file).exists():
                # Reuse existing clip - instant playback
                player = VideoPlayerWindow(str(temp_file), 0, "", self, is_clip=True)
                player.show()
                return
        
        # Extract new clip
        temp_filename = self._get_temp_filename(video_path, timecode_ms)
        temp_file = self.temp_clip_dir / temp_filename
        
        # Extract clip (with progress)
        if self._extract_clip(video_path, timecode_ms, temp_file):
            # Add to cache and tracking
            self.clip_cache[cache_key] = str(temp_file)
            self.temp_clip_files.append(str(temp_file))
            
            # Open player with extracted clip
            player = VideoPlayerWindow(str(temp_file), 0, "", self, is_clip=True)
            player.show()
        else:
            QMessageBox.warning(self, "Error", "Failed to extract video clip. Falling back to full video.")
            # Fallback to original behavior
            player = VideoPlayerWindow(video_path, timecode_ms, "", self)
            player.show()
    
    def on_new_collection(self):
        """Create a new collection."""
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "New Collection", "Collection name:")
        if ok and name:
            description, ok2 = QInputDialog.getText(self, "New Collection", "Description (optional):", 
                                                   text="")
            desc = description if ok2 else None
            collection = self.collection_service.create_collection(name, desc)
            self.current_collection = collection
            self.populate_collections_list()
            # Select the new collection
            index = self.collection_combo.findData(collection.collection_id)
            if index >= 0:
                self.collection_combo.setCurrentIndex(index)
    
    def on_save_collection(self):
        """Save current clips to collection."""
        if not self.current_collection:
            QMessageBox.warning(self, "No Collection", "Please create or load a collection first.")
            return
        
        # Get selected clips (checked checkboxes)
        selected_clips = []
        for row in range(self.clip_table.rowCount()):
            checkbox = self.clip_table.cellWidget(row, 1)
            if checkbox and checkbox.isChecked():
                clip_data = checkbox.property("clip_data")
                if clip_data:
                    # Find matching clip
                    for clip in self.current_clips:
                        if (clip.contact_id == clip_data['contact_id'] and 
                            clip.game_id == clip_data['game_id']):
                            clip.order_index = row
                            selected_clips.append(clip)
                            break
        
        if not selected_clips:
            QMessageBox.warning(self, "No Clips Selected", "Please select clips to save.")
            return
        
        try:
            collection_id = self.collection_service.save_collection(self.current_collection, selected_clips)
            self.current_collection.collection_id = collection_id
            QMessageBox.information(self, "Saved", f"Collection '{self.current_collection.name}' saved with {len(selected_clips)} clips.")
            self.populate_collections_list()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save collection:\n{str(e)}")
    
    def on_load_collection(self):
        """Load a collection."""
        collection_id = self.collection_combo.currentData()
        if not collection_id:
            QMessageBox.warning(self, "No Collection", "Please select a collection to load.")
            return
        
        try:
            collection, clips = self.collection_service.load_collection(collection_id)
            self.current_collection = collection
            self.current_clips = clips
            self.populate_clip_table()
            QMessageBox.information(self, "Loaded", f"Loaded collection '{collection.name}' with {len(clips)} clips.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load collection:\n{str(e)}")
    
    def on_delete_collection(self):
        """Delete a collection."""
        collection_id = self.collection_combo.currentData()
        if not collection_id:
            QMessageBox.warning(self, "No Collection", "Please select a collection to delete.")
            return
        
        reply = QMessageBox.question(self, "Delete Collection", 
                                    "Are you sure you want to delete this collection%s",
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if self.collection_service.delete_collection(collection_id):
                QMessageBox.information(self, "Deleted", "Collection deleted successfully.")
                self.current_collection = None
                self.populate_collections_list()
            else:
                QMessageBox.warning(self, "Error", "Failed to delete collection.")
    
    def on_create_highlight(self):
        """Create highlight video from selected clips."""
        # Get selected clips
        selected_clips = []
        for row in range(self.clip_table.rowCount()):
            checkbox = self.clip_table.cellWidget(row, 1)
            if checkbox and checkbox.isChecked():
                clip_data = checkbox.property("clip_data")
                if clip_data:
                    for clip in self.current_clips:
                        if (clip.contact_id == clip_data['contact_id'] and 
                            clip.game_id == clip_data['game_id']):
                            selected_clips.append(clip)
                            break
        
        if not selected_clips:
            QMessageBox.warning(self, "No Selection", "Please select at least one clip.")
            return
        
        # Create output directory
        output_dir = Path("video_clips")
        output_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        highlight_filename = f"highlight_{timestamp}.mp4"
        
        # Show progress
        progress = QProgressDialog("Creating highlight video...", "Cancel", 0, len(selected_clips) + 1, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setCancelButton(None)
        progress.show()
        
        def progress_callback(current, total):
            progress.setValue(current)
            QApplication.processEvents()
        
        # Create highlight
        include_title = self.include_title_checkbox.isChecked()
        title_path = "output.mp4" if include_title else None
        
        result_path = self.video_service.create_highlight_from_clips(
            selected_clips,
            output_dir,
            highlight_filename,
            include_title,
            title_path,
            progress_callback
        )
        
        progress.close()
        
        if result_path:
            QMessageBox.information(self, "Success", 
                                  f"Highlight video created:\n{result_path}")
        else:
            QMessageBox.warning(self, "Error", "Failed to create highlight video.")
    
    def on_configure_title(self):
        """Open title screen creator."""
        try:
            from highlight_title_creator import MovieMakerGUI
            title_window = MovieMakerGUI()
            title_window.show()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to open title creator:\n{str(e)}")
    
    def closeEvent(self, event):
        """Clean up all temp clip files when window closes."""
        for temp_file in self.temp_clip_files:
            try:
                if Path(temp_file).exists():
                    Path(temp_file).unlink()
            except Exception as e:
                print(f"Warning: Could not delete temp file {temp_file}: {e}")
        
        # Try to remove temp directory if empty
        try:
            if self.temp_clip_dir.exists() and not any(self.temp_clip_dir.iterdir()):
                self.temp_clip_dir.rmdir()
        except Exception:
            pass
        
        event.accept()


def main():
    """Main entry point."""
    app = QApplication(sys.argv)
    
    # Initialize database
    db = VideoStatsDB()
    db.initialize_database()
    db.connect()
    
    # Create collection tables if they don't exist
    db.create_collection_tables()
    
    # Create and show window
    window = HighlightCollectionManager(db)
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

