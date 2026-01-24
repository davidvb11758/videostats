"""
Dialog for listing all games with video playback and delete functionality.
"""

import sys
from pathlib import Path
from datetime import datetime
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, 
    QListWidgetItem, QLabel, QMessageBox, QWidget, QGraphicsScene, 
    QGraphicsView, QSlider
)
from PySide6.QtCore import Qt, QUrl, QRectF
from PySide6.QtGui import QFont, QPainter
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
from dbstuff.database import VideoStatsDB


class ListGamesDialog(QDialog):
    """Dialog to list all games, view videos, and delete games."""
    
    def __init__(self, db: VideoStatsDB, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("List All Games")
        self.setMinimumSize(1200, 700)
        
        # Create main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Create horizontal layout for list and video
        content_layout = QHBoxLayout()
        
        # Left side: Game list
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        list_label = QLabel("Games:")
        list_label.setFont(QFont('Arial', 12, QFont.Weight.Bold))
        left_layout.addWidget(list_label)
        
        self.game_list = QListWidget()
        self.game_list.setMinimumWidth(300)
        self.game_list.itemSelectionChanged.connect(self.on_game_selected)
        left_layout.addWidget(self.game_list)
        
        # Delete button
        self.delete_btn = QPushButton("Delete Selected Game")
        self.delete_btn.setFont(QFont('Arial', 10))
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
        """)
        self.delete_btn.clicked.connect(self.delete_selected_game)
        self.delete_btn.setEnabled(False)
        left_layout.addWidget(self.delete_btn)
        
        content_layout.addWidget(left_widget)
        
        # Right side: Video player
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        video_label = QLabel("Video Player:")
        video_label.setFont(QFont('Arial', 12, QFont.Weight.Bold))
        right_layout.addWidget(video_label)
        
        # Create graphics scene and view for video
        self.scene = QGraphicsScene(0, 0, 800, 450)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setMinimumSize(800, 450)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        right_layout.addWidget(self.view)
        
        # Video controls layout
        controls_layout = QHBoxLayout()
        
        self.play_pause_btn = QPushButton("Play")
        self.play_pause_btn.setFont(QFont('Arial', 10))
        self.play_pause_btn.setEnabled(False)
        self.play_pause_btn.clicked.connect(self.toggle_play_pause)
        controls_layout.addWidget(self.play_pause_btn)
        
        self.video_slider = QSlider(Qt.Orientation.Horizontal)
        self.video_slider.setEnabled(False)
        self.video_slider.sliderMoved.connect(self.seek_video)
        controls_layout.addWidget(self.video_slider)
        
        self.time_label = QLabel("00:00:00 / 00:00:00")
        self.time_label.setFont(QFont('Arial', 10))
        controls_layout.addWidget(self.time_label)
        
        right_layout.addLayout(controls_layout)
        
        content_layout.addWidget(right_widget)
        
        main_layout.addLayout(content_layout)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.setFont(QFont('Arial', 10))
        close_btn.clicked.connect(self.accept)
        main_layout.addWidget(close_btn)
        
        # Create media player
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        
        # Create video item
        self.video_item = QGraphicsVideoItem()
        self.video_item.setSize(QRectF(0, 0, 800, 450).size())
        self.scene.addItem(self.video_item)
        
        # Set video output
        self.media_player.setVideoOutput(self.video_item)
        
        # Connect signals
        self.media_player.positionChanged.connect(self.update_position)
        self.media_player.durationChanged.connect(self.update_duration)
        self.media_player.mediaStatusChanged.connect(self.on_media_status_changed)
        
        # Store current game info
        self.current_game_id = None
        self.current_video_path = None
        
        # Load games
        self.load_games()
    
    def load_games(self):
        """Load all games from the database into the list."""
        if not self.db.conn:
            self.db.connect()
        
        games = self.db.games.get_all_games_with_teams()
        
        self.game_list.clear()
        
        # Collect games with their display text for sorting
        game_items = []
        
        for game in games:
            game_id = game['game_id']
            game_date = game['game_date']
            team_us_name = game['team_us_name']
            team_them_name = game['team_them_name']
            video_file_path = game.get('video_file_path')
            notes = game.get('notes')
            is_ended = game.get('is_ended')
            
            # Format game date to show only the date (YYYY-MM-DD)
            date_display = game_date
            if game_date:
                try:
                    # Try parsing ISO format
                    if isinstance(game_date, str):
                        if 'T' in game_date:
                            date_obj = datetime.fromisoformat(game_date.replace(' ', 'T'))
                        else:
                            # Try parsing space-separated format
                            date_obj = datetime.strptime(game_date, '%Y-%m-%d %H:%M:%S')
                    else:
                        # Already a datetime object
                        date_obj = game_date
                    date_display = date_obj.strftime('%Y-%m-%d')
                except:
                    # If parsing fails, try to extract just the date part
                    if isinstance(game_date, str):
                        date_display = game_date[:10] if len(game_date) >= 10 else game_date
                    else:
                        date_display = str(game_date)
            
            # Extract opponent alias from notes field
            opponent_display = team_them_name  # Default to team name
            if notes:
                # Check if notes contains "Opponent: " prefix
                if notes.startswith("Opponent: "):
                    opponent_display = notes.replace("Opponent: ", "").strip()
                else:
                    # If notes doesn't start with "Opponent: ", use it as-is if it's not empty
                    opponent_display = notes.strip() if notes.strip() else team_them_name
            
            display_text = f"Game {game_id}: {team_us_name} vs {opponent_display} ({date_display})"
            game_items.append((display_text, game_id, video_file_path, is_ended))
        
        # Sort games alphabetically in descending order (Z to A)
        game_items.sort(key=lambda x: x[0], reverse=True)
        
        # Add sorted games to the list
        for display_text, game_id, video_file_path, is_ended in game_items:
            item = QListWidgetItem(display_text)
            
            # Set font to bold if game is ended
            if is_ended:
                font = QFont()
                font.setBold(True)
                item.setFont(font)
            
            item.setData(Qt.ItemDataRole.UserRole, {
                'game_id': game_id,
                'video_file_path': video_file_path
            })
            self.game_list.addItem(item)
    
    def on_game_selected(self):
        """Handle game selection from the list."""
        selected_items = self.game_list.selectedItems()
        if not selected_items:
            self.delete_btn.setEnabled(False)
            self.current_game_id = None
            self.current_video_path = None
            return
        
        item = selected_items[0]
        game_data = item.data(Qt.ItemDataRole.UserRole)
        self.current_game_id = game_data['game_id']
        self.current_video_path = game_data['video_file_path']
        
        self.delete_btn.setEnabled(True)
        
        # Load video if path exists
        if self.current_video_path and Path(self.current_video_path).exists():
            self.load_video(self.current_video_path)
        else:
            # Clear video player
            self.media_player.setSource(QUrl())
            self.play_pause_btn.setEnabled(False)
            self.video_slider.setEnabled(False)
            self.time_label.setText("00:00:00 / 00:00:00")
            if not self.current_video_path:
                QMessageBox.information(
                    self,
                    "No Video",
                    f"Game {self.current_game_id} does not have a video file path set."
                )
            else:
                QMessageBox.warning(
                    self,
                    "Video Not Found",
                    f"Video file not found:\n{self.current_video_path}"
                )
    
    def load_video(self, video_path: str):
        """Load a video file into the player."""
        file_url = QUrl.fromLocalFile(video_path)
        self.media_player.setSource(file_url)
        self.play_pause_btn.setEnabled(False)  # Will be enabled when video loads
    
    def on_media_status_changed(self, status):
        """Handle media status changes."""
        from PySide6.QtMultimedia import QMediaPlayer
        if status == QMediaPlayer.MediaStatus.LoadedMedia or status == QMediaPlayer.MediaStatus.BufferedMedia:
            # Video is loaded, enable controls
            self.play_pause_btn.setEnabled(True)
            self.video_slider.setEnabled(True)
            # Seek to beginning
            self.media_player.setPosition(0)
    
    def toggle_play_pause(self):
        """Toggle between play and pause."""
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
            self.play_pause_btn.setText("Play")
        else:
            self.media_player.play()
            self.play_pause_btn.setText("Pause")
    
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
        """Format milliseconds to HH:MM:SS."""
        total_seconds = ms // 1000
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    def get_game_statistics(self, game_id: int):
        """Get statistics for a game before deletion.
        
        Returns:
            Dictionary with game statistics or None if game not found
        """
        if not self.db.conn:
            self.db.connect()
        
        # Get game info
        game = self.db.games.get_game_by_id(game_id)
        if not game:
            return None
        
        team_us_id = game['team_us_id']
        team_them_id = game['team_them_id']
        team_us_name = self.db.teams.get_team_name(team_us_id)
        team_them_name = self.db.teams.get_team_name(team_them_id)
        
        # Count rallies
        num_rallies = self.db.rallies.count_rallies(game_id)
        
        # Count contacts
        num_contacts = self.db.contacts.count_contacts_for_game(game_id)
        
        # Count points for Us and Them
        score_summary = self.db.rallies.get_score_summary(game_id)
        points_us = score_summary.get(team_us_id, 0)
        points_them = score_summary.get(team_them_id, 0)
        
        # Count game players
        num_game_players = self.db.game_players.count_game_players(game_id)
        
        # Count player stats
        num_player_stats = self.db.stats.count_player_stats(game_id)
        
        return {
            'game_id': game_id,
            'team_us_id': team_us_id,
            'team_them_id': team_them_id,
            'team_us_name': team_us_name,
            'team_them_name': team_them_name,
            'num_rallies': num_rallies,
            'num_contacts': num_contacts,
            'points_us': points_us,
            'points_them': points_them,
            'num_game_players': num_game_players,
            'num_player_stats': num_player_stats
        }
    
    def delete_selected_game(self):
        """Delete the selected game after confirmation."""
        if not self.current_game_id:
            return
        
        # Get game statistics before showing confirmation
        stats = self.get_game_statistics(self.current_game_id)
        if not stats:
            QMessageBox.warning(
                self,
                "Game Not Found",
                f"Game {self.current_game_id} not found in database."
            )
            return
        
        # Build confirmation message with statistics
        confirmation_message = (
            f"Are you sure you want to delete Game {stats['game_id']}%s\n\n"
            f"Game: {stats['team_us_name']} vs {stats['team_them_name']}\n\n"
            f"This will delete all associated data:\n"
            f"- {stats['num_rallies']} rallies\n"
            f"- {stats['num_contacts']} contacts\n"
            f"- Points: {stats['team_us_name']} {stats['points_us']} - {stats['points_them']} {stats['team_them_name']}\n"
            f"- {stats['num_game_players']} game players\n"
            f"- {stats['num_player_stats']} player statistics\n\n"
            f"This action cannot be undone!"
        )
        
        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            confirmation_message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Stop video playback
                self.media_player.stop()
                self.media_player.setSource(QUrl())
                
                # Store stats for success message (before deletion)
                deleted_stats = stats.copy()
                
                # Delete the game
                deleted_counts = self.db.games.delete_game(self.current_game_id)
                
                # Show success message with the same format as confirmation
                success_message = (
                    f"Game {deleted_stats['game_id']} has been deleted successfully.\n\n"
                    f"Game: {deleted_stats['team_us_name']} vs {deleted_stats['team_them_name']}\n\n"
                    f"Deleted:\n"
                    f"- {deleted_stats['num_rallies']} rallies\n"
                    f"- {deleted_stats['num_contacts']} contacts\n"
                    f"- Points: {deleted_stats['team_us_name']} {deleted_stats['points_us']} - {deleted_stats['points_them']} {deleted_stats['team_them_name']}\n"
                    f"- {deleted_stats['num_game_players']} game players\n"
                    f"- {deleted_stats['num_player_stats']} player statistics"
                )
                
                QMessageBox.information(
                    self,
                    "Game Deleted",
                    success_message
                )
                
                # Reload games list
                self.load_games()
                
                # Clear selection
                self.game_list.clearSelection()
                self.current_game_id = None
                self.current_video_path = None
                self.delete_btn.setEnabled(False)
                self.play_pause_btn.setEnabled(False)
                self.video_slider.setEnabled(False)
                self.time_label.setText("00:00:00 / 00:00:00")
                
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Deletion Error",
                    f"Failed to delete game:\n{str(e)}"
                )
    
    def resizeEvent(self, event):
        """Handle window resize to scale video."""
        super().resizeEvent(event)
        if self.video_item and self.view:
            # Scale video to fit view
            view_size = self.view.viewport().size()
            self.video_item.setSize(QRectF(0, 0, view_size.width(), view_size.height()).size())
            self.scene.setSceneRect(0, 0, view_size.width(), view_size.height())


