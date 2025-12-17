"""
Data entry screen for tracking ball contacts during a volleyball game.
"""

from PySide6.QtWidgets import QMainWindow, QMessageBox, QLabel, QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton, QListWidgetItem, QScrollArea, QWidget, QGroupBox, QGridLayout, QTextEdit
from PySide6.QtCore import Qt, QEvent, QPoint, Signal, QObject, QThread
from PySide6.QtGui import QMouseEvent, QFont
from PySide6.QtUiTools import QUiLoader
from pathlib import Path
from database import VideoStatsDB
from datetime import datetime
from typing import Optional
from coordinate_mapper import CoordinateMapper
from lineup_manager import LineupManager
from lineup_models import BACK_ROW_POSITIONS
import json
import threading


# Voice recognition imports - optional if vosk is not installed
try:
    from vosk import Model, KaldiRecognizer
    import pyaudio
    VOSK_AVAILABLE = True
except ImportError:
    VOSK_AVAILABLE = False
    print("Warning: vosk or pyaudio not installed. Voice input will be disabled.")


class VoiceRecognizer(QObject):
    """Voice recognition handler for player-action pairs."""
    
    # Signal emitted when a player-action pair is recognized
    pair_recognized = Signal(str, str)  # (player_word, action_word)
    # Signal for status updates
    status_update = Signal(str)
    # Signal when listening starts/stops
    listening_changed = Signal(bool)
    
    # Word-to-number mapping for spoken numbers
    WORD_TO_NUMBER = {
        "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
        "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
        "ten": "10", "eleven": "11", "twelve": "12", "thirteen": "13",
        "fourteen": "14", "fifteen": "15", "sixteen": "16", "seventeen": "17",
        "eighteen": "18", "nineteen": "19", "twenty": "20",
        # Also accept digit strings directly
        "0": "0", "1": "1", "2": "2", "3": "3", "4": "4",
        "5": "5", "6": "6", "7": "7", "8": "8", "9": "9",
        "10": "10", "11": "11", "12": "12", "13": "13", "14": "14",
        "15": "15", "16": "16", "17": "17", "18": "18", "19": "19", "20": "20",
    }
    
    # Valid action words
    VALID_ACTIONS = {
        "serve": "serve", "receive": "receive", "pass": "pass", "dig": "pass",
        "set": "set", "attack": "attack", "hit": "attack",
        "free": "freeball", "freeball": "freeball",
        "block": "block", "down": "down",
        "net": "net", "fault": "fault"
    }
    
    def __init__(self, model_path: str = r"C:\vosk-model-smEng"):
        super().__init__()
        self.model_path = model_path
        self.model = None
        self.recognizer = None
        self.audio_stream = None
        self.pyaudio_instance = None
        self._is_listening = False
        self._stop_requested = False
        self._listen_thread = None
        self._words_buffer = []  # Buffer to collect words for pairing
        
    def initialize(self) -> bool:
        """Initialize the voice recognition model and audio. Returns True if successful."""
        if not VOSK_AVAILABLE:
            self.status_update.emit("Voice recognition not available - vosk/pyaudio not installed")
            return False
        
        try:
            self.status_update.emit("Loading voice model...")
            self.model = Model(self.model_path)
            
            # Define grammar for restricted vocabulary
            number_words = [
                "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
                "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
                "seventeen", "eighteen", "nineteen", "twenty"
            ]
            digits = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", 
                     "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20"]
            actions = ["serve", "receive", "pass", "dig", "set", "attack", "hit",
                      "free", "freeball", "block", "down", "net", "fault"]
            
            grammar = digits + number_words + actions
            
            self.recognizer = KaldiRecognizer(self.model, 16000)
            self.recognizer.SetGrammar(json.dumps(grammar))
            
            # Initialize audio
            self.pyaudio_instance = pyaudio.PyAudio()
            
            self.status_update.emit("Voice model loaded successfully")
            return True
            
        except Exception as e:
            self.status_update.emit(f"Failed to initialize voice recognition: {str(e)}")
            return False
    
    def start_listening(self):
        """Start listening for voice input in background thread."""
        if not self.model or not self.recognizer:
            if not self.initialize():
                return
        
        if self._is_listening:
            return
        
        self._stop_requested = False
        self._words_buffer = []
        self._listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._listen_thread.start()
        self._is_listening = True
        self.listening_changed.emit(True)
        self.status_update.emit("Voice input active - speak player number and action")
    
    def stop_listening(self):
        """Stop listening for voice input."""
        self._stop_requested = True
        if self.audio_stream:
            try:
                self.audio_stream.stop_stream()
                self.audio_stream.close()
            except:
                pass
            self.audio_stream = None
        self._is_listening = False
        self.listening_changed.emit(False)
        self.status_update.emit("Voice input stopped")
    
    def _listen_loop(self):
        """Main listening loop - runs in background thread."""
        try:
            self.audio_stream = self.pyaudio_instance.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=8000
            )
            self.audio_stream.start_stream()
            
            while not self._stop_requested:
                try:
                    data = self.audio_stream.read(4000, exception_on_overflow=False)
                    if self.recognizer.AcceptWaveform(data):
                        result = json.loads(self.recognizer.Result())
                        text = result.get("text", "").strip()
                        
                        if text:
                            self._process_recognized_text(text)
                except Exception as e:
                    if not self._stop_requested:
                        print(f"Voice recognition error: {e}")
                        
        except Exception as e:
            self.status_update.emit(f"Audio stream error: {str(e)}")
        finally:
            self._is_listening = False
            self.listening_changed.emit(False)
    
    def _process_recognized_text(self, text: str):
        """Process recognized text and emit signals when a valid pair is found."""
        words = text.lower().split()
        print(f"DEBUG VOICE: Heard raw text: '{text}'")
        print(f"DEBUG VOICE: Split words: {words}")
        self._words_buffer.extend(words)
        print(f"DEBUG VOICE: Buffer now: {self._words_buffer}")
        
        # Try to form a player-action pair from the buffer
        while len(self._words_buffer) >= 2:
            first_word = self._words_buffer[0]
            second_word = self._words_buffer[1]
            
            # Check if first word is a number
            player_number = self.WORD_TO_NUMBER.get(first_word)
            # Check if second word is an action
            action = self.VALID_ACTIONS.get(second_word)
            
            print(f"DEBUG VOICE: Checking pair: '{first_word}' -> player={player_number}, '{second_word}' -> action={action}")
            
            if player_number and action:
                # Valid pair found
                self._words_buffer = self._words_buffer[2:]  # Remove used words
                print(f"DEBUG VOICE: *** VALID PAIR FOUND: Player {player_number}, Action {action} ***")
                self.pair_recognized.emit(player_number, action)
                self.status_update.emit(f"Recognized: Player {player_number} - {action}")
                return
            else:
                # First word is not a valid number, skip it
                if not player_number:
                    print(f"DEBUG VOICE: Skipping '{first_word}' - not a valid number")
                    self._words_buffer.pop(0)
                # Or second word is not a valid action, skip first word
                elif not action:
                    print(f"DEBUG VOICE: Skipping '{first_word}' - '{second_word}' is not a valid action")
                    self._words_buffer.pop(0)
    
    def is_listening(self) -> bool:
        """Return whether voice recognition is currently listening."""
        return self._is_listening
    
    def cleanup(self):
        """Clean up resources."""
        self.stop_listening()
        if self.pyaudio_instance:
            self.pyaudio_instance.terminate()
            self.pyaudio_instance = None


class DataEntryWindow(QMainWindow):
    """Main window for data entry with rally tracking and scoring."""
    
    def __init__(self, ui_widget, db: VideoStatsDB, team_us_id: Optional[int] = None, team_them_id: Optional[int] = None, game_id: Optional[int] = None, lock_game_selection: bool = False):
        super().__init__()
        # Copy properties from loaded UI
        self.setWindowTitle(ui_widget.windowTitle())
        self.setGeometry(ui_widget.geometry())
        
        # Set central widget and other components
        self.setCentralWidget(ui_widget.centralwidget)
        if hasattr(ui_widget, 'menubar'):
            self.setMenuBar(ui_widget.menubar)
        if hasattr(ui_widget, 'statusbar'):
            self.setStatusBar(ui_widget.statusbar)
        
        # Store reference to UI widgets for button access
        self.ui = ui_widget
        self.db = db
        self.team_us_id = team_us_id
        self.team_them_id = team_them_id
        self.game_id = game_id
        self.lock_game_selection = lock_game_selection
        
        # Lineup manager for rotations
        self.lineup_manager = LineupManager(db)
        
        # Rally tracking
        self.current_rally_id = None
        self.current_rally_number = 0
        self.current_sequence = 0
        self.serving_team_id = None
        self.rally_in_progress = False
        
        # Score tracking
        self.score_us = 0
        self.score_them = 0
        
        # Location tracking for contacts
        self.last_clicked_x = None
        self.last_clicked_y = None
        self.last_clicked_side = None  # 'A' or 'B' for courtSide_A or courtSide_B
        self.last_clicked_timecode = None  # Video timecode in milliseconds
        
        # Team 1 side selection
        self.team_1_side = None  # 'A' or 'B'
        
        # Coordinate mapper for perspective correction
        self.coordinate_mapper = None
        self.use_coordinate_mapper = False  # Flag to enable/disable mapper
        
        # Opponent contact sequence tracking (resets when team A contacts)
        # 1st opponent contact = pass (dig), 2nd = set, 3rd = attack
        self.opponent_contact_count = 0
        
        # Track which team should serve next after a point is awarded
        self.expected_next_server_team_id = None
        
        # Voice input tracking
        self.voice_recognizer = None
        self.use_voice_input = False
        self.pending_voice_contact_x = None
        self.pending_voice_contact_y = None
        self.pending_voice_contact_timecode = None
        
        # Setup UI first (populate games dropdown)
        self.setup_ui()
        self.connect_signals()
        self.setup_court_click_tracking()
        self.setup_coordinate_mapper()
        self.setup_voice_input()
        
        # Initialize with no game selected - labels start blank
        if hasattr(self.ui, 'team_1_name'):
            self.ui.team_1_name.setText("")
        if hasattr(self.ui, 'team_2_name'):
            self.ui.team_2_name.setText("")
        # Also check for old naming convention (backward compatibility)
        if hasattr(self.ui, 'teamNameUs'):
            self.ui.teamNameUs.setText("")
        if hasattr(self.ui, 'teamNameThem'):
            self.ui.teamNameThem.setText("")
        
        # Load game data if game_id provided, otherwise wait for user selection
        # Note: on_game_selected() will be called by populate_games_dropdown() if game_id is provided
        if self.game_id:
            self.load_score()
            # Update MainWindow player buttons based on active lineup
            self.update_mainwindow_player_buttons()
        
        # Always update UI state to set button states correctly
        self.update_ui_state()
    
    def setup_coordinate_mapper(self):
        """Set up and launch the coordinate mapper window."""
        self.coordinate_mapper = CoordinateMapper(parent=self, db=self.db, game_id=self.game_id)
        # Connect signal to receive mapped coordinates
        self.coordinate_mapper.coordinate_mapped.connect(self.on_coordinate_mapped)
        # Connect double-click signal for DOWN contacts
        self.coordinate_mapper.double_click_mapped.connect(self.on_double_click_mapped)
        # Connect signal for when a point is awarded
        self.coordinate_mapper.point_awarded.connect(self.on_point_awarded_from_mapper)
        # Show the coordinate mapper window
        self.coordinate_mapper.show()
        # Position it next to the data entry window
        data_entry_geometry = self.geometry()
        self.coordinate_mapper.setGeometry(
            data_entry_geometry.x() + data_entry_geometry.width() + 20,
            data_entry_geometry.y(),
            1700,  # Width to accommodate 1600 canvas + margins
            1400   # Height to accommodate 1200 canvas + labels
        )
    
    def setup_voice_input(self):
        """Set up voice input functionality."""
        # Connect checkbox if it exists
        if hasattr(self.ui, 'checkBox_UseVoiceInput'):
            self.ui.checkBox_UseVoiceInput.stateChanged.connect(self.on_voice_input_checkbox_changed)
            # Initialize as unchecked
            self.ui.checkBox_UseVoiceInput.setChecked(False)
    
    def on_voice_input_checkbox_changed(self, state):
        """Handle voice input checkbox state change."""
        # In PySide6, stateChanged emits int: 0=Unchecked, 2=Checked
        self.use_voice_input = (state == Qt.CheckState.Checked.value)
        print(f"DEBUG VOICE: Checkbox state changed to {state}, use_voice_input={self.use_voice_input}")
        
        if self.use_voice_input:
            # Initialize voice recognizer if not already done
            if self.voice_recognizer is None:
                if not VOSK_AVAILABLE:
                    QMessageBox.warning(self, "Voice Input Unavailable", 
                                       "Voice input requires vosk and pyaudio packages.\n"
                                       "Install them with: pip install vosk pyaudio")
                    self.ui.checkBox_UseVoiceInput.setChecked(False)
                    self.use_voice_input = False
                    return
                
                self.voice_recognizer = VoiceRecognizer()
                self.voice_recognizer.pair_recognized.connect(self.on_voice_pair_recognized)
                self.voice_recognizer.status_update.connect(self.on_voice_status_update)
            
            # Start listening
            self.voice_recognizer.start_listening()
            self.status_label.setText("Voice input enabled - click location then speak: [number] [action]")
        else:
            # Stop listening
            if self.voice_recognizer:
                self.voice_recognizer.stop_listening()
            self.status_label.setText("Voice input disabled")
    
    def on_voice_status_update(self, message: str):
        """Handle voice recognition status updates."""
        self.status_label.setText(message)
    
    def on_voice_pair_recognized(self, player_number: str, action: str):
        """Handle recognized player-action pair from voice input."""
        print(f"DEBUG VOICE_HANDLER: ========================================")
        print(f"DEBUG VOICE_HANDLER: Voice pair recognized - Player: '{player_number}', Action: '{action}'")
        print(f"DEBUG VOICE_HANDLER: game_id={self.game_id}, rally_in_progress={self.rally_in_progress}")
        print(f"DEBUG VOICE_HANDLER: pending coords: x={self.pending_voice_contact_x}, y={self.pending_voice_contact_y}")
        
        if not self.game_id:
            print(f"DEBUG VOICE_HANDLER: REJECTED - No game selected")
            self.status_label.setText("No game selected - cannot record contact")
            return
        
        if not self.rally_in_progress and action != "serve":
            print(f"DEBUG VOICE_HANDLER: REJECTED - Rally not started and action is not serve")
            self.status_label.setText("Rally must start with a serve")
            return
        
        # Check if we have pending coordinates
        if self.pending_voice_contact_x is None or self.pending_voice_contact_y is None:
            print(f"DEBUG VOICE_HANDLER: REJECTED - No pending coordinates")
            self.status_label.setText(f"Recognized: {player_number} {action} - but no location set. Click on court first.")
            return
        
        # Use the pending coordinates
        self.last_clicked_x = self.pending_voice_contact_x
        self.last_clicked_y = self.pending_voice_contact_y
        self.last_clicked_timecode = self.pending_voice_contact_timecode
        print(f"DEBUG VOICE_HANDLER: Using coords: x={self.last_clicked_x}, y={self.last_clicked_y}, timecode={self.last_clicked_timecode}")
        
        # Look up the player - for team_us, check active_lineup first
        if not self.db.conn:
            self.db.connect()
        
        # Determine team - for now assume "our team" (team_us_id) for voice input
        # The Y coordinate could be used to determine team, but voice is simpler with our team
        team_id = self.team_us_id
        print(f"DEBUG VOICE_HANDLER: Looking up player #{player_number} in team_id={team_id}, game_id={self.game_id}")
        
        # For team_us, check active_lineup first
        player = None
        if team_id == self.team_us_id:
            cursor = self.db.conn.cursor()
            cursor.execute("""
                SELECT p.player_id, p.player_number, p.name, p.jersey
                FROM active_lineup al
                INNER JOIN players p ON al.player_id = p.player_id
                WHERE al.game_id = ? AND al.team_id = ? 
                AND (p.player_number = ? OR CAST(p.jersey AS TEXT) = ?)
            """, (self.game_id, team_id, str(player_number), str(player_number)))
            result = cursor.fetchone()
            if result:
                player = {
                    'player_id': result[0],
                    'player_number': result[1],
                    'name': result[2],
                    'jersey': result[3]
                }
        
        # Fall back to game_players if not found in active_lineup
        if not player:
            player = self.db.get_player_by_number_for_game(self.game_id, team_id, player_number)
        if not player:
            print(f"DEBUG VOICE_HANDLER: REJECTED - Player #{player_number} not found in game roster!")
            self.status_label.setText(f"Player #{player_number} not found in game roster")
            # Clear pending coordinates since we couldn't use them
            self.pending_voice_contact_x = None
            self.pending_voice_contact_y = None
            self.pending_voice_contact_timecode = None
            return
        
        print(f"DEBUG VOICE_HANDLER: Player found! player_id={player['player_id']}")
        self.selected_player_id = player['player_id']
        self.selected_player_number = player_number
        self.selected_team_id = team_id
        
        # Handle special actions: "net" and "fault" have outcome "down"
        # These contacts end the rally
        if action in ("net", "fault"):
            print(f"DEBUG VOICE_HANDLER: Recording net/fault contact...")
            self.status_label.setText(f"Recording #{player_number} {action} (results in down)...")
            self.record_contact(action)
        else:
            print(f"DEBUG VOICE_HANDLER: Recording {action} contact...")
            self.status_label.setText(f"Recording #{player_number} {action}...")
            self.record_contact(action)
        
        # Clear pending coordinates after recording
        self.pending_voice_contact_x = None
        self.pending_voice_contact_y = None
        self.pending_voice_contact_timecode = None
        print(f"DEBUG VOICE_HANDLER: Pending coordinates cleared")
        
        # Clear pending coordinates after recording
        self.pending_voice_contact_x = None
        self.pending_voice_contact_y = None
        self.pending_voice_contact_timecode = None
    
    def on_coordinate_mapped(self, logical_x, logical_y, pixel_x, pixel_y, timecode_ms):
        """Handle coordinate mapping from coordinate_mapper."""
        # Always store coordinates when mapper emits them (if mapper is configured)
        if self.coordinate_mapper and self.coordinate_mapper.is_configured():
            # Store the logical coordinates (these are the perspective-corrected coordinates)
            self.last_clicked_x = logical_x
            self.last_clicked_y = logical_y
            self.last_clicked_timecode = timecode_ms
            
            print(f"DEBUG: on_coordinate_mapped - stored coordinates: x={logical_x}, y={logical_y}, timecode={timecode_ms}ms")
            
            # Format timecode for display (MM:SS.mmm)
            seconds = timecode_ms // 1000
            milliseconds = timecode_ms % 1000
            minutes = seconds // 60
            seconds = seconds % 60
            timecode_str = f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
            
            # Display in tempXYcoord label
            if hasattr(self.ui, 'tempXYcoord'):
                self.ui.tempXYcoord.setText(f"({logical_x:.2f}, {logical_y:.2f}) @ {timecode_str} [Mapped]")
            
            # Handle contacts if game is active and rally in progress
            if self.game_id and self.rally_in_progress:
                # Determine which team based on Y coordinate
                # Y > 300 is far side (opponent/team B), Y <= 300 is near side (team A)
                is_opponent = logical_y > 300
                
                if is_opponent:
                    # Auto-classify opponent contacts based on sequence
                    # 1st = pass (dig), 2nd = set, 3rd = attack (then cycle)
                    contact_sequence = ['pass', 'set', 'attack']
                    contact_type = contact_sequence[self.opponent_contact_count % 3]
                    
                    # Assign opponent player based on sequence: o1, o2, o3
                    opponent_player_number = f"o{(self.opponent_contact_count % 3) + 1}"
                    
                    # Increment opponent contact count
                    self.opponent_contact_count += 1
                    
                    # Set up for recording the contact
                    self.selected_team_id = self.team_them_id
                    self.selected_player_number = opponent_player_number
                    
                    # Get player_id for the opponent player
                    if not self.db.conn:
                        self.db.connect()
                    player = self.db.get_player_by_number_for_game(self.game_id, self.team_them_id, opponent_player_number)
                    if player:
                        self.selected_player_id = player['player_id']
                    else:
                        self.selected_player_id = None
                        print(f"Warning: Opponent player {opponent_player_number} not found in game")
                    
                    # Record the contact automatically
                    self.status_label.setText(f"Recording opponent #{opponent_player_number} {contact_type} at ({logical_x:.2f}, {logical_y:.2f})...")
                    self.record_contact(contact_type)
                else:
                    # Team A contact - reset opponent contact count
                    self.opponent_contact_count = 0
                    
                    # Check if voice input is enabled
                    if self.use_voice_input:
                        # Store coordinates for voice input
                        self.pending_voice_contact_x = logical_x
                        self.pending_voice_contact_y = logical_y
                        self.pending_voice_contact_timecode = timecode_ms
                        print(f"DEBUG COORD: Voice mode - stored pending coords: x={logical_x}, y={logical_y}, timecode={timecode_ms}")
                        self.status_label.setText(f"Location captured ({logical_x:.0f}, {logical_y:.0f}). Now speak: [player number] [action]")
                    else:
                        # Show player selection dialog for team A
                        team_id = self.team_us_id
                        self.show_player_selection_dialog(team_id, logical_x, logical_y, pixel_x, pixel_y)
            else:
                # No rally in progress - check if this is a serve location
                # After a point is awarded, the next click should be for the serving team
                # Serve locations: y near 0 for team_us, y near 600 for team_them
                is_serve_location = False
                expected_team_id = None
                
                # Check if we're expecting a serve after a point was awarded
                if self.expected_next_server_team_id is not None:
                    # Check if click is at serve location for the expected team
                    if self.expected_next_server_team_id == self.team_us_id:
                        # Team_us serves from near y=0 (within 50 units)
                        if logical_y <= 50:
                            is_serve_location = True
                            expected_team_id = self.team_us_id
                    elif self.expected_next_server_team_id == self.team_them_id:
                        # Team_them serves from near y=600 (within 50 units of 600)
                        if logical_y >= 550:
                            is_serve_location = True
                            expected_team_id = self.team_them_id
                
                # Also check if click is at serve location even if not explicitly expected
                # (for cases where user clicks serve location manually)
                if not is_serve_location:
                    if logical_y <= 50:
                        # Near team_us serve location
                        is_serve_location = True
                        expected_team_id = self.team_us_id
                    elif logical_y >= 550:
                        # Near team_them serve location
                        is_serve_location = True
                        expected_team_id = self.team_them_id
                
                if is_serve_location and expected_team_id:
                    # Show serve dialog for the appropriate team
                    self.show_player_selection_dialog(expected_team_id, logical_x, logical_y, pixel_x, pixel_y)
                else:
                    # Update status to indicate coordinate was captured
                    if self.use_coordinate_mapper:
                        self.status_label.setText(f"Coordinate captured: ({logical_x:.2f}, {logical_y:.2f}) @ {timecode_str}. Now click the contact button again to record.")
                    else:
                        self.status_label.setText(f"Coordinate captured: ({logical_x:.2f}, {logical_y:.2f}) @ {timecode_str}. Ready to record contact.")
    
    def on_double_click_mapped(self, logical_x, logical_y, pixel_x, pixel_y, timecode_ms):
        """Handle double-click from coordinate_mapper - records a DOWN contact.
        
        When double-clicking on team_them_id's side (opponent side), records "down" 
        with coordinates but does NOT automatically assign it to a player-action.
        """
        if not self.game_id:
            self.status_label.setText("No game selected - cannot record DOWN contact")
            return
        
        if not self.rally_in_progress:
            self.status_label.setText("No rally in progress - cannot record DOWN contact")
            return
        
        # Handle double-clicks on both sides
        # Y > 300 is opponent side (team_them), Y <= 300 is our side (team_us)
        if logical_y <= 300:
            # Double-click on team_us side - always allow DOWN contact (even on 4th contact)
            # because the ball contacted the floor, not a player
            losing_team_id = self.team_us_id
            print(f"DEBUG: on_double_click_mapped - DOWN contact at x={logical_x}, y={logical_y}, timecode={timecode_ms}ms (team_us side)")
        else:
            # Double-click on team_them side
            losing_team_id = self.team_them_id
            print(f"DEBUG: on_double_click_mapped - DOWN contact at x={logical_x}, y={logical_y}, timecode={timecode_ms}ms (opponent side)")
        
        # Store the coordinates
        self.last_clicked_x = logical_x
        self.last_clicked_y = logical_y
        self.last_clicked_timecode = timecode_ms
        
        # Set up for DOWN contact
        self.selected_team_id = losing_team_id
        self.selected_player_number = None
        self.selected_player_id = None
        
        # Format timecode for display
        seconds = timecode_ms // 1000
        milliseconds = timecode_ms % 1000
        minutes = seconds // 60
        seconds = seconds % 60
        timecode_str = f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
        
        # Update display
        if hasattr(self.ui, 'tempXYcoord'):
            self.ui.tempXYcoord.setText(f"DOWN @ ({logical_x:.2f}, {logical_y:.2f}) @ {timecode_str}")
        
        self.status_label.setText(f"Recording DOWN contact at ({logical_x:.2f}, {logical_y:.2f})...")
        
        # Record the DOWN contact (this is a manual recording, not automatic error assignment)
        self.record_contact("down")
    
    def setup_ui(self):
        """Set up the UI with score display and status."""
        # Populate games dropdown
        self.populate_games_dropdown()
        
        # Create score label in status bar
        try:
            self.score_label = QLabel()
            if hasattr(self.ui, 'statusbar') and self.ui.statusbar:
                self.ui.statusbar.addPermanentWidget(self.score_label)
            if self.game_id:
                self.update_score_display()
        except Exception as e:
            print(f"Warning: Failed to create score_label: {e}")
            self.score_label = None
        
        # Create status label
        try:
            self.status_label = QLabel()
            if hasattr(self.ui, 'statusbar') and self.ui.statusbar:
                self.ui.statusbar.addWidget(self.status_label)
            if self.game_id:
                self.update_status()
        except Exception as e:
            print(f"Warning: Failed to create status_label: {e}")
            self.status_label = None
        
        if not self.game_id:
            self.status_label.setText("Please select a game from the dropdown")
    
    def populate_games_dropdown(self):
        """Populate the games comboBox with all games from the database."""
        if not self.db.conn:
            self.db.connect()
        
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT g.game_id, g.game_date, 
                   t1.name as team_us_name, t2.name as team_them_name,
                   g.team_us_id, g.team_them_id
            FROM games g
            INNER JOIN teams t1 ON g.team_us_id = t1.team_id
            INNER JOIN teams t2 ON g.team_them_id = t2.team_id
            ORDER BY g.game_date DESC, g.game_id DESC
        """)
        games = cursor.fetchall()
        
        self.ui.comboBox.clear()
        
        # Add blank/placeholder item at the start
        self.ui.comboBox.addItem("-- Select a Game --", None)
        
        for game in games:
            game_id, game_date, team_us_name, team_them_name, team_us_id, team_them_id = game
            # Format display text
            display_text = f"Game {game_id}: {team_us_name} vs {team_them_name} ({game_date})"
            self.ui.comboBox.addItem(display_text)
            # Store game data in the item
            index = self.ui.comboBox.count() - 1
            self.ui.comboBox.setItemData(index, {
                'game_id': game_id,
                'team_us_id': team_us_id,
                'team_them_id': team_them_id,
                'team_us_name': team_us_name,
                'team_them_name': team_them_name
            }, Qt.UserRole)
        
        # Auto-select game if game_id is provided
        if self.game_id:
            # Find the game in the dropdown and select it
            found = False
            for i in range(self.ui.comboBox.count()):
                item_data = self.ui.comboBox.itemData(i, Qt.UserRole)
                if item_data and item_data.get('game_id') == self.game_id:
                    self.ui.comboBox.setCurrentIndex(i)
                    # Disable the combo box if selection is locked
                    if self.lock_game_selection:
                        self.ui.comboBox.setEnabled(False)
                    # Trigger the selection handler
                    self.on_game_selected(i)
                    found = True
                    break
            
            if not found:
                # Game not found in dropdown - set to blank selection
                self.ui.comboBox.setCurrentIndex(0)
        else:
            # Always set to blank selection (index 0 is the placeholder)
            self.ui.comboBox.setCurrentIndex(0)
    
    def on_game_selected(self, index: int):
        """Handle game selection from dropdown."""
        if index <= 0:  # 0 is the placeholder, negative is invalid
            # Clear labels if placeholder or invalid selection
            if hasattr(self.ui, 'team_1_name'):
                self.ui.team_1_name.setText("")
            if hasattr(self.ui, 'team_2_name'):
                self.ui.team_2_name.setText("")
            # Also check for old naming convention (backward compatibility)
            if hasattr(self.ui, 'teamNameUs'):
                self.ui.teamNameUs.setText("")
            if hasattr(self.ui, 'teamNameThem'):
                self.ui.teamNameThem.setText("")
            # Clear game data
            self.game_id = None
            self.team_us_id = None
            self.team_them_id = None
            
            # Clear coordinate mapper's game_id as well
            if self.coordinate_mapper:
                self.coordinate_mapper.game_id = None
                print(f"DEBUG: Cleared coordinate_mapper.game_id")
            
            return
        
        # Get game data from selected item
        item_data = self.ui.comboBox.itemData(index, Qt.UserRole)
        if not item_data:
            return
        
        # Update game and team IDs
        self.game_id = item_data['game_id']
        self.team_us_id = item_data['team_us_id']
        self.team_them_id = item_data['team_them_id']
        
        # Update coordinate mapper's game_id so it saves to the correct game
        if self.coordinate_mapper:
            self.coordinate_mapper.game_id = self.game_id
            print(f"DEBUG: Updated coordinate_mapper.game_id to {self.game_id}")
        
        # Update team name labels
        if hasattr(self.ui, 'team_1_name'):
            self.ui.team_1_name.setText(item_data['team_us_name'])
        if hasattr(self.ui, 'team_2_name'):
            self.ui.team_2_name.setText(item_data['team_them_name'])
        # Also check for old naming convention (backward compatibility)
        if hasattr(self.ui, 'teamNameUs'):
            self.ui.teamNameUs.setText(item_data['team_us_name'])
        if hasattr(self.ui, 'teamNameThem'):
            self.ui.teamNameThem.setText(item_data['team_them_name'])
        
        # Update MainWindow player buttons based on active lineup
        self.update_mainwindow_player_buttons()
        
        # Load score and rally data for selected game
        self.load_score()
        self.update_score_display()
        self.update_status()
        self.update_ui_state()
        
        # Clear any selected player
        self.selected_player_number = None
        self.selected_team_id = None
        self.opponent_contact_count = 0  # Reset opponent contact sequence
        
        # Load video file for this game if available
        self.load_game_video()
        
        # Load court boundaries if available
        self.load_game_court_boundaries()
    
    def load_score(self):
        """Load current score from completed rallies."""
        if not self.game_id:
            return
        
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
            # Check if there's an incomplete rally
            cursor.execute(
                """SELECT rally_id, serving_team_id 
                   FROM rallies 
                   WHERE game_id = ? AND rally_number = ? AND point_winner_id IS NULL""",
                (self.game_id, self.current_rally_number)
            )
            incomplete = cursor.fetchone()
            if incomplete:
                self.current_rally_id = incomplete[0]
                self.serving_team_id = incomplete[1]
                self.rally_in_progress = True
                # Get current sequence
                cursor.execute(
                    "SELECT MAX(sequence_number) FROM contacts WHERE rally_id = ?",
                    (self.current_rally_id,)
                )
                seq_result = cursor.fetchone()
                self.current_sequence = (seq_result[0] or 0) + 1
            else:
                # Start new rally - determine serving team
                self.current_rally_number += 1
                # Alternate serving team (simplified - you may want to track this better)
                self.serving_team_id = self.team_us_id if (self.current_rally_number % 2 == 1) else self.team_them_id
        else:
            # First rally
            self.current_rally_number = 1
            self.serving_team_id = self.team_us_id
    
    def load_game_video(self):
        """Load the video file associated with the current game."""
        if not self.game_id:
            return
        
        # Get video path from database
        video_path = self.db.get_game_video_path(self.game_id)
        
        if video_path:
            print(f"DEBUG: Loading video for game {self.game_id}: {video_path}")
            # Load video in coordinate mapper
            if self.coordinate_mapper:
                self.coordinate_mapper.load_video_from_path(video_path)
        else:
            print(f"DEBUG: No video path stored for game {self.game_id}")
    
    def load_game_court_boundaries(self):
        """Load the court boundaries associated with the current game."""
        if not self.game_id:
            return
        
        # Get court boundaries from database
        court_boundaries = self.db.get_game_court_boundaries(self.game_id)
        
        if court_boundaries:
            print(f"DEBUG: Loading court boundaries for game {self.game_id}")
            # Convert to the format expected by coordinate mapper
            # Database returns: corner_tl, corner_tr, corner_bl, corner_br, centerline_top, centerline_bottom,
            #                  y200_left, y200_right, y400_left, y400_right
            # Coordinate mapper expects: [BL, BR, TR, TL, ML, MR, Y200L, Y200R, Y400L, Y400R]
            corner_points = [
                list(court_boundaries['corner_bl']),      # 0: BL (0,0)
                list(court_boundaries['corner_br']),      # 1: BR (300,0)
                list(court_boundaries['corner_tr']),      # 2: TR (300,600)
                list(court_boundaries['corner_tl']),      # 3: TL (0,600)
                list(court_boundaries['centerline_bottom']),  # 4: ML (0,300) - left end of centerline
                list(court_boundaries['centerline_top']),     # 5: MR (300,300) - right end of centerline
            ]
            
            # Add Y200 and Y400 points if available
            if court_boundaries.get('y200_left') is not None:
                corner_points.append(list(court_boundaries['y200_left']))  # 6: Y200L (0,200)
            if court_boundaries.get('y200_right') is not None:
                corner_points.append(list(court_boundaries['y200_right']))  # 7: Y200R (300,200)
            if court_boundaries.get('y400_left') is not None:
                corner_points.append(list(court_boundaries['y400_left']))  # 8: Y400L (0,400)
            if court_boundaries.get('y400_right') is not None:
                corner_points.append(list(court_boundaries['y400_right']))  # 9: Y400R (300,400)
            
            if self.coordinate_mapper:
                self.coordinate_mapper.set_corner_points(corner_points)
                print(f"DEBUG: Court boundaries loaded successfully ({len(corner_points)} points)")
        else:
            print(f"DEBUG: No court boundaries stored for game {self.game_id}")
    
    def connect_signals(self):
        """Connect all button signals to handlers."""
        # Game selection dropdown
        self.ui.comboBox.currentIndexChanged.connect(self.on_game_selected)
        
        # Player number buttons - connect all player number selection buttons
        # These buttons select which player will perform the next action
        if hasattr(self.ui, 'pushButton'):
            self.ui.pushButton.clicked.connect(lambda: self.set_selected_player("13"))
        if hasattr(self.ui, 'pushButton_2'):
            self.ui.pushButton_2.clicked.connect(lambda: self.set_selected_player("8"))
        if hasattr(self.ui, 'pushButton_3'):
            self.ui.pushButton_3.clicked.connect(lambda: self.set_selected_player("1"))
        if hasattr(self.ui, 'pushButton_4'):
            self.ui.pushButton_4.clicked.connect(lambda: self.set_selected_player("opp"))
        if hasattr(self.ui, 'pushButton_9'):
            self.ui.pushButton_9.clicked.connect(lambda: self.set_selected_player("9"))
        if hasattr(self.ui, 'pushButton_13'):
            self.ui.pushButton_13.clicked.connect(lambda: self.set_selected_player("15"))
        if hasattr(self.ui, 'pushButton_14'):
            self.ui.pushButton_14.clicked.connect(lambda: self.set_selected_player("10"))
        if hasattr(self.ui, 'pushButton_15'):
            self.ui.pushButton_15.clicked.connect(lambda: self.set_selected_player("16"))
        if hasattr(self.ui, 'pushButton_16'):
            self.ui.pushButton_16.clicked.connect(lambda: self.set_selected_player("3"))
        if hasattr(self.ui, 'pushButton_17'):
            self.ui.pushButton_17.clicked.connect(lambda: self.set_selected_player("19"))
        if hasattr(self.ui, 'pushButton_18'):
            self.ui.pushButton_18.clicked.connect(lambda: self.set_selected_player("opp"))
        if hasattr(self.ui, 'pushButton_19'):
            self.ui.pushButton_19.clicked.connect(lambda: self.set_selected_player("opp"))
        
        # Connect all player-specific action buttons dynamically
        # Pattern: {player_number}_{action} where action is: receive, pass, set, attack, freeball, block, serve
        action_mapping = {
            'receive': 'receive',
            'pass': 'pass',
            'set': 'set',
            'attack': 'attack',
            'freeball': 'freeball',
            'block': 'block',
            'serve': 'serve'
        }
        
        # Get all widgets and find buttons matching the pattern
        for widget_name in dir(self.ui):
            if not widget_name.startswith('_'):
                widget = getattr(self.ui, widget_name, None)
                if widget and hasattr(widget, 'clicked'):
                    # Check if it matches the pattern {player}_{action}
                    if '_' in widget_name:
                        parts = widget_name.split('_', 1)
                        if len(parts) == 2:
                            player_part = parts[0]
                            action_part = parts[1]
                            
                            # Check if action_part is a valid action
                            if action_part in action_mapping:
                                action = action_mapping[action_part]
                                # Create a closure with default arguments to capture values correctly
                                widget.clicked.connect(
                                    lambda checked=False, p=player_part, a=action: self.handle_player_action(p, a)
                                )
        
        # Point buttons - use givePointUs and givePointThem
        if hasattr(self.ui, 'givePointUs'):
            self.ui.givePointUs.clicked.connect(lambda: self.end_rally(self.team_us_id))
        else:
            # Fallback to old name if exists
            if hasattr(self.ui, 'pushButton_11'):
                self.ui.pushButton_11.clicked.connect(lambda: self.end_rally(self.team_us_id))
        
        if hasattr(self.ui, 'givePointThem'):
            self.ui.givePointThem.clicked.connect(lambda: self.end_rally(self.team_them_id))
        else:
            # Fallback to old name if exists
            if hasattr(self.ui, 'pushButton_12'):
                self.ui.pushButton_12.clicked.connect(lambda: self.end_rally(self.team_them_id))
        
        # Reset game button
        if hasattr(self.ui, 'resetTheGame'):
            self.ui.resetTheGame.clicked.connect(self.reset_the_game)
        
        # Substitution button
        if hasattr(self.ui, 'pushButton_substitution'):
            self.ui.pushButton_substitution.clicked.connect(self.show_substitution_dialog)
        
        # Add Libero IN and Libero OUT buttons next to substitution button
        self.setup_libero_buttons()
        
        # Store selected player
        self.selected_player_number = None
        self.selected_team_id = None
        
        # Track libero replacements: position -> replaced_player_id
        self.libero_replacements = {}  # {position: replaced_player_id}
    
    def setup_court_click_tracking(self):
        """Set up mouse click tracking for the outerCourt widget and court sides."""
        if hasattr(self.ui, 'outerCourt'):
            # Enable mouse tracking
            self.ui.outerCourt.setMouseTracking(False)  # We only need click events, not tracking
            # Install event filter to capture mouse clicks
            self.ui.outerCourt.installEventFilter(self)
        
        # Set up click tracking for courtSide_A and courtSide_B
        if hasattr(self.ui, 'courtSide_A'):
            self.ui.courtSide_A.installEventFilter(self)
        if hasattr(self.ui, 'courtSide_B'):
            self.ui.courtSide_B.installEventFilter(self)
        
        # Set up side selection radio buttons for team 1
        if hasattr(self.ui, 'radioButton_team_1_side_A'):
            self.ui.radioButton_team_1_side_A.clicked.connect(lambda: self.set_team_1_side('A'))
        if hasattr(self.ui, 'radioButton_team_1_side_B'):
            self.ui.radioButton_team_1_side_B.clicked.connect(lambda: self.set_team_1_side('B'))
    
    def set_team_1_side(self, side: str):
        """Set team 1's chosen side (A or B)."""
        self.team_1_side = side
        print(f"Team 1 side set to: {side}")
    
    def get_team_contact_count(self, team_id: int) -> int:
        """Get the number of contacts made by a team in the current rally (excluding 'down' contacts).
        
        Args:
            team_id: The team ID to count contacts for
            
        Returns:
            The number of contacts (1st, 2nd, 3rd, etc.)
        """
        if not self.current_rally_id:
            return 0
        
        if not self.db.conn:
            self.db.connect()
        
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) 
            FROM contacts 
            WHERE rally_id = ? AND team_id = ? AND contact_type != 'down'
            ORDER BY sequence_number
        """, (self.current_rally_id, team_id))
        
        result = cursor.fetchone()
        return result[0] if result else 0
    
    def get_current_possession_contact_count(self, team_id: int) -> int:
        """Get the number of contacts made by a team in their current possession.
        This counts only consecutive contacts by the team since the last opponent contact (or since serve).
        
        Args:
            team_id: The team ID to count contacts for
            
        Returns:
            The number of contacts in the current possession (0, 1, 2, etc.)
        """
        if not self.current_rally_id:
            return 0
        
        if not self.db.conn:
            self.db.connect()
        
        cursor = self.db.conn.cursor()
        # Get all contacts in reverse order (most recent first)
        cursor.execute("""
            SELECT team_id, contact_type, sequence_number
            FROM contacts 
            WHERE rally_id = ? AND contact_type != 'down'
            ORDER BY sequence_number DESC
        """, (self.current_rally_id,))
        
        contacts = cursor.fetchall()
        
        if not contacts:
            return 0
        
        # Count consecutive contacts by the same team, starting from the most recent
        count = 0
        for contact_team_id, contact_type, seq_num in contacts:
            if contact_team_id == team_id:
                count += 1
            else:
                # Found opponent contact - stop counting
                break
        
        return count
    
    def get_team_players(self, team_id: int):
        """Get players for a team, using active_lineup for team_us, game_players for team_them.
        
        Args:
            team_id: The team ID to get players from
            
        Returns:
            List of (player_id, player_number, player_name) tuples
        """
        if not self.game_id:
            return []
        
        if not self.db.conn:
            self.db.connect()
        
        cursor = self.db.conn.cursor()
        
        # For team_us, use active_lineup to get players currently on court
        if team_id == self.team_us_id:
            cursor.execute("""
                SELECT p.player_id, 
                       COALESCE(p.jersey, p.player_number) as player_number,
                       p.name
                FROM active_lineup al
                INNER JOIN players p ON al.player_id = p.player_id
                WHERE al.team_id = ?
                ORDER BY al.position_number
            """, (team_id,))
            players = cursor.fetchall()
            
            # If no active lineup found, fall back to game_players
            if not players:
                cursor.execute("""
                    SELECT p.player_id, p.player_number, p.name
                    FROM players p
                    INNER JOIN game_players gp ON p.player_id = gp.player_id
                    WHERE gp.game_id = ? AND gp.team_id = ?
                    ORDER BY CASE 
                        WHEN CAST(p.player_number AS INTEGER) IS NOT NULL 
                        THEN CAST(p.player_number AS INTEGER)
                        ELSE 999
                    END,
                    p.player_number
                """, (self.game_id, team_id))
                players = cursor.fetchall()
        else:
            # For team_them, use game_players (existing behavior)
            cursor.execute("""
                SELECT p.player_id, p.player_number, p.name
                FROM players p
                INNER JOIN game_players gp ON p.player_id = gp.player_id
                WHERE gp.game_id = ? AND gp.team_id = ?
                ORDER BY CASE 
                    WHEN CAST(p.player_number AS INTEGER) IS NOT NULL 
                    THEN CAST(p.player_number AS INTEGER)
                    ELSE 999
                END,
                p.player_number
            """, (self.game_id, team_id))
            players = cursor.fetchall()
        
        return players
    
    def get_active_lineup_with_roles(self, team_id: int):
        """Get active lineup players with their role_code and position_number.
        
        Args:
            team_id: The team ID to get active lineup for
            
        Returns:
            List of (player_id, player_number, player_name, role_code, position_number) tuples
        """
        if not self.game_id:
            return []
        
        if not self.db.conn:
            self.db.connect()
        
        # Ensure connection is active and sees latest data
        # Commit any pending transactions to ensure we see the latest lineup
        if self.db.conn:
            try:
                self.db.conn.commit()
            except:
                pass
        
        cursor = self.db.conn.cursor()
        
        # For team_us, get active lineup with roles and positions
        if team_id == self.team_us_id:
            cursor.execute("""
                SELECT p.player_id, 
                       COALESCE(p.jersey, p.player_number) as player_number,
                       p.name,
                       COALESCE(al.role_code, '') as role_code,
                       al.position_number,
                       al.is_server
                FROM active_lineup al
                INNER JOIN players p ON al.player_id = p.player_id
                WHERE al.game_id = ? AND al.team_id = ?
                ORDER BY al.position_number
            """, (self.game_id, team_id))
            results = cursor.fetchall()
            # Debug: print all players including libero
            print(f"DEBUG get_active_lineup_with_roles: Found {len(results)} players")
            for row in results:
                player_id, player_number, player_name, role_code, position_number, is_server = row
                server_marker = " [SERVER]" if is_server else ""
                print(f"  Player #{player_number} ({player_name}) - Role: '{role_code}', Position: {position_number}{server_marker}")
            
            # Validate we have exactly 6 players
            if len(results) != 6:
                print(f"WARNING: get_active_lineup_with_roles returned {len(results)} players, expected 6")
            
            # Return results with is_server included (will be used for prioritizing server)
            return results
        else:
            # For team_them, return empty (they don't use active_lineup)
            return []
    
    def map_player_to_groupbox(self, role_code: str, position_number: int, has_libero: bool):
        """Map a player to a GroupBox based on role and position.
        
        Args:
            role_code: Player's role (OH, MH, RS, S, Lib, DS)
            position_number: Court position (1-6)
            has_libero: Whether libero is currently on court
            
        Returns:
            GroupBox name (e.g., 'groupBox_LF') or None if no match
        """
        # Handle None or empty role_code
        if not role_code or role_code.strip() == '':
            # Default to OH if role is not set
            role = 'OH'
        else:
            # Normalize role codes (RS and RH are synonyms, S is Setter)
            role = role_code.upper().strip()
            if role == 'RH':
                role = 'RS'
        
        # Front row positions: 2, 3, 4 (RF, MF, LF)
        # Back row positions: 1, 5, 6 (RB, MB, LB)
        FRONT_ROW = {2, 3, 4}
        BACK_ROW = {1, 5, 6}
        
        if position_number in FRONT_ROW:
            # Front row logic
            if role == 'OH':
                return 'groupBox_LF'
            elif role == 'MH':
                return 'groupBox_MF'
            elif role in ('RS', 'S', 'RH'):
                return 'groupBox_RF'
            else:
                # Fallback for unknown roles in front row: distribute evenly
                if position_number == 2:
                    return 'groupBox_RF'
                elif position_number == 3:
                    return 'groupBox_MF'
                elif position_number == 4:
                    return 'groupBox_LF'
        elif position_number in BACK_ROW:
            # Back row logic
            if role == 'LIB':  # Note: role is already uppercased above
                # Libero always uses LB when in back row
                return 'groupBox_LB'
            elif role in ('S', 'RS', 'RH'):
                # Setter or RS always uses RB when in back row
                return 'groupBox_RB'
            elif role in ('OH', 'DS'):
                # OH or DS: use MB normally, but LB when libero is NOT on court
                if has_libero:
                    return 'groupBox_MB'
                else:
                    return 'groupBox_LB'
            elif role == 'MH':
                # MH: always use MB when in back row (regardless of libero status)
                return 'groupBox_MB'
            else:
                # Fallback for unknown roles in back row: distribute evenly
                if position_number == 1:
                    return 'groupBox_RB'
                elif position_number == 5:
                    return 'groupBox_LB'
                elif position_number == 6:
                    return 'groupBox_MB'
        
        # Final fallback: return a default based on position
        if position_number in FRONT_ROW:
            return 'groupBox_MF'  # Default to middle front
        elif position_number in BACK_ROW:
            return 'groupBox_MB'  # Default to middle back
        
        return None
    
    def show_player_selection_dialog(self, team_id: int, x_coord: float, y_coord: float, pixel_x: float = None, pixel_y: float = None):
        """Show a dialog to select a player from the specified team using the new UI layout.
        
        Args:
            team_id: The team ID to get players from
            x_coord: X coordinate of the click (logical)
            y_coord: Y coordinate of the click (logical)
            pixel_x: Pixel X coordinate for positioning dialog (optional)
            pixel_y: Pixel Y coordinate for positioning dialog (optional)
        """
        if not self.game_id:
            return
        
        # Detect which side of the court the click is on
        # Y <= 300 is team_us side, Y > 300 is team_them side
        is_team_us_side = y_coord <= 300 if y_coord is not None else None
        
        # If click is on team_us side, automatically use team_us for the contact
        if is_team_us_side is True:
            team_id = self.team_us_id
            print(f"DEBUG: Click on team_us side (Y={y_coord}) - using team_us")
        elif is_team_us_side is False:
            # Click is on team_them side - use team_them
            team_id = self.team_them_id
            print(f"DEBUG: Click on team_them side (Y={y_coord}) - using team_them")
        
        # Check if this is a serve location (no rally in progress and click is at serve location)
        # Serve locations: y <= 50 for team_us, y >= 550 for team_them
        # This must be checked BEFORE all the contact counting logic
        is_serve_location = False
        if y_coord is not None:
            if y_coord <= 50:
                # Near team_us serve location (y near 0)
                is_serve_location = True
                team_id = self.team_us_id
            elif y_coord >= 550:
                # Near team_them serve location (y near 600)
                is_serve_location = True
                team_id = self.team_them_id
        
        print(f"DEBUG SERVE CHECK: rally_in_progress={self.rally_in_progress}, is_serve_location={is_serve_location}, team_id={team_id}, y_coord={y_coord}, serving_team_id={self.serving_team_id}, expected_next_server_team_id={self.expected_next_server_team_id}")
        
        if not self.rally_in_progress and is_serve_location:
            # Check if this team should be serving
            should_serve = False
            if self.expected_next_server_team_id is not None:
                # We're expecting a specific team to serve
                should_serve = (team_id == self.expected_next_server_team_id)
            elif self.serving_team_id is not None:
                # Use serving_team_id as fallback
                should_serve = (team_id == self.serving_team_id)
            else:
                # No explicit expectation, but we're at a serve location, so allow it
                should_serve = True
            
            if should_serve:
                server_player_id = None
                server_player_number = None
                server_player_name = None
                
                if team_id == self.team_us_id:
                    # Get the server from active_lineup (position 1)
                    if not self.db.conn:
                        self.db.connect()
                    cursor = self.db.conn.cursor()
                    cursor.execute("""
                        SELECT al.player_id, COALESCE(p.jersey, p.player_number) as player_number, p.name
                        FROM active_lineup al
                        INNER JOIN players p ON al.player_id = p.player_id
                        WHERE al.game_id = ? AND al.team_id = ? AND al.is_server = 1
                    """, (self.game_id, team_id))
                    result = cursor.fetchone()
                    
                    if result:
                        server_player_id, server_player_number, server_player_name = result
                        print(f"DEBUG: Serve detected (team_us) - Server: #{server_player_number} {server_player_name} (ID:{server_player_id})")
                    else:
                        # Fallback: position 1 is the server
                        cursor.execute("""
                            SELECT al.player_id, COALESCE(p.jersey, p.player_number) as player_number, p.name
                            FROM active_lineup al
                            INNER JOIN players p ON al.player_id = p.player_id
                            WHERE al.game_id = ? AND al.team_id = ? AND al.position_number = 1
                        """, (self.game_id, team_id))
                        result = cursor.fetchone()
                        if result:
                            server_player_id, server_player_number, server_player_name = result
                            print(f"DEBUG: Serve detected (team_us, fallback to position 1) - Server: #{server_player_number} {server_player_name} (ID:{server_player_id})")
                elif team_id == self.team_them_id:
                    # For team_them, default to player o0
                    if not self.db.conn:
                        self.db.connect()
                    player = self.db.get_player_by_number_for_game(self.game_id, self.team_them_id, "o0")
                    if player:
                        server_player_id = player['player_id']
                        server_player_number = "o0"
                        server_player_name = player.get('name', 'Unknown')
                        print(f"DEBUG: Serve detected (team_them) - Server: #{server_player_number} {server_player_name} (ID:{server_player_id})")
                    else:
                        # Fallback: try to get any team_them player
                        players = self.get_team_players(team_id)
                        if players:
                            server_player_id = players[0]['player_id']
                            server_player_number = players[0].get('jersey') or players[0].get('player_number', 'Unknown')
                            server_player_name = players[0].get('name', 'Unknown')
                            print(f"DEBUG: Serve detected (team_them, fallback) - Server: #{server_player_number} {server_player_name} (ID:{server_player_id})")
                
                if server_player_id:
                    # Show serve dialog with only "serve" option
                    dialog = QDialog(self.coordinate_mapper if self.coordinate_mapper else self)
                    dialog.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
                    dialog.setModal(True)
                    
                    layout = QVBoxLayout()
                    layout.setContentsMargins(10, 10, 10, 10)
                    layout.setSpacing(5)
                    
                    # Server label
                    server_label = QLabel(f"Server: #{server_player_number} {server_player_name or 'Unknown'}")
                    server_label.setFont(QFont('Arial', 10, QFont.Weight.Bold))
                    layout.addWidget(server_label)
                    
                    # Serve button (only option)
                    serve_btn = QPushButton("Serve")
                    serve_btn.setFont(QFont('Arial', 10))
                    serve_btn.setFixedSize(100, 40)
                    serve_btn.setStyleSheet("background-color: #E0FFFF; border: 1px solid #505050;")
                    
                    selected_action = [None]
                    serve_btn.clicked.connect(lambda: (selected_action.__setitem__(0, [server_player_id, "serve"]), dialog.accept()))
                    
                    layout.addWidget(serve_btn)
                    dialog.setLayout(layout)
                    dialog.setFixedSize(120, 80)
                    
                    # Position dialog to the upper right corner of the clicked point
                    if self.coordinate_mapper and pixel_x is not None and pixel_y is not None:
                        mapper_pos = self.coordinate_mapper.mapToGlobal(QPoint(0, 0))
                        dialog_x = mapper_pos.x() + int(pixel_x) + 10
                        dialog_y = mapper_pos.y() + int(pixel_y) - 80
                        dialog.move(dialog_x, dialog_y)
                    elif pixel_x is not None and pixel_y is not None:
                        dialog_x = int(pixel_x) + 10
                        dialog_y = int(pixel_y) - 80
                        dialog.move(dialog_x, dialog_y)
                    
                    if dialog.exec() == QDialog.Accepted and selected_action[0]:
                        self.selected_player_id = selected_action[0][0]
                        self.selected_team_id = team_id
                        # Clear expected server after serve is recorded
                        self.expected_next_server_team_id = None
                        self.record_contact(selected_action[0][1])
                    return  # Return immediately after handling serve
        
        # Only use new UI for team_us (they have active_lineup)
        # For team_them, fall back to old dialog
        if team_id != self.team_us_id:
            # For team_them, use the old dialog implementation
            players = self.get_team_players(team_id)
            if not players:
                QMessageBox.warning(self, "No Players", "No players found for this team in this game.")
                return
            # Continue with old dialog implementation below (will be handled in the else branch)
            use_new_ui = False
        else:
            # For team_us, use new UI with active lineup
            active_players = self.get_active_lineup_with_roles(team_id)
            if not active_players:
                QMessageBox.warning(self, "No Players", "No active players found for this team.")
                return
            
            # Validate we have exactly 6 players
            if len(active_players) != 6:
                print(f"WARNING: Expected 6 players in active lineup, but found {len(active_players)}")
                QMessageBox.warning(self, "Incomplete Lineup", 
                                  f"Expected 6 players on court, but found {len(active_players)}. "
                                  "Please check the lineup configuration.")
                # Continue anyway, but log the issue
            
            use_new_ui = True
        
        # Check if the prior contact was a serve by the opponent team
        prior_contact_was_opponent_serve = False
        if self.current_rally_id:
            if not self.db.conn:
                self.db.connect()
            cursor = self.db.conn.cursor()
            cursor.execute("""
                SELECT contact_type, team_id 
                FROM contacts 
                WHERE rally_id = ? AND contact_type != 'down'
                ORDER BY sequence_number DESC 
                LIMIT 1
            """, (self.current_rally_id,))
            result = cursor.fetchone()
            if result:
                last_contact_type, last_contact_team_id = result
                # Check if it was a serve by the opponent team
                if last_contact_type == 'serve' and last_contact_team_id != team_id:
                    prior_contact_was_opponent_serve = True
        
        # Check if the last contact was by the opponent team - if so, this is a new possession
        last_contact_was_opponent = False
        if self.current_rally_id:
            if not self.db.conn:
                self.db.connect()
            cursor = self.db.conn.cursor()
            cursor.execute("""
                SELECT team_id 
                FROM contacts 
                WHERE rally_id = ? AND contact_type != 'down'
                ORDER BY sequence_number DESC 
                LIMIT 1
            """, (self.current_rally_id,))
            result = cursor.fetchone()
            if result:
                last_contact_team_id = result[0]
                if last_contact_team_id != team_id:
                    last_contact_was_opponent = True
        
        # If the last contact was by the opponent, this is a new possession for the current team
        # Reset contact count to 0 (so next contact is contact 1)
        if last_contact_was_opponent:
            contact_count = 0
            contact_number = 1
            print(f"DEBUG: Last contact was by opponent - treating as {team_id}'s first contact (new possession)")
        else:
            # Last contact was by the same team - continue their possession
            # Count only contacts in the current possession (since last opponent contact or since serve)
            contact_count = self.get_current_possession_contact_count(team_id)
            contact_number = contact_count + 1
            print(f"DEBUG: Last contact was by same team - current possession contact count={contact_count}, contact number={contact_number}")
        
        # Special case: If click is on team_us side, ensure we're using team_us
        if is_team_us_side is True:
            # Already handled above - team_id was set to team_us_id
            pass
        
        # Check if team already has 3 contacts in current possession
        # If so, this would be a 4th contact - handle it appropriately
        # Only show error/dialog if contact_number > 3 (next contact would be 4th or more)
        # Don't show error if contact_number is 3 (team is making their 3rd contact, which is allowed)
        # Also don't show error if we're currently recording a contact (prevents error from showing during contact recording)
        _recording_flag = getattr(self, '_recording_contact', False)
        print(f"DEBUG 4TH CONTACT CHECK: contact_count={contact_count}, contact_number={contact_number}, _recording_contact={_recording_flag}, team_id={team_id}")
        if contact_number > 3 and not _recording_flag:
            # Team already has 3 contacts - this would be a 4th contact
            print(f"DEBUG 4TH CONTACT CHECK: Triggering 4th contact handling for team {team_id}")
            # For team_us, show special "Down (Error)" dialog
            # For team_them, show error message
            if team_id == self.team_us_id:
                # Handle 4th contact on team_us side - show small popup with only "down" button
                dialog = QDialog(self.coordinate_mapper if self.coordinate_mapper else self)
                dialog.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
                dialog.setModal(True)
                
                layout = QVBoxLayout()
                layout.setContentsMargins(5, 5, 5, 5)
                layout.setSpacing(2)
                
                down_btn = QPushButton("Down (Error)")
                down_btn.setFont(QFont('Arial', 9))
                down_btn.setFixedSize(80, 30)
                down_btn.setStyleSheet("background-color: #FF6B6B; border: 1px solid #505050;")
                
                selected_action = [None]
                down_btn.clicked.connect(lambda: (selected_action.__setitem__(0, ["down", "down", "error"]), dialog.accept()))
                
                layout.addWidget(down_btn)
                dialog.setLayout(layout)
                dialog.setFixedSize(90, 40)
                
                # Position dialog to the upper right corner of the clicked point
                if self.coordinate_mapper and pixel_x is not None and pixel_y is not None:
                    mapper_pos = self.coordinate_mapper.mapToGlobal(QPoint(0, 0))
                    dialog_x = mapper_pos.x() + int(pixel_x) + 10
                    dialog_y = mapper_pos.y() + int(pixel_y) - 40
                    dialog.move(dialog_x, dialog_y)
                elif pixel_x is not None and pixel_y is not None:
                    dialog_x = int(pixel_x) + 10
                    dialog_y = int(pixel_y) - 40
                    dialog.move(dialog_x, dialog_y)
                
                if dialog.exec() == QDialog.Accepted and selected_action[0]:
                    # Record down contact with error outcome
                    self.selected_player_id = None
                    self.selected_player_number = None
                    self.selected_team_id = team_id
                    if hasattr(self, 'status_label'):
                        self.status_label.setText("Recording DOWN contact (error)...")
                    # Store the outcome for record_contact
                    self._pending_contact_outcome = "error"
                    self.record_contact("down")
                    self._pending_contact_outcome = None
                return
            else:
                # For team_them, show error message for 4th contact
                QMessageBox.warning(self, "Invalid Contact", 
                                  f"Maximum 3 contacts allowed per team. This would be contact #{contact_number}.")
                return
        
        # Get opponent's contact count to check if they can block
        opponent_team_id = self.team_them_id if team_id == self.team_us_id else self.team_us_id
        opponent_contact_count = self.get_team_contact_count(opponent_team_id)
        
        # Determine allowed actions based on whether it's after opponent serve or later in rally
        # Initialize allowed_actions early to avoid UnboundLocalError in closures
        # Ensure allowed_actions is always assigned (defensive programming)
        allowed_actions = []
        print(f"DEBUG ALLOWED_ACTIONS: Starting - contact_number={contact_number}, prior_contact_was_opponent_serve={prior_contact_was_opponent_serve}, team_id={team_id}")
        
        if prior_contact_was_opponent_serve:
            # After opponent's serve: receive, then set/attack/free, then attack/free
            if contact_number == 1:
                # 1st contact after opponent serve: only receive
                allowed_actions = ['receive']
            elif contact_number == 2:
                # 2nd contact: set, attack, free
                allowed_actions = ['set', 'attack', 'freeball']
            elif contact_number == 3:
                # 3rd contact: attack, free
                allowed_actions = ['attack', 'freeball']
            else:
                # Fallback for unexpected contact_number
                allowed_actions = ['receive', 'pass', 'set', 'attack', 'freeball']
        else:
            # After serving team has their contact(s) or later in rally: pass/attack/block, then set/attack/free, then attack/free
            if contact_number == 1:
                # 1st contact: pass, attack, block
                allowed_actions = ['pass', 'attack', 'block']
            elif contact_number == 2:
                # 2nd contact: set, attack, free
                allowed_actions = ['set', 'attack', 'freeball']
            elif contact_number == 3:
                # 3rd contact: attack, free
                allowed_actions = ['attack', 'freeball']
            else:
                # Fallback for unexpected contact_number
                allowed_actions = ['pass', 'set', 'attack', 'freeball']
        
        print(f"DEBUG ALLOWED_ACTIONS: After initial assignment - allowed_actions={allowed_actions}")
        
        # Add block as allowed action if opponent has 1st or 2nd contact
        # Block can happen after opponent's 1st or 2nd contact
        # Ensure allowed_actions exists before checking/adding
        if allowed_actions and (opponent_contact_count == 1 or opponent_contact_count == 2):
            if 'block' not in allowed_actions:
                allowed_actions.append('block')
                print(f"DEBUG ALLOWED_ACTIONS: Added block - allowed_actions={allowed_actions}")
        
        # Safety check: if allowed_actions is still empty, something went wrong
        if not allowed_actions:
            QMessageBox.warning(self, "Invalid Contact", 
                              f"Cannot determine allowed actions for contact #{contact_number}.")
            print(f"DEBUG ERROR: allowed_actions is empty - contact_number={contact_number}, prior_serve={prior_contact_was_opponent_serve}, team_id={team_id}")
            return
        
        # Ensure allowed_actions is a list (defensive programming)
        if not isinstance(allowed_actions, list):
            allowed_actions = list(allowed_actions) if allowed_actions else []
        
        # Store allowed_actions in a safe variable to avoid UnboundLocalError in nested scopes
        # This ensures the value is captured after all modifications (including block addition)
        safe_allowed_actions = list(allowed_actions) if allowed_actions else []
        print(f"DEBUG ALLOWED_ACTIONS: Created safe_allowed_actions={safe_allowed_actions}")
        
        # Use new UI for team_us, old UI for team_them
        if use_new_ui:
            # Load the new UI file
            ui_file = Path(__file__).parent / "contact-popup1.ui"
            loader = QUiLoader()
            dialog_widget = loader.load(str(ui_file))
            
            if not dialog_widget:
                QMessageBox.critical(self, "Error", "Failed to load contact popup UI file.")
                return
            
            # Create dialog and set widget
            dialog = QDialog(self.coordinate_mapper if self.coordinate_mapper else self)
            dialog.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
            dialog.setModal(True)
            
            dialog_layout = QVBoxLayout(dialog)
            dialog_layout.setContentsMargins(0, 0, 0, 0)
            dialog_layout.addWidget(dialog_widget)
            
            # Store selected action info
            selected_action = [None]  # [player_id, action_type] or ["down", "down"]
            
            # Check if libero is on court (check both 'Lib' and 'LIB' for case sensitivity)
            # active_players now includes is_server as 6th element: (player_id, player_number, player_name, role_code, position_number, is_server)
            has_libero = any((len(p) >= 5 and p[3] and p[3].upper().strip() == 'LIB') for p in active_players)
            
            # Map players to GroupBoxes
            groupbox_assignments = {}  # {groupbox_name: [(player_id, player_number, player_name, role_code, position_number, is_server), ...]}
            
            # Track which positions have been assigned to ensure all 6 players are shown
            assigned_positions = set()
            
            print(f"DEBUG POPUP: Active players count: {len(active_players)}")
            for player_data in active_players:
                # Handle both old format (5 elements) and new format (6 elements with is_server)
                if len(player_data) == 6:
                    player_id, player_number, player_name, role_code, position_number, is_server = player_data
                else:
                    player_id, player_number, player_name, role_code, position_number = player_data
                    is_server = False
                print(f"DEBUG POPUP: Player #{player_number} ({player_name}) - Role: {role_code}, Position: {position_number}, Has Libero: {has_libero}")
                groupbox_name = self.map_player_to_groupbox(role_code, position_number, has_libero)
                print(f"DEBUG POPUP:   -> Mapped to GroupBox: {groupbox_name}")
                
                # If no GroupBox mapping, use a fallback based on position
                if not groupbox_name:
                    # Fallback mapping: ensure every position maps to a GroupBox
                    FRONT_ROW = {2, 3, 4}
                    BACK_ROW = {1, 5, 6}
                    if position_number in FRONT_ROW:
                        if position_number == 2:
                            groupbox_name = 'groupBox_RF'
                        elif position_number == 3:
                            groupbox_name = 'groupBox_MF'
                        elif position_number == 4:
                            groupbox_name = 'groupBox_LF'
                    elif position_number in BACK_ROW:
                        if position_number == 1:
                            groupbox_name = 'groupBox_RB'  # Server position
                        elif position_number == 5:
                            groupbox_name = 'groupBox_LB'
                        elif position_number == 6:
                            groupbox_name = 'groupBox_MB'
                    print(f"DEBUG POPUP:   -> Using fallback GroupBox: {groupbox_name}")
                
                if groupbox_name:
                    if groupbox_name not in groupbox_assignments:
                        groupbox_assignments[groupbox_name] = []
                    groupbox_assignments[groupbox_name].append(player_data)
                    assigned_positions.add(position_number)
                else:
                    print(f"DEBUG POPUP:   -> ERROR: Still no GroupBox mapping for player #{player_number} (Role: {role_code}, Position: {position_number})")
            
            # Validate all 6 positions are assigned
            if len(assigned_positions) != 6:
                missing_positions = set(range(1, 7)) - assigned_positions
                print(f"WARNING: Not all positions assigned to GroupBoxes. Missing positions: {missing_positions}")
            
            print(f"DEBUG POPUP: GroupBox assignments: {list(groupbox_assignments.keys())}")
            print(f"DEBUG POPUP: Assigned positions: {sorted(assigned_positions)}")
            
            # Define button configurations by contact number
            # Button order: 1st contact row (buttons 1-3), 2nd contact row (buttons 4-5), 3rd contact row (buttons 6-7)
            button_configs = {
                1: {  # 1st contact
                    'after_serve': [
                        ('Recv', 'receive', '#DDA0DD'),  # pushButton_X_1
                    ],
                    'other': [
                        ('Dig', 'pass', '#DDA0DD'),      # pushButton_X_1
                    ],
                    'common': [
                        ('Attack', 'attack', '#E0FFFF'),  # pushButton_X_2
                        ('Block', 'block', '#BFFF00')     # pushButton_X_3
                    ]
                },
                2: {  # 2nd contact
                    'buttons': [
                        ('Set', 'set', '#ADD8E6'),       # pushButton_X_4
                        ('Free', 'freeball', '#90EE90')  # pushButton_X_5
                    ]
                },
                3: {  # 3rd contact
                    'buttons': [
                        ('Attack', 'attack', '#E0FFFF'), # pushButton_X_6
                        ('Free', 'freeball', '#90EE90')  # pushButton_X_7
                    ]
                }
            }
            
            # Define action colors
            action_colors = {
                'receive': '#DDA0DD',
                'pass': '#DDA0DD',
                'set': '#ADD8E6',
                'attack': '#E0FFFF',
                'freeball': '#90EE90',
                'block': '#BFFF00'
            }
            
            # Create a local copy of allowed_actions to avoid scoping issues
            # Use the safe copy we created earlier to avoid UnboundLocalError
            try:
                local_allowed_actions = list(safe_allowed_actions)
                print(f"DEBUG ALLOWED_ACTIONS: In new UI - local_allowed_actions={local_allowed_actions}")
            except (NameError, UnboundLocalError) as e:
                print(f"DEBUG ERROR: Failed to access safe_allowed_actions in new UI: {e}")
                # Fallback based on contact_number
                if contact_number == 3:
                    local_allowed_actions = ['attack', 'freeball']
                elif contact_number == 2:
                    local_allowed_actions = ['set', 'attack', 'freeball']
                else:
                    local_allowed_actions = ['receive', 'pass', 'set', 'attack', 'freeball']
                print(f"DEBUG ALLOWED_ACTIONS: Using fallback - local_allowed_actions={local_allowed_actions}")
            
            # Process each GroupBox
            for groupbox_name, players_in_groupbox in groupbox_assignments.items():
                groupbox = dialog_widget.findChild(QGroupBox, groupbox_name)
                if not groupbox:
                    print(f"DEBUG: GroupBox {groupbox_name} not found in UI")
                    continue
                
                # Set GroupBox width to 66px
                groupbox.setFixedWidth(66)
                
                # Set GroupBox title to first player's "#-Name" (or combine if multiple)
                if players_in_groupbox:
                    player_labels = []
                    for player_data in players_in_groupbox:
                        # Handle both old format (5 elements) and new format (6 elements)
                        if len(player_data) == 6:
                            _, player_number, player_name, _, _, _ = player_data
                        else:
                            _, player_number, player_name, _, _ = player_data
                        label = f"#{player_number}-{player_name}" if player_name else f"#{player_number}"
                        player_labels.append(label)
                    groupbox.setTitle(" / ".join(player_labels))
                
                # Get buttons for this GroupBox
                # Button naming: pushButton_{LF|MF|RF|LB|MB|RB}_{1-7}
                position_prefix = groupbox_name.replace('groupBox_', '')
                
                # Hide all buttons first
                for btn_num in range(1, 8):
                    btn_name = f"pushButton_{position_prefix}_{btn_num}"
                    btn = dialog_widget.findChild(QPushButton, btn_name)
                    if btn:
                        btn.setVisible(False)
                        btn.setEnabled(False)
                        btn.setText("")
                
                # Determine which buttons to show based on contact_number
                buttons_to_show = []
                
                if contact_number == 1:
                    # 1st contact buttons: buttons 1, 2, 3
                    if prior_contact_was_opponent_serve:
                        # Recv, Attack, Block
                        buttons_to_show = [
                            (1, 'Recv', 'receive', '#DDA0DD'),
                            (2, 'Attack', 'attack', '#E0FFFF'),
                            (3, 'Block', 'block', '#BFFF00')
                        ]
                    else:
                        # Dig, Attack, Block
                        buttons_to_show = [
                            (1, 'Dig', 'pass', '#DDA0DD'),
                            (2, 'Attack', 'attack', '#E0FFFF'),
                            (3, 'Block', 'block', '#BFFF00')
                        ]
                    # Filter by allowed_actions
                    buttons_to_show = [(num, label, action, color) for num, label, action, color in buttons_to_show if action in local_allowed_actions]
                elif contact_number == 2:
                    # 2nd contact buttons: buttons 4, 5, 6 (add Attack for team_us)
                    if team_id == self.team_us_id:
                        # For team_us, add Attack to 2nd contact
                        buttons_to_show = [
                            (4, 'Set', 'set', '#ADD8E6'),
                            (5, 'Free', 'freeball', '#90EE90'),
                            (6, 'Attack', 'attack', '#E0FFFF')
                        ]
                    else:
                        # For team_them, only Set and Free
                        buttons_to_show = [
                            (4, 'Set', 'set', '#ADD8E6'),
                            (5, 'Free', 'freeball', '#90EE90')
                        ]
                    # Filter by allowed_actions
                    buttons_to_show = [(num, label, action, color) for num, label, action, color in buttons_to_show if action in local_allowed_actions]
                elif contact_number == 3:
                    # 3rd contact buttons: buttons 6, 7
                    buttons_to_show = [
                        (6, 'Attack', 'attack', '#E0FFFF'),
                        (7, 'Free', 'freeball', '#90EE90')
                    ]
                    # Filter by allowed_actions
                    buttons_to_show = [(num, label, action, color) for num, label, action, color in buttons_to_show if action in local_allowed_actions]
                
                # Assign buttons to players in the groupbox
                # If multiple players map to same groupbox, prioritize the server (position 1 or is_server=True) or use the first one
                if players_in_groupbox:
                    # Find the server (position 1 or is_server=True) if present, otherwise use first player
                    primary_player = None
                    for player_data in players_in_groupbox:
                        # Handle both old format (5 elements) and new format (6 elements)
                        if len(player_data) == 6:
                            _, _, _, _, pos, is_server = player_data
                            if pos == 1 or is_server:  # Server position or marked as server
                                primary_player = player_data
                                break
                        else:
                            _, _, _, _, pos = player_data
                            if pos == 1:  # Server position
                                primary_player = player_data
                                break
                    if not primary_player:
                        primary_player = players_in_groupbox[0]
                    
                    # Extract player data
                    if len(primary_player) == 6:
                        player_id, player_number, player_name, role_code, position_number, is_server = primary_player
                    else:
                        player_id, player_number, player_name, role_code, position_number = primary_player
                        is_server = False
                    
                    # Show and configure buttons
                    for btn_num, btn_label, btn_action, btn_color in buttons_to_show:
                        btn_name = f"pushButton_{position_prefix}_{btn_num}"
                        btn = dialog_widget.findChild(QPushButton, btn_name)
                        if btn:
                            btn.setText(btn_label)
                            # Set button width to 60px
                            btn.setFixedWidth(60)
                            btn.setStyleSheet(f"background-color: {btn_color}; border: 1px solid #505050; padding: 1px 2px;")
                            btn.setVisible(True)
                            btn.setEnabled(True)
                            
                            # Connect button to player and action
                            def make_handler(pid, atype):
                                return lambda: (selected_action.__setitem__(0, [pid, atype]), dialog.accept())
                            btn.clicked.connect(make_handler(player_id, btn_action))
                        else:
                            print(f"DEBUG: Button {btn_name} not found")
                    
                    # If there are multiple players in this GroupBox, log a warning
                    if len(players_in_groupbox) > 1:
                        other_players = []
                        for p in players_in_groupbox:
                            if len(p) == 6:
                                _, pnum, _, _, ppos, _ = p
                            else:
                                _, pnum, _, _, ppos = p
                            if ppos != position_number:
                                other_players.append(f"#{pnum} (Pos {ppos})")
                        print(f"DEBUG POPUP: WARNING: Multiple players in {groupbox_name}: Primary=#{player_number} (Pos {position_number}), Others={other_players}")
            
            # Ensure all 6 positions are represented in GroupBoxes
            # If a position is missing, assign it to an appropriate GroupBox
            all_positions = set(range(1, 7))
            missing_positions = all_positions - assigned_positions
            if missing_positions:
                print(f"DEBUG POPUP: Missing positions in GroupBox assignments: {missing_positions}")
                # Try to assign missing positions to empty GroupBoxes
                available_groupboxes = ['groupBox_LF', 'groupBox_MF', 'groupBox_RF', 'groupBox_LB', 'groupBox_MB', 'groupBox_RB']
                used_groupboxes = set(groupbox_assignments.keys())
                empty_groupboxes = [gb for gb in available_groupboxes if gb not in used_groupboxes]
                
                # Find players for missing positions
                for missing_pos in missing_positions:
                    # Find the player at this position
                    player_at_pos = None
                    for player_data in active_players:
                        # Handle both old format (5 elements) and new format (6 elements)
                        if len(player_data) == 6:
                            _, _, _, _, pos, _ = player_data
                        else:
                            _, _, _, _, pos = player_data
                        if pos == missing_pos:
                            player_at_pos = player_data
                            break
                    
                    if player_at_pos and empty_groupboxes:
                        # Assign to first available empty GroupBox
                        assigned_gb = empty_groupboxes.pop(0)
                        groupbox_assignments[assigned_gb] = [player_at_pos]
                        assigned_positions.add(missing_pos)
                        print(f"DEBUG POPUP: Assigned missing position {missing_pos} to {assigned_gb}")
            
            # Ensure position 1 (server) is always visible and active
            # Find which GroupBox has position 1
            server_groupbox = None
            for groupbox_name, players_list in groupbox_assignments.items():
                for player_data in players_list:
                    if len(player_data) == 6:
                        _, _, _, _, pos, is_server = player_data
                    else:
                        _, _, _, _, pos = player_data
                        is_server = False
                    if pos == 1 or is_server:
                        server_groupbox = groupbox_name
                        break
                if server_groupbox:
                    break
            
            # Show/hide GroupBoxes based on assignments
            for groupbox_name in ['groupBox_LF', 'groupBox_MF', 'groupBox_RF', 'groupBox_LB', 'groupBox_MB', 'groupBox_RB']:
                groupbox = dialog_widget.findChild(QGroupBox, groupbox_name)
                if groupbox:
                    if groupbox_name in groupbox_assignments and groupbox_assignments[groupbox_name]:
                        groupbox.setVisible(True)
                        # Highlight server GroupBox if this is it
                        if groupbox_name == server_groupbox:
                            groupbox.setStyleSheet("QGroupBox { font-weight: bold; border: 2px solid #FF0000; }")
                    else:
                        groupbox.setVisible(False)
            
            # Final validation: ensure we have 6 players assigned
            total_assigned = sum(len(players) for players in groupbox_assignments.values())
            if total_assigned != 6:
                print(f"WARNING: Only {total_assigned} players assigned to GroupBoxes, expected 6")
                print(f"  GroupBox assignments: {[(gb, len(players)) for gb, players in groupbox_assignments.items()]}")
            
            # Connect down button
            down_btn = dialog_widget.findChild(QPushButton, "pushButton_down")
            if down_btn:
                down_btn.clicked.connect(lambda: (selected_action.__setitem__(0, ["down", "down"]), dialog.accept()))
            
            # Set dialog size - adjust for narrower GroupBoxes (66px each + 2px spacing = 70px per column, 3 columns = 210px + margins)
            dialog.setFixedSize(220, 280)
            
            # Position dialog to the upper right corner of the clicked point
            if self.coordinate_mapper and pixel_x is not None and pixel_y is not None:
                mapper_pos = self.coordinate_mapper.mapToGlobal(QPoint(0, 0))
                # Position to upper right: x = click + offset, y = click - dialog height
                dialog_x = mapper_pos.x() + int(pixel_x) + 10  # 10 pixels to the right
                dialog_y = mapper_pos.y() + int(pixel_y) - 280  # Above the click point
                dialog.move(dialog_x, dialog_y)
            elif pixel_x is not None and pixel_y is not None:
                # Fallback: use logical coordinates for positioning
                dialog_x = int(pixel_x) + 10
                dialog_y = int(pixel_y) - 280
                dialog.move(dialog_x, dialog_y)
            
            # Show dialog and get result (for new UI)
            # Use safe_allowed_actions instead of allowed_actions to avoid UnboundLocalError
            try:
                _allowed_actions_backup = list(safe_allowed_actions)
                print(f"DEBUG ALLOWED_ACTIONS: In new UI - _allowed_actions_backup={_allowed_actions_backup}")
            except (NameError, UnboundLocalError) as e:
                print(f"DEBUG ERROR: Failed to create _allowed_actions_backup: {e}")
                _allowed_actions_backup = []
            
            try:
                print(f"DEBUG: About to show dialog for team {team_id}, contact_number={contact_number}, action_type will be selected")
                if dialog.exec() == QDialog.Accepted and selected_action[0]:
                    player_id_or_down, action_type = selected_action[0]
                    print(f"DEBUG: Dialog accepted, action_type={action_type}, player_id={player_id_or_down}")
                    
                    # Set flag BEFORE calling record_contact to prevent error dialogs from showing
                    self._recording_contact = True
                    
                    # Check if "down" was selected (floor contact)
                    if player_id_or_down == "down":
                        self.selected_player_id = None
                        self.selected_player_number = None
                        self.selected_team_id = team_id
                        if hasattr(self, 'status_label'):
                            self.status_label.setText("Recording floor contact (down)...")
                        self.record_contact("down")
                    else:
                        # Set the selected player
                        self.selected_player_id = player_id_or_down
                        self.selected_team_id = team_id
                        
                        # Get player info for status message
                        if not self.db.conn:
                            self.db.connect()
                        cursor = self.db.conn.cursor()
                        cursor.execute("""
                            SELECT player_number, name
                            FROM players
                            WHERE player_id = ?
                        """, (player_id_or_down,))
                        player_info = cursor.fetchone()
                        if player_info:
                            player_number, player_name = player_info
                            self.selected_player_number = str(player_number)
                            player_display = f"#{player_number} {player_name}" if player_name else f"#{player_number}"
                            if hasattr(self, 'status_label'):
                                self.status_label.setText(f"Selected: {player_display} - Recording {action_type}...")
                        
                        # Record the contact with the selected action type
                        self.record_contact(action_type)
            except UnboundLocalError as e:
                error_msg = str(e)
                print(f"DEBUG ERROR: UnboundLocalError in show_player_selection_dialog (new UI): {error_msg}")
                print(f"DEBUG ERROR: Traceback: {e.__traceback__}")
                if 'allowed_actions' in error_msg or 'safe_allowed_actions' in error_msg:
                    print(f"DEBUG ERROR: Scoping issue with allowed_actions. Backup value: {_allowed_actions_backup}")
                    print(f"DEBUG ERROR: contact_number={contact_number}, team_id={team_id}")
                    # Don't show error popup - this is a scoping issue that's been handled
                    return
                # Re-raise if it's not an allowed_actions issue
                raise
            except NameError as e:
                error_msg = str(e)
                print(f"DEBUG ERROR: NameError in show_player_selection_dialog (new UI): {error_msg}")
                if 'allowed_actions' in error_msg or 'safe_allowed_actions' in error_msg:
                    print(f"DEBUG ERROR: NameError with allowed_actions. Backup value: {_allowed_actions_backup}")
                    print(f"DEBUG ERROR: contact_number={contact_number}, team_id={team_id}")
                    # Don't show error popup - this is a scoping issue that's been handled
                    return
                # Re-raise if it's not an allowed_actions issue
                raise
            except Exception as e:
                error_msg = str(e)
                import traceback
                print(f"DEBUG ERROR: Exception in show_player_selection_dialog (new UI): {error_msg}")
                print(f"DEBUG ERROR: Exception type: {type(e).__name__}")
                print(f"DEBUG ERROR: Full traceback:")
                traceback.print_exc()
                if 'allowed_actions' in error_msg or 'safe_allowed_actions' in error_msg:
                    # Don't show error popup for allowed_actions scoping issues
                    print(f"DEBUG ERROR: Allowed actions issue detected, returning silently")
                    return
                # Only re-raise if it's not an allowed_actions issue
                # But wrap it to prevent it from showing an error dialog
                print(f"DEBUG ERROR: Re-raising exception (not allowed_actions related)")
                raise
            
        else:
            # Old dialog implementation for team_them
            # Create compact dialog with no title bar
            dialog = QDialog(self.coordinate_mapper if self.coordinate_mapper else self)
            dialog.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
            dialog.setModal(True)
            
            main_layout = QVBoxLayout()
            main_layout.setContentsMargins(3, 3, 3, 3)
            main_layout.setSpacing(2)
            
            # Store selected action info
            selected_action = [None]  # [player_id, action_type] or ["down", "down"]
            
            # Define action colors matching the player-contact grid
            action_colors = {
                'receive': '#FFB3B3',    # light red
                'pass': '#DDA0DD',       # light purple (plum) - for Dig
                'set': '#ADD8E6',        # light blue
                'attack': '#E0FFFF',     # light cyan
                'freeball': '#90EE90',   # light green
                'block': '#BFFF00'       # lime (light yellowish-green)
            }
            
            # Create a row for each player with action buttons
            for player_id, player_number, player_name in players:
                row_layout = QHBoxLayout()
            row_layout.setSpacing(2)
            row_layout.setContentsMargins(0, 0, 0, 0)
            
            # Player label
            player_text = f"#{player_number} - {player_name}" if player_name else f"#{player_number}"
            player_label = QLabel(player_text)
            player_label.setFont(QFont('Arial', 9))
            player_label.setFixedWidth(100)
            row_layout.addWidget(player_label, 0)  # 0 stretch factor
            
            # Action buttons - only show allowed actions
            actions = [
                ("Rcv", "receive"),
                ("Dig", "pass"),
                ("Set", "set"),
                ("Atk", "attack"),
                ("Free", "freeball"),
                ("Blk", "block")
            ]
            
            # Store allowed_actions in local variable to avoid closure issues
            # Use the safe copy we created earlier to avoid UnboundLocalError
            try:
                local_allowed_actions = list(safe_allowed_actions)
                print(f"DEBUG ALLOWED_ACTIONS: In old UI - local_allowed_actions={local_allowed_actions}")
            except (NameError, UnboundLocalError) as e:
                print(f"DEBUG ERROR: Failed to access safe_allowed_actions in old UI: {e}")
                # Fallback based on contact_number
                if contact_number == 3:
                    local_allowed_actions = ['attack', 'freeball']
                elif contact_number == 2:
                    local_allowed_actions = ['set', 'attack', 'freeball']
                else:
                    local_allowed_actions = ['receive', 'pass', 'set', 'attack', 'freeball']
                print(f"DEBUG ALLOWED_ACTIONS: Using fallback - local_allowed_actions={local_allowed_actions}")
            except (AttributeError, TypeError) as e:
                print(f"DEBUG ERROR: Failed to copy safe_allowed_actions: {e}")
                local_allowed_actions = ['attack', 'freeball'] if contact_number == 3 else []
            
            for action_label, action_type in actions:
                # Only show button if action is allowed for this contact number
                if action_type not in local_allowed_actions:
                    continue
                
                btn = QPushButton(action_label)
                btn.setFont(QFont('Arial', 8))
                btn.setFixedWidth(40)
                btn.setFixedHeight(22)
                
                # Apply background color with border
                color = action_colors.get(action_type, '#FFFFFF')
                btn.setStyleSheet(f"background-color: {color}; border: 1px solid #505050;")
                
                # Create closure to capture current player_id and action_type
                def make_handler(pid, atype):
                    return lambda: (selected_action.__setitem__(0, [pid, atype]), dialog.accept())
                
                btn.clicked.connect(make_handler(player_id, action_type))
                row_layout.addWidget(btn, 0)  # 0 stretch factor
            
                main_layout.addLayout(row_layout)
            
            # Add "down" button at the bottom for floor contact
            down_layout = QHBoxLayout()
            down_btn = QPushButton("down (floor contact)")
            down_btn.setFont(QFont('Arial', 9))
            down_btn.clicked.connect(lambda: (selected_action.__setitem__(0, ["down", "down"]), dialog.accept()))
            down_layout.addWidget(down_btn)
            main_layout.addLayout(down_layout)
            
            dialog.setLayout(main_layout)
            
            # Set size - compact width for player name + buttons, tall enough for all players
            dialog.setFixedWidth(320)
            # Calculate height: each row is ~26px, plus padding
            total_rows = len(players) + 1  # +1 for "down" button
            dialog.setFixedHeight(total_rows * 26 + 20)
            
            # Position dialog to the right of the clicked point
            # Use pixel coordinates if available (from coordinate mapper)
            if self.coordinate_mapper and pixel_x is not None and pixel_y is not None:
                # Get the coordinate mapper's global position
                mapper_pos = self.coordinate_mapper.mapToGlobal(QPoint(0, 0))
                # Position dialog to the right of the click point
                dialog_x = mapper_pos.x() + int(pixel_x) + 20  # 20 pixels to the right
                dialog_y = mapper_pos.y() + int(pixel_y) - 50  # Adjust to center on click
                dialog.move(dialog_x, dialog_y)
            elif pixel_x is not None and pixel_y is not None:
                # Fallback: use logical coordinates for positioning
                dialog_x = int(pixel_x) + 20
                dialog_y = int(pixel_y) - 50
                dialog.move(dialog_x, dialog_y)
            
            # Show dialog and get result
            # Use safe_allowed_actions instead of allowed_actions to avoid UnboundLocalError
            _allowed_actions_backup = list(safe_allowed_actions)
            print(f"DEBUG ALLOWED_ACTIONS: In old UI - _allowed_actions_backup={_allowed_actions_backup}")
            
            try:
                if dialog.exec() == QDialog.Accepted and selected_action[0]:
                    # Set flag BEFORE calling record_contact to prevent error dialogs from showing
                    self._recording_contact = True
                    
                    player_id_or_down, action_type = selected_action[0]
                    
                    # Check if "down" was selected (floor contact)
                    if player_id_or_down == "down":
                        # Record floor contact
                        self.selected_player_id = None
                        self.selected_player_number = None
                        self.selected_team_id = team_id
                        self.status_label.setText("Recording floor contact (down)...")
                        self.record_contact("down")
                    else:
                        # Set the selected player
                        self.selected_player_id = player_id_or_down
                        self.selected_team_id = team_id
                        
                        # Get player info for status message
                        if not self.db.conn:
                            self.db.connect()
                        cursor = self.db.conn.cursor()
                        cursor.execute("""
                            SELECT player_number, name
                            FROM players
                            WHERE player_id = ?
                        """, (player_id_or_down,))
                        player_info = cursor.fetchone()
                        if player_info:
                            player_number, player_name = player_info
                            self.selected_player_number = str(player_number)
                            player_display = f"#{player_number} {player_name}" if player_name else f"#{player_number}"
                            self.status_label.setText(f"Selected: {player_display} - Recording {action_type}...")
                        
                        # Record the contact with the selected action type
                        self.record_contact(action_type)
            except UnboundLocalError as e:
                # Catch scoping errors - this shouldn't happen, but if it does, log and continue
                error_msg = str(e)
                print(f"DEBUG ERROR: UnboundLocalError in show_player_selection_dialog: {error_msg}")
                if 'allowed_actions' in error_msg:
                    print(f"DEBUG ERROR: Scoping issue with allowed_actions. Backup value: {_allowed_actions_backup}")
                    # Don't show error popup - this is a scoping issue that's been handled
                    return
                # Don't re-raise - the contact may have already been recorded
            except Exception as e:
                # Log other exceptions but don't show error popup if contact was already recorded
                error_msg = str(e)
                print(f"DEBUG ERROR: Exception in show_player_selection_dialog: {error_msg}")
                # Don't show error popup for allowed_actions scoping issues
                if 'allowed_actions' in error_msg:
                    return
                # Only re-raise if it's not an allowed_actions issue
                raise
    
    def eventFilter(self, obj, event):
        """Event filter to capture mouse clicks on outerCourt and court sides."""
        # If coordinate mapper is configured and enabled, clicks should go to mapper instead
        # (The mapper will emit signals that we handle in on_coordinate_mapped)
        # For now, we still allow clicks on the court widgets for backward compatibility
        # but they won't be used if coordinate mapper is enabled
        
        # Handle clicks on courtSide_A
        if hasattr(self.ui, 'courtSide_A') and obj == self.ui.courtSide_A and event.type() == QEvent.Type.MouseButtonPress:
            # If coordinate mapper is enabled and configured, don't process these clicks
            if self.use_coordinate_mapper and self.coordinate_mapper and self.coordinate_mapper.is_configured():
                return False
            
            click_pos = event.position().toPoint()
            x = click_pos.x()
            y = click_pos.y()
            
            # Get widget dimensions
            widget_height = self.ui.courtSide_A.height()
            
            # Convert to coordinate system with lower-left as (0,0)
            x_coord = x
            y_coord = widget_height - y
            
            # Store coordinates and side
            self.last_clicked_x = x_coord
            self.last_clicked_y = y_coord
            self.last_clicked_side = 'A'
            
            # Display in tempXYcoord label
            if hasattr(self.ui, 'tempXYcoord'):
                self.ui.tempXYcoord.setText(f"({x_coord}, {y_coord}) Side A")
            
            # Determine which team based on Y coordinate and show player selection
            if self.game_id and self.rally_in_progress:
                # Y > 300 is far side (team B), Y <= 300 is near side (team A)
                team_id = self.team_them_id if y_coord > 300 else self.team_us_id
                self.show_player_selection_dialog(team_id, x_coord, y_coord, x, y)
            
            return False
        
        # Handle clicks on courtSide_B
        if hasattr(self.ui, 'courtSide_B') and obj == self.ui.courtSide_B and event.type() == QEvent.Type.MouseButtonPress:
            # If coordinate mapper is enabled and configured, don't process these clicks
            if self.use_coordinate_mapper and self.coordinate_mapper and self.coordinate_mapper.is_configured():
                return False
            
            click_pos = event.position().toPoint()
            x = click_pos.x()
            y = click_pos.y()
            
            # Get widget dimensions
            widget_height = self.ui.courtSide_B.height()
            
            # Convert to coordinate system with lower-left as (0,0)
            x_coord = x
            y_coord = widget_height - y
            
            # Store coordinates and side
            self.last_clicked_x = x_coord
            self.last_clicked_y = y_coord
            self.last_clicked_side = 'B'
            
            # Display in tempXYcoord label
            if hasattr(self.ui, 'tempXYcoord'):
                self.ui.tempXYcoord.setText(f"({x_coord}, {y_coord}) Side B")
            
            # Determine which team based on Y coordinate and show player selection
            if self.game_id and self.rally_in_progress:
                # Y > 300 is far side (team B), Y <= 300 is near side (team A)
                team_id = self.team_them_id if y_coord > 300 else self.team_us_id
                self.show_player_selection_dialog(team_id, x_coord, y_coord, x, y)
            
            return False
        
        # Handle clicks on outerCourt (for backward compatibility)
        if hasattr(self.ui, 'outerCourt') and obj == self.ui.outerCourt and event.type() == QEvent.Type.MouseButtonPress:
            # If coordinate mapper is enabled and configured, don't process these clicks
            if self.use_coordinate_mapper and self.coordinate_mapper and self.coordinate_mapper.is_configured():
                return False
            
            # Get click position relative to the widget
            click_pos = event.position().toPoint()
            x = click_pos.x()
            y = click_pos.y()
            
            # Get widget dimensions
            widget_height = self.ui.outerCourt.height()
            
            # Convert to coordinate system with lower-left as (0,0)
            # Qt uses top-left as (0,0), so we need to invert y
            x_coord = x
            y_coord = widget_height - y
            
            # Store the coordinates for the next contact
            self.last_clicked_x = x_coord
            self.last_clicked_y = y_coord
            self.last_clicked_side = None  # outerCourt doesn't have a side
            
            # Display in tempXYcoord label
            if hasattr(self.ui, 'tempXYcoord'):
                self.ui.tempXYcoord.setText(f"({x_coord}, {y_coord})")
            
            # Determine which team based on Y coordinate and show player selection
            if self.game_id and self.rally_in_progress:
                # Y > 300 is far side (team B), Y <= 300 is near side (team A)
                team_id = self.team_them_id if y_coord > 300 else self.team_us_id
                self.show_player_selection_dialog(team_id, x_coord, y_coord, x, y)
            
            # Return False to allow normal event processing to continue
            return False
        
        # For all other events, use default processing
        return super().eventFilter(obj, event)
    
    def set_selected_player(self, player_number):
        """Set the selected player for the next contact.
        
        Args:
            player_number: Player number (can be alphanumeric) or "opp" for opponent
        """
        if not self.game_id:
            QMessageBox.warning(self, "No Game Selected", "Please select a game first!")
            return
        
        if player_number == "opp":
            self.selected_player_number = None
            self.selected_team_id = self.team_them_id
            self.status_label.setText("Selected: Opponent")
        else:
            # Convert to string to handle both numeric and alphanumeric
            player_number_str = str(player_number)
            self.selected_player_number = player_number_str
            self.selected_team_id = self.team_us_id
            # Get player_id - for team_us, check active_lineup first
            if not self.db.conn:
                self.db.connect()
            
            player = None
            cursor = self.db.conn.cursor()
            cursor.execute("""
                SELECT p.player_id, p.player_number, p.name, p.jersey
                FROM active_lineup al
                INNER JOIN players p ON al.player_id = p.player_id
                WHERE al.game_id = ? AND al.team_id = ? 
                AND (p.player_number = ? OR CAST(p.jersey AS TEXT) = ?)
            """, (self.game_id, self.team_us_id, player_number_str, player_number_str))
            result = cursor.fetchone()
            if result:
                player = {
                    'player_id': result[0],
                    'player_number': result[1],
                    'name': result[2],
                    'jersey': result[3]
                }
            
            # Fall back to game_players if not found in active_lineup
            if not player:
                player = self.db.get_player_by_number_for_game(self.game_id, self.team_us_id, player_number_str)
            
            if player:
                self.selected_player_id = player['player_id']
                self.status_label.setText(f"Selected: Player {player_number_str}")
            else:
                QMessageBox.warning(self, "Player Not Found", 
                                  f"Player {player_number_str} not found in this game. Please add players to the game first.")
                self.selected_player_number = None
                self.selected_team_id = None
                return
        
        self.update_ui_state()
    
    def handle_player_action(self, player_number: str, action: str):
        """Handle a player-specific action button click.
        
        Args:
            player_number: Player number (can be alphanumeric like "1", "o1", etc.)
            action: The action type (receive, pass, set, attack, freeball, block, serve)
        """
        if not self.game_id:
            QMessageBox.warning(self, "No Game Selected", "Please select a game first!")
            return
        
        # Determine team based on player number
        if player_number.startswith('o'):
            # Opponent player
            team_id = self.team_them_id
            player_number_str = player_number
        else:
            # Our team player
            team_id = self.team_us_id
            player_number_str = str(player_number)
            # For team_us, check active_lineup first
            if not self.db.conn:
                self.db.connect()
            cursor = self.db.conn.cursor()
            cursor.execute("""
                SELECT p.player_id, p.player_number, p.name, p.jersey
                FROM active_lineup al
                INNER JOIN players p ON al.player_id = p.player_id
                WHERE al.game_id = ? AND al.team_id = ? 
                AND (p.player_number = ? OR CAST(p.jersey AS TEXT) = ?)
            """, (self.game_id, self.team_us_id, player_number_str, player_number_str))
            result = cursor.fetchone()
            if result:
                self.selected_player_id = result[0]
                self.selected_team_id = self.team_us_id
                self.selected_player_number = player_number_str
                # Record the contact
                self.record_contact(action)
                return
        
        # Set the selected player/team
        if player_number.startswith('o'):
            # Opponent player - use the full player number as stored in database (e.g., "o1")
            opponent_player_number = player_number  # Keep the full "o1", "o2", etc.
            self.selected_team_id = self.team_them_id
            self.selected_player_number = opponent_player_number
            # Get player_id from database for opponent player (always use game_players for opponents)
            if not self.db.conn:
                self.db.connect()
            player = self.db.get_player_by_number_for_game(self.game_id, self.team_them_id, opponent_player_number)
            if player:
                self.selected_player_id = player['player_id']
            else:
                QMessageBox.warning(self, "Player Not Found", 
                                  f"Opponent player {opponent_player_number} not found in this game. Please add players to the game first.")
                return
        else:
            # Our team player - already handled above with active_lineup check
            # If we get here, player wasn't found in active_lineup, so fall back to game_players
            if not self.db.conn:
                self.db.connect()
            player = self.db.get_player_by_number_for_game(self.game_id, self.team_us_id, player_number_str)
            if player:
                self.selected_player_id = player['player_id']
                self.selected_team_id = self.team_us_id
                self.selected_player_number = player_number_str
            else:
                QMessageBox.warning(self, "Player Not Found", 
                                  f"Player {player_number_str} not found in this game. Please add players to the game first.")
                return
        
        # Check if coordinate mapper is ready before recording
        # If mapper is configured, check if we already have coordinates
        if self.coordinate_mapper and self.coordinate_mapper.is_configured():
            # If we don't have coordinates yet, enable mapper mode and wait
            if self.last_clicked_x is None or self.last_clicked_y is None:
                self.use_coordinate_mapper = True
                # Show message to user to click in coordinate mapper window
                self.status_label.setText(f"Click in Coordinate Mapper window to set {action} location, then click {action} button again")
                # Don't record yet - wait for coordinate to be captured
                return
            # If we have coordinates, proceed to record (mapper was already used)
        
        # Record the contact
        self.record_contact(action)
    
    def record_contact(self, contact_type: str):
        """Record a ball contact."""
        # Flag should be set before calling this function to prevent error dialogs from showing
        # If not set, set it here as a safety measure
        if not getattr(self, '_recording_contact', False):
            self._recording_contact = True
        print(f"DEBUG RECORD: ========================================")
        print(f"DEBUG RECORD: record_contact called for contact_type='{contact_type}'")
        print(f"DEBUG RECORD: game_id={self.game_id}, rally_in_progress={self.rally_in_progress}")
        print(f"DEBUG RECORD: selected_team_id={self.selected_team_id}, selected_player_id={getattr(self, 'selected_player_id', None)}")
        print(f"DEBUG RECORD: selected_player_number={self.selected_player_number}")
        
        if not self.game_id:
            QMessageBox.warning(self, "No Game Selected", "Please select a game first!")
            return
        
        print(f"DEBUG RECORD: last_clicked_x={self.last_clicked_x}, last_clicked_y={self.last_clicked_y}")
        
        # If rally not started, must start with serve
        if not self.rally_in_progress:
            if contact_type != "serve":
                QMessageBox.warning(self, "Invalid Action", 
                                  "Rally must start with a serve!")
                return
            
            # For serve, determine team from selected player/team
            if not self.selected_team_id:
                QMessageBox.warning(self, "No Player Selected", 
                                  "Please select a player to serve!")
                return
            
            # Use the selected team for serving
            serving_team_id = self.selected_team_id
            
            # Start new rally
            if not self.db.conn:
                self.db.connect()
            
            print(f"DEBUG RECORD: Starting new rally - game_id={self.game_id}, rally_number={self.current_rally_number}, serving_team_id={serving_team_id}")
            self.current_rally_id = self.db.start_rally(
                game_id=self.game_id,
                rally_number=self.current_rally_number,
                serving_team_id=serving_team_id
            )
            print(f"DEBUG RECORD: Rally started! rally_id={self.current_rally_id}")
            self.rally_in_progress = True
            self.current_sequence = 1
            # Clear expected server since rally has started
            self.expected_next_server_team_id = None
            
            # For serve, use selected team and player
            team_id = self.selected_team_id
            player_id = getattr(self, 'selected_player_id', None)
            print(f"DEBUG RECORD: Serve contact - team_id={team_id}, player_id={player_id}")
        else:
            # Regular contact - must have selected a player/team
            if not self.selected_team_id:
                QMessageBox.warning(self, "No Player Selected", 
                                  "Please select a player or 'opp' first!")
                return
            
            team_id = self.selected_team_id
            player_id = None
            
            # Get player_id if we have one selected (for both our team and opponent team)
            if hasattr(self, 'selected_player_id') and self.selected_player_id is not None:
                player_id = self.selected_player_id
            
            self.current_sequence = self.db.get_current_rally_sequence(self.current_rally_id)
        
        # Add contact to database
        try:
            # Get the stored x,y coordinates from the last court click
            x_coord = self.last_clicked_x
            y_coord = self.last_clicked_y
            
            # Convert coordinates to integers if they are floats (from coordinate mapper)
            # Database expects INTEGER type
            if x_coord is not None:
                x_coord = int(round(x_coord))
            if y_coord is not None:
                y_coord = int(round(y_coord))
            
            # Warn if no location was clicked (but still allow the contact to be recorded)
            if x_coord is None or y_coord is None:
                # Optional: You can uncomment this to require location before contact
                # QMessageBox.warning(self, "No Location", 
                #                   "Please click on the court to set the location first!")
                # return
                pass  # Allow contact without location (x,y will be NULL in database)
            
            # Get timecode
            timecode_ms = self.last_clicked_timecode
            
            # Debug output
            print(f"DEBUG: Recording contact with coordinates: x={x_coord}, y={y_coord}, timecode={timecode_ms}ms")
            
            # Detect court side based on Y coordinate
            # Y <= 300 is team_us side, Y > 300 is team_them side
            is_team_us_side = y_coord <= 300 if y_coord is not None else None
            
            # If click is on team_us side, this is team_us's first contact
            if is_team_us_side is True and team_id != self.team_us_id:
                # Click is on team_us side but team_id was set to team_them
                # This means team_them sent the ball to team_us side - switch to team_us
                team_id = self.team_us_id
                self.selected_team_id = team_id
                # Reset player selection since we're switching teams
                player_id = None
                self.selected_player_id = None
                print(f"DEBUG: Click on team_us side (Y={y_coord}) - switching to team_us first contact")
            
            # Block detection based on Y coordinate
            # If contact_type is block, check Y coordinate to determine team
            if contact_type == "block" and y_coord is not None:
                # Y coordinate 301-315: team_them contacted and sent back to team_us side
                # Y coordinate 285-301: team_us contacted and sent back to team_them side
                if 301 <= y_coord <= 315:
                    # team_them blocked and sent back to team_us side
                    team_id = self.team_them_id
                    print(f"DEBUG: Block detected at Y={y_coord} - team_them blocked")
                    # Update selected_team_id to match for consistency
                    self.selected_team_id = team_id
                elif 285 <= y_coord < 301:
                    # team_us blocked and sent back to team_them side
                    team_id = self.team_us_id
                    print(f"DEBUG: Block detected at Y={y_coord} - team_us blocked")
                    # Update selected_team_id to match for consistency
                    self.selected_team_id = team_id
                # Note: If Y is outside these ranges, use the originally selected team_id
            
            # Set outcome for contacts
            # Check if there's a pending outcome (e.g., from 4th contact error)
            if hasattr(self, '_pending_contact_outcome') and self._pending_contact_outcome:
                outcome = self._pending_contact_outcome
            elif contact_type in ("down", "net", "fault"):
                outcome = "down"
            elif contact_type == "block":
                # Block outcome is always "continue"
                outcome = "continue"
            else:
                outcome = "continue"
            
            print(f"DEBUG RECORD: >>> WRITING TO DATABASE <<<")
            print(f"DEBUG RECORD:   rally_id={self.current_rally_id}")
            print(f"DEBUG RECORD:   sequence_number={self.current_sequence}")
            print(f"DEBUG RECORD:   contact_type='{contact_type}'")
            print(f"DEBUG RECORD:   team_id={team_id}")
            print(f"DEBUG RECORD:   player_id={player_id}")
            print(f"DEBUG RECORD:   x={x_coord}, y={y_coord}")
            print(f"DEBUG RECORD:   timecode={timecode_ms}")
            print(f"DEBUG RECORD:   outcome='{outcome}'")
            
            contact_id = self.db.add_contact(
                rally_id=self.current_rally_id,
                sequence_number=self.current_sequence,
                contact_type=contact_type,
                team_id=team_id,
                player_id=player_id,
                x=x_coord,
                y=y_coord,
                timecode=timecode_ms,
                outcome=outcome
            )
            
            print(f"DEBUG RECORD: *** SUCCESS! Contact saved with contact_id={contact_id} ***")
            
            # If this is a "down" contact, check if the previous contact was a block
            # If so, update the block's outcome to "stuff"
            if contact_type == "down":
                if not self.db.conn:
                    self.db.connect()
                cursor = self.db.conn.cursor()
                cursor.execute("""
                    SELECT contact_id, contact_type, team_id
                    FROM contacts
                    WHERE rally_id = ? AND sequence_number < ?
                    ORDER BY sequence_number DESC
                    LIMIT 1
                """, (self.current_rally_id, self.current_sequence))
                result = cursor.fetchone()
                if result:
                    prev_contact_id, prev_contact_type, prev_team_id = result
                    if prev_contact_type == "block":
                        # Previous contact was a block - update its outcome to "stuff"
                        self.db.update_contact_outcome(prev_contact_id, "stuff")
                        print(f"DEBUG: Updated block contact {prev_contact_id} outcome to 'stuff' (next contact was 'down')")
            
            # Reset opponent contact count if this was a team A contact (not opponent)
            if team_id == self.team_us_id:
                self.opponent_contact_count = 0
            
            # Save player number for status message before clearing
            recorded_player_number = self.selected_player_number
            
            # Clear the stored coordinates and timecode after recording
            self.last_clicked_x = None
            self.last_clicked_y = None
            self.last_clicked_timecode = None
            
            # Clear the coordinate display
            if hasattr(self.ui, 'tempXYcoord'):
                self.ui.tempXYcoord.setText("")
            
            # Clear selection after recording
            self.selected_player_number = None
            self.selected_team_id = None
            
            # Update status with recorded info
            if self.use_coordinate_mapper:
                self.use_coordinate_mapper = False
                self.status_label.setText(f"Contact recorded: #{recorded_player_number or '?'} {contact_type}. Click for next location.")
            elif self.use_voice_input:
                self.status_label.setText(f"Contact recorded: #{recorded_player_number or '?'} {contact_type}. Click for next location, then speak.")
            else:
                self.status_label.setText(f"Contact recorded: #{recorded_player_number or '?'} {contact_type}. Select player for next contact.")
            
            self.update_ui_state()
            
            # Clear flag after recording is complete
            self._recording_contact = False
            
        except Exception as e:
            # Clear flag even if there's an error
            self._recording_contact = False
            QMessageBox.critical(self, "Database Error", f"Failed to record contact:\n{str(e)}")
    
    def assign_rally_outcomes(self, rally_id: int, point_winner_id: int):
        """Determine and assign outcomes to contacts in a rally based on rules.
        
        Rules:
        - Ace: Serve that directly wins the point (serve by winning team, no or minimal opponent contacts)
               OR serve followed immediately by a receive error
        - Kill: Attack that wins the point (attack by winning team)
                OR attack/freeball/block followed immediately by a pass error
        - Stuff: Block that wins the point (block by winning team)
        - Error: Contact by losing team that causes them to lose the point
        - Down: Ball contact with the floor (set when floor contact is recorded)
        - Continue: All other contacts (default)
        
        Additional rules:
        - When receive has error, mark prior serve as ace
        - When pass has error, mark prior attack/freeball/block as kill
        - When block wins the point (stuff), mark prior contact as error
        
        Args:
            rally_id: The rally ID
            point_winner_id: The team that won the point
        """
        if not self.db.conn:
            self.db.connect()
        
        # Get all contacts in this rally
        contacts = self.db.get_rally_contacts(rally_id)
        
        if not contacts:
            return
        
        # Determine losing team
        losing_team_id = self.team_them_id if point_winner_id == self.team_us_id else self.team_us_id
        
        # Find the last contact by each team (excluding 'down' contacts)
        last_winning_team_contact = None
        last_losing_team_contact = None
        
        for contact in contacts:
            contact_id = contact[0]
            contact_type = contact[4]
            team_id = contact[5]
            
            # Skip floor contacts ('down')
            if contact_type == 'down':
                continue
            
            if team_id == point_winner_id:
                last_winning_team_contact = contact
            else:
                last_losing_team_contact = contact
        
        # Determine the outcome based on rules
        # Check if the last contact was by the losing team (indicating an error)
        # or by the winning team (indicating ace or kill)
        
        # Check if the very last contact is a "down" (manually recorded via double-click)
        # If so, skip automatic error assignment for losing team contacts
        last_contact_is_manual_down = False
        last_contact = contacts[-1] if contacts else None
        if last_contact and last_contact[4] == 'down':
            # Last contact is a manually recorded "down" - skip automatic error assignment
            last_contact_is_manual_down = True
            print(f"DEBUG: Last contact is manually recorded 'down' - will skip automatic error assignment")
        
        # Get the very last player contact (not floor contact)
        last_player_contact = None
        for contact in reversed(contacts):
            if contact[4] != 'down':  # contact_type != 'down'
                last_player_contact = contact
                break
        
        if not last_player_contact:
            return
        
        contact_id = last_player_contact[0]
        contact_type = last_player_contact[4]
        team_id = last_player_contact[5]
        
        outcome = 'continue'  # Default
        
        # If the last contact was by the losing team, it's an error
        # BUT: skip this if the last contact was a manually recorded "down"
        if team_id == losing_team_id and not last_contact_is_manual_down:
            outcome = 'error'
            print(f"DEBUG: Contact {contact_id} ({contact_type}) assigned outcome 'error' (losing team contact)")
        elif team_id == losing_team_id and last_contact_is_manual_down:
            # Skip automatic error assignment when "down" was manually recorded
            print(f"DEBUG: Contact {contact_id} ({contact_type}) - skipping error assignment (manual 'down' recorded)")
        
        # If the last contact was by the winning team
        elif team_id == point_winner_id:
            # Check if it's a serve (could be an ace)
            if contact_type == 'serve':
                # It's an ace if:
                # 1. The serve was by the winning team, AND
                # 2. There are no or very few opponent contacts after it
                opponent_contacts_after_serve = 0
                for contact in contacts:
                    if contact[4] != 'down' and contact[5] == losing_team_id:
                        opponent_contacts_after_serve += 1
                
                # If opponent had 0 or 1 contacts, it's an ace
                if opponent_contacts_after_serve <= 1:
                    outcome = 'ace'
                    print(f"DEBUG: Contact {contact_id} (serve) assigned outcome 'ace' (winning serve with {opponent_contacts_after_serve} opponent contacts)")
            
            # Check if it's an attack (could be a kill)
            elif contact_type == 'attack':
                outcome = 'kill'
                print(f"DEBUG: Contact {contact_id} (attack) assigned outcome 'kill' (winning attack)")
            
            # Check if it's a block (could be a stuff)
            elif contact_type == 'block':
                outcome = 'stuff'
                print(f"DEBUG: Contact {contact_id} (block) assigned outcome 'stuff' (winning block)")
        
        # Update the outcome for this contact
        if outcome != 'continue':
            self.db.update_contact_outcome(contact_id, outcome)
        
        # Additional rules: Set outcomes for prior contacts based on subsequent errors
        # Rule 1: If receive has error, mark prior serve as ace
        # Rule 2: If pass has error, mark prior attack/freeball/block as kill
        for i, contact in enumerate(contacts):
            contact_id = contact[0]
            contact_type = contact[4]
            current_outcome = contact[8]  # outcome is at index 8
            
            # Rule 1: If this is a receive with error, find prior serve and mark it as ace
            if contact_type == 'receive' and current_outcome == 'error':
                # Look backwards for a serve
                for j in range(i - 1, -1, -1):
                    prior_contact = contacts[j]
                    prior_contact_id = prior_contact[0]
                    prior_contact_type = prior_contact[4]
                    
                    if prior_contact_type == 'serve':
                        # Mark this serve as an ace
                        self.db.update_contact_outcome(prior_contact_id, 'ace')
                        print(f"DEBUG: Contact {prior_contact_id} (serve) assigned outcome 'ace' (subsequent receive error)")
                        break  # Only mark the immediate prior serve
            
            # Rule 2: If this is a pass with error, find prior attack/freeball/block and mark it as kill
            elif contact_type == 'pass' and current_outcome == 'error':
                # Look backwards for an attack, freeball, or block
                for j in range(i - 1, -1, -1):
                    prior_contact = contacts[j]
                    prior_contact_id = prior_contact[0]
                    prior_contact_type = prior_contact[4]
                    
                    if prior_contact_type in ['attack', 'freeball', 'block']:
                        # Mark this attack/freeball/block as a kill
                        self.db.update_contact_outcome(prior_contact_id, 'kill')
                        print(f"DEBUG: Contact {prior_contact_id} ({prior_contact_type}) assigned outcome 'kill' (subsequent pass error)")
                        break  # Only mark the immediate prior attack/freeball/block
            
            # Rule 3: If this is a block with stuff outcome, mark prior contact as error
            elif contact_type == 'block' and current_outcome == 'stuff':
                # Look backwards for the prior contact (should be an attack, but could be anything)
                for j in range(i - 1, -1, -1):
                    prior_contact = contacts[j]
                    prior_contact_id = prior_contact[0]
                    prior_contact_type = prior_contact[4]
                    
                    # Skip 'down' contacts
                    if prior_contact_type == 'down':
                        continue
                    
                    # Mark the prior contact as error
                    self.db.update_contact_outcome(prior_contact_id, 'error')
                    print(f"DEBUG: Contact {prior_contact_id} ({prior_contact_type}) assigned outcome 'error' (subsequent stuff block)")
                    break  # Only mark the immediate prior player contact
    
    def end_rally(self, point_winner_id: int):
        """End the current rally and award point. Records floor contact if coordinates are available."""
        if not self.game_id:
            QMessageBox.warning(self, "No Game Selected", "Please select a game first!")
            return
        
        if not self.rally_in_progress:
            QMessageBox.warning(self, "No Rally", "No rally in progress!")
            return
        
        try:
            # Before ending the rally, record a floor contact if coordinates are available
            # This represents where the ball hit the floor
            if self.last_clicked_x is not None and self.last_clicked_y is not None:
                # Determine the losing team (the team that didn't win the point)
                losing_team_id = self.team_them_id if point_winner_id == self.team_us_id else self.team_us_id
                
                # Get the next sequence number for this rally
                if not self.db.conn:
                    self.db.connect()
                next_sequence = self.db.get_current_rally_sequence(self.current_rally_id)
                
                # Convert coordinates to integers if they are floats (from coordinate mapper)
                x_coord = int(round(self.last_clicked_x))
                y_coord = int(round(self.last_clicked_y))
                timecode_ms = self.last_clicked_timecode
                
                # Record floor contact (no player_id, but has coordinates)
                # Use contact_type "down" to indicate the ball hit the floor
                self.db.add_contact(
                    rally_id=self.current_rally_id,
                    sequence_number=next_sequence,
                    contact_type="down",  # Contact type "down" indicates ball hit the floor
                    team_id=losing_team_id,
                    player_id=None,  # No player - ball hit the floor
                    x=x_coord,
                    y=y_coord,
                    timecode=timecode_ms,
                    outcome="down"  # Floor contact outcome is always "down"
                )
                
                print(f"DEBUG: Floor contact recorded at ({x_coord}, {y_coord}, timecode={timecode_ms}ms) for losing team {losing_team_id}")
                
                # Clear the stored coordinates and timecode after recording
                self.last_clicked_x = None
                self.last_clicked_timecode = None
                self.last_clicked_y = None
                
                # Clear the coordinate display
                if hasattr(self.ui, 'tempXYcoord'):
                    self.ui.tempXYcoord.setText("")
            
            # Determine and assign outcomes to contacts in this rally
            self.assign_rally_outcomes(self.current_rally_id, point_winner_id)
            
            # End rally in database
            self.db.end_rally(self.current_rally_id, point_winner_id)
            
            # Update score
            if point_winner_id == self.team_us_id:
                self.score_us += 1
            else:
                self.score_them += 1
            
            # Check if team_them served (first contact in rally was a serve by team_them)
            team_them_served = False
            if self.current_rally_id:
                if not self.db.conn:
                    self.db.connect()
                cursor = self.db.conn.cursor()
                cursor.execute("""
                    SELECT contact_type, team_id 
                    FROM contacts 
                    WHERE rally_id = ? 
                    ORDER BY sequence_number ASC 
                    LIMIT 1
                """, (self.current_rally_id,))
                first_contact = cursor.fetchone()
                if first_contact:
                    first_contact_type, first_contact_team_id = first_contact
                    if first_contact_type == 'serve' and first_contact_team_id == self.team_them_id:
                        team_them_served = True
            
            # Auto-rotate team_us if team_them served and team_us won the point
            if team_them_served and point_winner_id == self.team_us_id:
                try:
                    self.lineup_manager.rotate(self.game_id, self.team_us_id)
                    print(f"DEBUG: Auto-rotated team_us after winning point (team_them had served)")
                    # Update MainWindow player buttons to reflect rotation
                    self.update_mainwindow_player_buttons()
                    # Show rotation popup
                    self.show_rotation_popup()
                except Exception as e:
                    print(f"DEBUG ERROR: Failed to rotate team_us: {e}")
            
            # Display debug message with team_us lineup after each point
            self.print_team_us_lineup()
            
            # Reset for next rally
            self.rally_in_progress = False
            self.current_rally_id = None
            self.current_rally_number += 1
            
            # Team that won the point serves next
            self.serving_team_id = point_winner_id
            # Track which team should serve next (the team that just received the point)
            self.expected_next_server_team_id = point_winner_id
            
            self.current_sequence = 0
            self.selected_player_number = None
            self.selected_team_id = None
            self.opponent_contact_count = 0  # Reset opponent contact sequence
            
            self.update_score_display()
            self.update_status()
            self.update_ui_state()
            
            QMessageBox.information(self, "Point Scored", 
                                  f"Point awarded! Score: {self.score_us} - {self.score_them}")
            
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Failed to end rally:\n{str(e)}")
    
    def on_point_awarded_from_mapper(self, point_winner_id: int):
        """Handle point awarded from coordinate mapper - refresh state to ensure only serve is available."""
        try:
            # Check if team_them served in the rally that was just completed
            # When awarding through mapper, a new rally is created and immediately ended
            # We need to check who served in that rally (or the previous one if this one has no contacts)
            team_them_served_previous = False
            if not self.db.conn:
                self.db.connect()
            cursor = self.db.conn.cursor()
            # Get the most recent completed rally (the one we just created via mapper)
            cursor.execute("""
                SELECT rally_id, serving_team_id, rally_number
                FROM rallies 
                WHERE game_id = ? AND point_winner_id = ?
                ORDER BY rally_number DESC
                LIMIT 1
            """, (self.game_id, point_winner_id))
            completed_rally = cursor.fetchone()
            if completed_rally:
                completed_rally_id, serving_team_id, rally_number = completed_rally
                # Check if there were any contacts in this rally to see who actually served
                cursor.execute("""
                    SELECT contact_type, team_id 
                    FROM contacts 
                    WHERE rally_id = ? AND contact_type = 'serve'
                    ORDER BY sequence_number ASC 
                    LIMIT 1
                """, (completed_rally_id,))
                serve_contact = cursor.fetchone()
                if serve_contact:
                    # There was a serve contact in this rally - use that
                    serve_contact_type, serve_team_id = serve_contact
                    if serve_team_id == self.team_them_id:
                        team_them_served_previous = True
                        print(f"DEBUG: Rally {rally_number} (rally_id={completed_rally_id}) had a serve by team_them")
                else:
                    # No serve contact in this rally (empty rally from mapper)
                    # Check the PREVIOUS rally to see who served there
                    if rally_number > 1:
                        cursor.execute("""
                            SELECT rally_id, serving_team_id
                            FROM rallies 
                            WHERE game_id = ? AND rally_number = ?
                        """, (self.game_id, rally_number - 1))
                        prev_rally = cursor.fetchone()
                        if prev_rally:
                            prev_rally_id, prev_serving_team_id = prev_rally[0], prev_rally[1]
                            # Also check if there was a serve contact in the previous rally
                            cursor.execute("""
                                SELECT contact_type, team_id 
                                FROM contacts 
                                WHERE rally_id = ? AND contact_type = 'serve'
                                ORDER BY sequence_number ASC 
                                LIMIT 1
                            """, (prev_rally_id,))
                            prev_serve_contact = cursor.fetchone()
                            if prev_serve_contact:
                                prev_serve_team_id = prev_serve_contact[1]
                                if prev_serve_team_id == self.team_them_id:
                                    team_them_served_previous = True
                                    print(f"DEBUG: Previous rally {rally_number - 1} (rally_id={prev_rally_id}) had a serve by team_them")
                            elif prev_serving_team_id == self.team_them_id:
                                # Fallback to serving_team_id if no serve contact found
                                team_them_served_previous = True
                                print(f"DEBUG: Previous rally {rally_number - 1} serving_team_id was team_them")
            
            # Auto-rotate team_us if team_them served in previous rally and team_us won the point
            if team_them_served_previous and point_winner_id == self.team_us_id:
                try:
                    self.lineup_manager.rotate(self.game_id, self.team_us_id)
                    print(f"DEBUG: Auto-rotated team_us after winning point from mapper (team_them had served in previous rally)")
                    # Update MainWindow player buttons to reflect rotation
                    self.update_mainwindow_player_buttons()
                    # Show rotation popup
                    self.show_rotation_popup()
                except Exception as e:
                    print(f"DEBUG ERROR: Failed to rotate team_us: {e}")
            
            # Reload score to get updated values
            self.load_score()
            
            # Reset rally state - no rally in progress after point is awarded
            self.rally_in_progress = False
            self.current_rally_id = None
            self.current_sequence = 0
            self.selected_player_number = None
            self.selected_team_id = None
            self.opponent_contact_count = 0
            
            # Set serving team to the team that won the point
            self.serving_team_id = point_winner_id
            self.expected_next_server_team_id = point_winner_id
            
            # Update MainWindow player buttons to reflect rotation (if it happened)
            self.update_mainwindow_player_buttons()
            
            # Update UI to reflect new state (this will enable only serve)
            self.update_score_display()
            self.update_status()
            self.update_ui_state()
            
            print(f"DEBUG: Point awarded from mapper to team {point_winner_id}. State refreshed - rally_in_progress=False, only serve available.")
        except Exception as e:
            print(f"ERROR: Failed to refresh state after point awarded from mapper: {e}")
    
    def check_and_remove_libero_from_front_row(self):
        """Check if libero is in position 4 (front row) after rotation and automatically remove them.
        
        Returns:
            bool: True if libero was removed, False otherwise
        """
        if not self.game_id or not self.team_us_id:
            return False
        
        # Get libero player ID
        libero_id = self.get_libero_player_id(self.team_us_id)
        if not libero_id:
            return False
        
        if not self.db.conn:
            self.db.connect()
        
        cursor = self.db.conn.cursor()
        
        # Check if libero is in position 4 (front row)
        cursor.execute("""
            SELECT position_number 
            FROM active_lineup 
            WHERE game_id = ? AND team_id = ? AND player_id = ? AND position_number = 4
        """, (self.game_id, self.team_us_id, libero_id))
        
        result = cursor.fetchone()
        if not result:
            # Libero is not in position 4
            return False
        
        # Libero is in position 4 - need to remove them
        position = 4
        
        # Find the original player that was replaced
        replaced_player_id = None
        
        # First check our tracking dict
        if position in self.libero_replacements:
            replaced_player_id = self.libero_replacements[position]
        else:
            # Position 4 comes from position 5 in rotation (ROTATION_MAP[5] = 4)
            # So first try to find libero_actions for position 5 (where libero came from)
            cursor.execute("""
                SELECT replaced_player_id 
                FROM libero_actions 
                WHERE game_id = ? AND team_id = ? AND replaced_position = ? AND action = 'enter'
                ORDER BY created_at DESC
                LIMIT 1
            """, (self.game_id, self.team_us_id, 5))
            result = cursor.fetchone()
            if result:
                replaced_player_id = result[0]
                print(f"DEBUG: Found libero_actions for position 5, using replaced_player_id={replaced_player_id}")
            else:
                # Fallback: Query libero_actions table for the most recent enter action at position 4
                cursor.execute("""
                    SELECT replaced_player_id 
                    FROM libero_actions 
                    WHERE game_id = ? AND team_id = ? AND replaced_position = ? AND action = 'enter'
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (self.game_id, self.team_us_id, position))
                result = cursor.fetchone()
                if result:
                    replaced_player_id = result[0]
                    print(f"DEBUG: Found libero_actions for position 4, using replaced_player_id={replaced_player_id}")
                else:
                    # Last fallback: find the most recent libero_actions record for this game overall
                    cursor.execute("""
                        SELECT replaced_player_id 
                        FROM libero_actions 
                        WHERE game_id = ? AND team_id = ? AND action = 'enter'
                        ORDER BY created_at DESC
                        LIMIT 1
                    """, (self.game_id, self.team_us_id))
                    result = cursor.fetchone()
                    if result:
                        replaced_player_id = result[0]
                        print(f"DEBUG: Found most recent libero_actions record, using replaced_player_id={replaced_player_id}")
        
        if not replaced_player_id:
            print(f"WARNING: Could not find original player replaced by libero at position {position}")
            QMessageBox.warning(
                self,
                "Libero Removal Error",
                f"Could not determine which player should be at position 4.\n\n"
                f"The libero is in position 4 (front row) but the system cannot find\n"
                f"which player should replace them in libero_actions table.\n\n"
                f"Please manually remove the libero using the Libero OUT button."
            )
            return False
        
        # Get player info for popup message
        cursor.execute("""
            SELECT COALESCE(p.jersey, p.player_number) as player_number, p.name
            FROM players p
            WHERE p.player_id = ?
        """, (replaced_player_id,))
        player_info = cursor.fetchone()
        player_number = player_info[0] if player_info else "Unknown"
        player_name = player_info[1] if player_info else ""
        
        # Perform libero exit
        try:
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
            
            # Update MainWindow player buttons
            self.update_mainwindow_player_buttons()
            
            # Show popup message
            player_display = f"#{player_number} {player_name}" if player_name else f"#{player_number}"
            QMessageBox.information(
                self, 
                "Libero Automatically Removed",
                f"The libero has been automatically removed from position 4 (front row).\n\n"
                f"Original player {player_display} has been restored to position 4."
            )
            
            print(f"DEBUG: Automatically removed libero from position 4, restored player #{player_number}")
            return True
            
        except Exception as e:
            print(f"ERROR: Failed to automatically remove libero from position 4: {e}")
            QMessageBox.warning(
                self,
                "Libero Removal Error",
                f"Failed to automatically remove libero from position 4:\n{str(e)}"
            )
            return False
    
    def show_rotation_popup(self):
        """Show a popup dialog displaying the 6 players and their positions after rotation."""
        if not self.team_us_id or not self.game_id:
            return
        
        try:
            if not self.db.conn:
                self.db.connect()
            cursor = self.db.conn.cursor()
            cursor.execute("""
                SELECT al.position_number, 
                       COALESCE(p.jersey, p.player_number) as player_number,
                       p.name,
                       al.role_code,
                       al.is_server
                FROM active_lineup al
                INNER JOIN players p ON al.player_id = p.player_id
                WHERE al.game_id = ? AND al.team_id = ?
                ORDER BY al.position_number
            """, (self.game_id, self.team_us_id))
            
            players = cursor.fetchall()
            
            if not players or len(players) != 6:
                print(f"DEBUG: Cannot show rotation popup - found {len(players) if players else 0} players (expected 6)")
                return
            
            # Create popup dialog
            dialog = QDialog(self)
            dialog.setWindowTitle("Team Rotation")
            dialog.setModal(True)
            dialog.setMinimumSize(400, 350)
            
            layout = QVBoxLayout(dialog)
            
            # Title
            title_label = QLabel("Team Rotation Complete")
            title_label.setFont(QFont('Arial', 14, QFont.Weight.Bold))
            title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(title_label)
            
            # Court diagram with positions
            # Volleyball court positions:
            #     4    3    2
            #     5    6    1
            # Where 1 is right back (server position), 2 is right front, etc.
            
            # Create a text display showing the lineup
            lineup_text = QTextEdit()
            lineup_text.setReadOnly(True)
            lineup_text.setFont(QFont('Courier', 10))
            lineup_text.setMaximumHeight(250)
            
            # Build the display text
            # Sort players by position number
            players_by_pos = {pos: (player_number, name, role_code, is_server) 
                             for pos, player_number, name, role_code, is_server in players}
            
            # Court layout visualization
            text_lines = []
            text_lines.append("Court Positions:")
            text_lines.append("")
            text_lines.append("  Front Row:")
            text_lines.append(f"    Position 4 (Left Front):  #{players_by_pos[4][0]} {players_by_pos[4][1] or 'Unknown'} ({players_by_pos[4][2] or 'N/A'})")
            text_lines.append(f"    Position 3 (Middle Front): #{players_by_pos[3][0]} {players_by_pos[3][1] or 'Unknown'} ({players_by_pos[3][2] or 'N/A'})")
            text_lines.append(f"    Position 2 (Right Front):  #{players_by_pos[2][0]} {players_by_pos[2][1] or 'Unknown'} ({players_by_pos[2][2] or 'N/A'})")
            text_lines.append("")
            text_lines.append("  Back Row:")
            text_lines.append(f"    Position 5 (Left Back):    #{players_by_pos[5][0]} {players_by_pos[5][1] or 'Unknown'} ({players_by_pos[5][2] or 'N/A'})")
            text_lines.append(f"    Position 6 (Middle Back):  #{players_by_pos[6][0]} {players_by_pos[6][1] or 'Unknown'} ({players_by_pos[6][2] or 'N/A'})")
            server_marker = " [SERVER]" if players_by_pos[1][3] else ""
            text_lines.append(f"    Position 1 (Right Back):   #{players_by_pos[1][0]} {players_by_pos[1][1] or 'Unknown'} ({players_by_pos[1][2] or 'N/A'}){server_marker}")
            
            lineup_text.setPlainText("\n".join(text_lines))
            layout.addWidget(lineup_text)
            
            # OK button
            button_layout = QHBoxLayout()
            button_layout.addStretch()
            ok_btn = QPushButton("OK")
            ok_btn.setFont(QFont('Arial', 10))
            ok_btn.clicked.connect(dialog.accept)
            ok_btn.setDefault(True)
            button_layout.addWidget(ok_btn)
            button_layout.addStretch()
            layout.addLayout(button_layout)
            
            # Show the dialog
            dialog.exec()
            
        except Exception as e:
            print(f"ERROR: Failed to show rotation popup: {e}")
    
    def print_team_us_lineup(self):
        """Print debug message listing the 6 players on team_us and their court positions, plus bench players."""
        if not self.team_us_id or not self.game_id:
            return
        
        try:
            if not self.db.conn:
                self.db.connect()
            cursor = self.db.conn.cursor()
            cursor.execute("""
                SELECT al.position_number, 
                       p.player_id,
                       COALESCE(p.jersey, p.player_number) as player_number,
                       p.name,
                       al.role_code
                FROM active_lineup al
                INNER JOIN players p ON al.player_id = p.player_id
                WHERE al.team_id = ?
                ORDER BY al.position_number
            """, (self.team_us_id,))
            
            players = cursor.fetchall()
            
            if players:
                print("\n" + "="*60)
                print("DEBUG: Team_US Lineup After Point:")
                print("="*60)
                for position_number, player_id, player_number, player_name, role_code in players:
                    name_display = player_name if player_name else "Unknown"
                    print(f"  Position {position_number}: Player #{player_number} (ID:{player_id}) - {name_display} ({role_code})")
                print("="*60)
                
                # Also print bench players
                bench_players = self.get_bench_players(self.team_us_id)
                if bench_players:
                    print("DEBUG: Team_US Bench Players:")
                    print("-"*60)
                    for player_id, player_number, player_name in bench_players:
                        name_display = player_name if player_name else "Unknown"
                        # Get role code for bench player
                        cursor.execute("""
                            SELECT role_code FROM players WHERE player_id = ?
                        """, (player_id,))
                        role_result = cursor.fetchone()
                        role_code = role_result[0] if role_result and role_result[0] else "N/A"
                        print(f"  Bench: Player #{player_number} (ID:{player_id}) - {name_display} ({role_code})")
                    print("-"*60)
                else:
                    print("DEBUG: No bench players available")
                print("="*60 + "\n")
            else:
                print("DEBUG: No active lineup found for team_us")
        except Exception as e:
            print(f"DEBUG ERROR: Failed to print team_us lineup: {e}")
    
    def get_bench_players(self, team_id: int):
        """Get bench players (players in game_players but not in active_lineup).
        
        Args:
            team_id: The team ID to get bench players for
            
        Returns:
            List of (player_id, player_number, player_name) tuples
        """
        if not self.game_id:
            return []
        
        if not self.db.conn:
            self.db.connect()
        
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
        
        if not self.db.conn:
            self.db.connect()
        
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
                # Perform substitution using LineupManager
                self.lineup_manager.substitution(
                    team_id=self.team_us_id,
                    out_player_id=out_player_id,
                    in_player_id=in_player_id,
                    game_id=self.game_id
                )
                
                # Update the MainWindow player buttons to reflect the new lineup
                self.update_mainwindow_player_buttons()
                
                # Update UI state to ensure action buttons are properly enabled/disabled
                self.update_ui_state()
                
                # Print updated lineup
                self.print_team_us_lineup()
                
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
    
    def setup_libero_buttons(self):
        """Create and position Libero IN and Libero OUT buttons next to substitution button."""
        if not hasattr(self.ui, 'pushButton_substitution'):
            return
        
        # Get substitution button position and size
        sub_btn = self.ui.pushButton_substitution
        sub_x = sub_btn.x()
        sub_y = sub_btn.y()
        sub_width = sub_btn.width()
        sub_height = sub_btn.height()
        
        # Create Libero IN button (to the right of substitution button)
        libero_in_btn = QPushButton("Libero IN", self.ui.centralwidget)
        libero_in_btn.setGeometry(sub_x + sub_width + 10, sub_y, 150, sub_height)
        libero_in_btn.clicked.connect(self.show_libero_in_dialog)
        self.libero_in_button = libero_in_btn
        
        # Create Libero OUT button (to the right of Libero IN button)
        libero_out_btn = QPushButton("Libero OUT", self.ui.centralwidget)
        libero_out_btn.setGeometry(sub_x + sub_width * 2 + 20, sub_y, 150, sub_height)
        libero_out_btn.clicked.connect(self.show_libero_out_dialog)
        self.libero_out_button = libero_out_btn
    
    def get_libero_player_id(self, team_id: int) -> Optional[int]:
        """Get the libero player ID for the team."""
        if not self.game_id:
            return None
        
        if not self.db.conn:
            self.db.connect()
        
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT player_id 
            FROM players 
            WHERE team_id = ? AND role_code = 'Lib'
            LIMIT 1
        """, (team_id,))
        
        result = cursor.fetchone()
        return result[0] if result else None
    
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
        if not self.db.conn:
            self.db.connect()
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
                
                # Update MainWindow player buttons to reflect the new lineup
                self.update_mainwindow_player_buttons()
                
                # Update UI state to ensure action buttons are properly enabled/disabled
                self.update_ui_state()
                
                # Print updated lineup
                self.print_team_us_lineup()
                
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
        if not self.db.conn:
            self.db.connect()
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
            """Perform the libero exit action."""
            item = positions_list.currentItem()
            if not item:
                return
            
            selected_position = item.data(Qt.ItemDataRole.UserRole)
            self.perform_libero_exit(libero_id, selected_position, replaced_player_id)
            dialog.accept()
        
        exit_btn.clicked.connect(perform_libero_exit_dialog)
        button_layout.addWidget(exit_btn)
        
        layout.addLayout(button_layout)
        
        dialog.exec()
    
    def perform_libero_exit(self, libero_id: int, position: int, replaced_player_id: int):
        """Perform the libero exit action."""
        try:
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
            
            # Update MainWindow player buttons to reflect the new lineup
            self.update_mainwindow_player_buttons()
            
            # Update UI state to ensure action buttons are properly enabled/disabled
            self.update_ui_state()
            
            # Print updated lineup
            self.print_team_us_lineup()
            
            QMessageBox.information(self, "Libero Exited", 
                                  f"Libero has exited position {position}. Original player restored.")
        except Exception as e:
            QMessageBox.critical(self, "Libero Error", 
                               f"Failed to exit libero:\n{str(e)}")
    
    def update_score_display(self):
        """Update the score display in status bar."""
        # Check if score_label exists (may not be initialized yet)
        if not hasattr(self, 'score_label') or self.score_label is None:
            return
        
        if not self.game_id:
            self.score_label.setText("")
            return
        
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
        
        self.score_label.setText(f"<b>Score: {team_us_name} {self.score_us} - {self.score_them} {team_them_name}</b>")
        
        # Also update LCD displays if they exist
        if hasattr(self.ui, 'scoreUs'):
            self.ui.scoreUs.display(self.score_us)
        if hasattr(self.ui, 'scoreThem'):
            self.ui.scoreThem.display(self.score_them)
    
    def update_status(self):
        """Update the status message."""
        # Check if status_label exists (may not be initialized yet)
        if not hasattr(self, 'status_label') or self.status_label is None:
            return
        
        if self.rally_in_progress:
            serving_team = "Us" if self.serving_team_id == self.team_us_id else "Them"
            self.status_label.setText(f"Rally #{self.current_rally_number} in progress (served by {serving_team}) | Select player, then contact type")
        else:
            next_serving = "Us" if self.serving_team_id == self.team_us_id else "Them"
            self.status_label.setText(f"Ready for Rally #{self.current_rally_number} | {next_serving} will serve | Start with SERVE")
    
    def update_mainwindow_player_buttons(self):
        """Update MainWindow player buttons and labels based on active lineup for team_us.
        
        This method:
        1. Updates roster labels (label_TeamUsRosterP1-P9) with jersey numbers in ascending order
        2. Connects buttons on each row to the correct player_id
        3. Enables/disables player-action buttons based on whether the player is in active lineup
        """
        if not self.game_id or not self.team_us_id:
            return
        
        # Get active players for team_us directly from active_lineup
        # This ensures we get the most up-to-date lineup after substitutions
        if not self.db.conn:
            self.db.connect()
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT al.player_id, 
                   COALESCE(p.jersey, p.player_number) as player_number,
                   p.name
            FROM active_lineup al
            INNER JOIN players p ON al.player_id = p.player_id
            WHERE al.game_id = ? AND al.team_id = ?
            ORDER BY al.position_number
        """, (self.game_id, self.team_us_id))
        active_players = cursor.fetchall()
        
        if not active_players:
            # Fallback to get_team_players if active_lineup is empty
            active_players = self.get_team_players(self.team_us_id)
            if not active_players:
                return
        
        # Get jersey numbers for all players in one query
        if not self.db.conn:
            self.db.connect()
        cursor = self.db.conn.cursor()
        player_ids = [p[0] for p in active_players]
        placeholders = ','.join('?' * len(player_ids))
        cursor.execute(f"""
            SELECT player_id, COALESCE(jersey, player_number) as jersey
            FROM players
            WHERE player_id IN ({placeholders})
        """, player_ids)
        jersey_map = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Sort players by jersey number (ascending numeric order)
        def get_jersey_for_sort(player_data):
            player_id, player_number, player_name = player_data
            jersey = jersey_map.get(player_id, player_number)
            try:
                return int(jersey) if jersey else 999
            except (ValueError, TypeError):
                return 999
        
        sorted_players = sorted(active_players, key=get_jersey_for_sort)
        
        # Create mapping of player_number to player_id for button connections
        player_number_to_id = {}
        for player_id, player_number, player_name in sorted_players:
            player_number_to_id[str(player_number)] = player_id
        
        # Update roster labels (label_TeamUsRosterP1 through P9)
        # Show up to 9 players, sorted by jersey number
        label_names = [f'label_TeamUsRosterP{i}' for i in range(1, 10)]
        for i, label_name in enumerate(label_names):
            if hasattr(self.ui, label_name):
                label = getattr(self.ui, label_name)
                if i < len(sorted_players):
                    player_id, player_number, player_name = sorted_players[i]
                    # Get jersey number for display (already fetched above)
                    jersey = jersey_map.get(player_id, player_number)
                    label.setText(str(jersey))
                    label.setProperty('player_id', player_id)
                    label.setProperty('player_number', str(player_number))
                    label.show()
                else:
                    # Hide label if no player for this position
                    label.setText("")
                    label.hide()
        
        # Update player-action buttons (pattern: {player_number}_{action})
        # Reconnect buttons to correct player_id based on sorted order
        action_mapping = {
            'receive': 'receive',
            'pass': 'pass',
            'set': 'set',
            'attack': 'attack',
            'freeball': 'freeball',
            'block': 'block',
            'serve': 'serve'
        }
        
        # Map of label position to player data
        position_to_player = {}
        for i, (player_id, player_number, player_name) in enumerate(sorted_players[:9], 1):
            jersey = jersey_map.get(player_id, player_number)
            position_to_player[i] = {
                'player_id': player_id,
                'player_number': str(player_number),
                'jersey': jersey
            }
        
        # Create mapping of jersey/player_number to player data for button connections
        jersey_to_player = {}
        for player_id, player_number, player_name in sorted_players:
            jersey = jersey_map.get(player_id, player_number)
            jersey_str = str(jersey)
            player_number_str = str(player_number)
            # Map both jersey and player_number to the same player
            jersey_to_player[jersey_str] = {
                'player_id': player_id,
                'player_number': player_number_str,
                'jersey': jersey
            }
            if jersey_str != player_number_str:
                jersey_to_player[player_number_str] = jersey_to_player[jersey_str]
        
        # Get all widgets and update player-action buttons
        # Buttons follow pattern: {jersey}_{action} (e.g., "1_pass", "3_set", "8_attack")
        for widget_name in dir(self.ui):
            if not widget_name.startswith('_'):
                widget = getattr(self.ui, widget_name, None)
                if widget and hasattr(widget, 'setEnabled') and hasattr(widget, 'clicked'):
                    # Check if it matches the pattern {jersey}_{action}
                    if '_' in widget_name:
                        parts = widget_name.split('_', 1)
                        if len(parts) == 2:
                            jersey_part = parts[0]  # e.g., "1", "3", "8"
                            action_part = parts[1]  # e.g., "pass", "set", "attack"
                            
                            # Check if action_part is a valid action
                            if action_part in action_mapping:
                                action = action_mapping[action_part]
                                
                                # Check if we have a player with this jersey/number
                                if jersey_part in jersey_to_player:
                                    player_data = jersey_to_player[jersey_part]
                                    player_number_str = player_data['player_number']
                                    
                                    # Disconnect existing connections
                                    # Check if widget exists and has the clicked signal before disconnecting
                                    if widget is not None and hasattr(widget, 'clicked'):
                                        try:
                                            # Try to disconnect all connections
                                            # If no connections exist, this will emit a RuntimeWarning
                                            # We suppress it by catching the exception or using a context manager
                                            import warnings
                                            with warnings.catch_warnings():
                                                warnings.simplefilter("ignore", RuntimeWarning)
                                                widget.clicked.disconnect()
                                        except (TypeError, RuntimeError):
                                            # No connections to disconnect or signal not connected
                                            pass
                                    
                                    # Reconnect to correct player
                                    widget.clicked.connect(
                                        lambda checked=False, pnum=player_number_str, act=action: 
                                        self.handle_player_action(pnum, act)
                                    )
                                    
                                    # Enable button
                                    widget.setEnabled(True)
                                    widget.setStyleSheet("")  # Clear any previous styling
                                else:
                                    # No player with this jersey - disable button
                                    widget.setEnabled(False)
                                    widget.setStyleSheet("background-color: #E0E0E0; color: #808080;")
    
    def update_ui_state(self):
        """Update UI button states based on current game state."""
        # Enable/disable contact buttons based on rally state and volleyball rules
        self.update_contact_button_states()
    
    def update_contact_button_states(self):
        """Update contact button enabled/disabled states based on volleyball rules."""
        # If no game selected, disable all contact buttons
        if not self.game_id:
            allowed_actions = []
        # Determine what contact types should be enabled based on current rally state
        elif not self.rally_in_progress:
            # Rally not started - only serve is allowed
            allowed_actions = ['serve']
        else:
            # Get the last contact type and team in the current rally
            if not self.db.conn:
                self.db.connect()
            
            cursor = self.db.conn.cursor()
            cursor.execute("""
                SELECT contact_type, team_id
                FROM contacts 
                WHERE rally_id = ? AND contact_type != 'down'
                ORDER BY sequence_number DESC 
                LIMIT 1
            """, (self.current_rally_id,))
            
            result = cursor.fetchone()
            
            if result:
                last_contact_type, last_contact_team_id = result[0], result[1]
                
                # Get contact counts for both teams
                team_us_count = self.get_team_contact_count(self.team_us_id)
                team_them_count = self.get_team_contact_count(self.team_them_id)
                
                # Determine which team is making the next contact
                # If last contact was by team_us, next is team_them, and vice versa
                next_team_id = self.team_them_id if last_contact_team_id == self.team_us_id else self.team_us_id
                next_team_count = team_them_count if next_team_id == self.team_them_id else team_us_count
                next_contact_number = next_team_count + 1
                
                # Get opponent's contact count (the team that just contacted)
                opponent_contact_count = team_us_count if last_contact_team_id == self.team_us_id else team_them_count
                
                # Apply volleyball rules based on last contact type and contact sequence
                if last_contact_type == 'serve':
                    # After serve, only receive is allowed
                    allowed_actions = ['receive']
                elif last_contact_type == 'receive':
                    # After receive, pass, set, attack, freeball allowed (not receive or serve)
                    # Also allow block if opponent has 1st or 2nd contact
                    allowed_actions = ['pass', 'set', 'attack', 'freeball']
                    if opponent_contact_count == 1 or opponent_contact_count == 2:
                        allowed_actions.append('block')
                elif last_contact_type in ['pass', 'set']:
                    # After pass/set, set, attack, freeball allowed
                    # Also allow block if opponent has 1st or 2nd contact
                    allowed_actions = ['set', 'attack', 'freeball']
                    if opponent_contact_count == 1 or opponent_contact_count == 2:
                        allowed_actions.append('block')
                elif last_contact_type in ['attack', 'block', 'freeball']:
                    # After attack/block/freeball, check contact number
                    if next_contact_number == 1:
                        allowed_actions = ['pass', 'attack', 'block']
                    elif next_contact_number == 2:
                        allowed_actions = ['set', 'attack', 'freeball']
                        # Also allow block if opponent has 1st or 2nd contact
                        if opponent_contact_count == 1 or opponent_contact_count == 2:
                            allowed_actions.append('block')
                    elif next_contact_number == 3:
                        allowed_actions = ['attack', 'freeball']
                    # No 4th+ contact allowed
                else:
                    # Default: allow all except serve
                    allowed_actions = ['receive', 'pass', 'set', 'attack', 'block', 'freeball']
            else:
                # No contacts yet in rally (shouldn't happen if rally_in_progress is True)
                allowed_actions = ['serve']
        
        # Define colors for each action type when enabled
        action_colors = {
            'receive': '#FFB3B3',    # light red
            'pass': '#DDA0DD',       # light purple (plum)
            'set': '#ADD8E6',        # light blue
            'attack': '#E0FFFF',     # light cyan
            'freeball': '#90EE90',   # light green
            'block': '#BFFF00',      # lime
            'serve': '#FFD580'       # light orange
        }
        
        # Update button states - iterate through all widgets
        for widget_name in dir(self.ui):
            if not widget_name.startswith('_'):
                widget = getattr(self.ui, widget_name, None)
                if widget and hasattr(widget, 'setEnabled'):
                    # Check if it matches the pattern {player}_{action}
                    if '_' in widget_name:
                        parts = widget_name.split('_', 1)
                        if len(parts) == 2:
                            player_part = parts[0]
                            action_part = parts[1]
                            
                            # Check if action_part is a valid action
                            valid_actions = ['receive', 'pass', 'set', 'attack', 'block', 'freeball', 'serve']
                            if action_part in valid_actions:
                                # Enable or disable based on allowed_actions
                                should_enable = action_part in allowed_actions
                                widget.setEnabled(should_enable)
                                
                                # Apply color styling based on enabled state
                                if should_enable:
                                    # Get the color for this action type
                                    color = action_colors.get(action_part, '#FFFFFF')
                                    # Enabled: colored background with 2px dark gray border
                                    widget.setStyleSheet(f"background-color: {color}; border: 2px solid #505050;")
                                else:
                                    # Disabled: very light gray background with no border
                                    widget.setStyleSheet("background-color: #F5F5F5; border: none;")
    
    def closeEvent(self, event):
        """Clean up resources when window is closed."""
        if self.voice_recognizer:
            self.voice_recognizer.cleanup()
        event.accept()
    
    def reset_the_game(self):
        """Reset the current game by deleting all rallies and contacts."""
        if not self.game_id:
            QMessageBox.warning(self, "No Game Selected", "Please select a game first!")
            return
        
        # Confirm with user
        reply = QMessageBox.question(
            self, "Confirm Reset",
            "Are you sure you want to reset this game?\n\n"
            "This will delete ALL rallies and contacts for this game.\n"
            "This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                # Delete all rallies and contacts for this game
                contacts_deleted, rallies_deleted = self.db.delete_game_rallies_and_contacts(self.game_id)
                
                # Restore initial lineup and rotation state for team_us
                success, team_us_serving = self.lineup_manager.restore_initial_lineup(self.game_id, self.team_us_id)
                if success:
                    # Set serving team based on initial setup
                    if team_us_serving:
                        self.serving_team_id = self.team_us_id
                    else:
                        self.serving_team_id = self.team_them_id
                else:
                    # Fallback: if no initial setup found, default to team_us serving
                    self.serving_team_id = self.team_us_id
                    print("WARNING: Could not find initial setup event. Using default lineup.")
                
                # Reset tracking state
                self.current_rally_id = None
                self.current_rally_number = 0
                self.current_sequence = 0
                self.rally_in_progress = False
                self.score_us = 0
                self.score_them = 0
                self.selected_player_number = None
                self.selected_team_id = None
                self.opponent_contact_count = 0  # Reset opponent contact sequence
                
                # Update MainWindow player buttons to reflect restored lineup
                self.update_mainwindow_player_buttons()
                
                # Print restored lineup
                self.print_team_us_lineup()
                
                # Update UI
                self.update_score_display()
                self.update_status()
                self.update_ui_state()
                
                QMessageBox.information(
                    self, "Game Reset",
                    f"Game has been reset successfully!\n\n"
                    f"Deleted: {rallies_deleted} rallies and {contacts_deleted} contacts.\n"
                    f"Restored starting lineup and rotation state."
                )
                
            except Exception as e:
                QMessageBox.critical(self, "Reset Error", f"Failed to reset game:\n{str(e)}")


if __name__ == "__main__":
    # Test the data entry window standalone
    import sys
    from PySide6.QtWidgets import QApplication
    from PySide6.QtUiTools import QUiLoader
    from pathlib import Path
    
    app = QApplication(sys.argv)
    
    # Initialize database
    db = VideoStatsDB()
    db.initialize_database()
    db.connect()
    
    # Get or create teams and game
    cursor = db.conn.cursor()
    cursor.execute("SELECT team_id, name FROM teams LIMIT 2")
    teams = cursor.fetchall()
    
    if len(teams) < 2:
        print("Error: Need at least 2 teams. Please run main.py first to configure teams.")
        db.close()
        sys.exit(1)
    
    team_us_id = teams[0][0]
    team_them_id = teams[1][0]
    
    # Get or create game
    cursor.execute("SELECT game_id FROM games ORDER BY game_id DESC LIMIT 1")
    game_result = cursor.fetchone()
    if game_result:
        game_id = game_result[0]
    else:
        game_id = db.start_game(team_us_id, team_them_id)
    
    db.close()
    
    # Load UI
    ui_file = Path(__file__).parent / "inputTouchesVoice.ui"
    loader = QUiLoader()
    ui_widget = loader.load(str(ui_file))
    
    if ui_widget:
        window = DataEntryWindow(
            ui_widget=ui_widget,
            db=db,
            team_us_id=team_us_id,
            team_them_id=team_them_id,
            game_id=game_id
        )
        window.show()
        sys.exit(app.exec())
    else:
        print("Failed to load UI file")
        sys.exit(1)
