"""
Data entry screen for tracking ball contacts during a volleyball game.
"""

from PySide6.QtWidgets import QMainWindow, QMessageBox, QLabel, QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton, QListWidgetItem, QScrollArea, QWidget
from PySide6.QtCore import Qt, QEvent, QPoint, Signal, QObject, QThread
from PySide6.QtGui import QMouseEvent, QFont
from database import VideoStatsDB
from datetime import datetime
from typing import Optional
from coordinate_mapper import CoordinateMapper
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
    
    def __init__(self, ui_widget, db: VideoStatsDB, team_us_id: Optional[int] = None, team_them_id: Optional[int] = None, game_id: Optional[int] = None):
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
        if self.game_id:
            self.load_score()
        
        # Always update UI state to set button states correctly
        self.update_ui_state()
    
    def setup_coordinate_mapper(self):
        """Set up and launch the coordinate mapper window."""
        self.coordinate_mapper = CoordinateMapper(parent=self, db=self.db, game_id=self.game_id)
        # Connect signal to receive mapped coordinates
        self.coordinate_mapper.coordinate_mapped.connect(self.on_coordinate_mapped)
        # Connect double-click signal for DOWN contacts
        self.coordinate_mapper.double_click_mapped.connect(self.on_double_click_mapped)
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
        
        # Look up the player in the game_players table
        if not self.db.conn:
            self.db.connect()
        
        # Determine team - for now assume "our team" (team_us_id) for voice input
        # The Y coordinate could be used to determine team, but voice is simpler with our team
        team_id = self.team_us_id
        print(f"DEBUG VOICE_HANDLER: Looking up player #{player_number} in team_id={team_id}, game_id={self.game_id}")
        
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
                # Update status to indicate coordinate was captured
                if self.use_coordinate_mapper:
                    self.status_label.setText(f"Coordinate captured: ({logical_x:.2f}, {logical_y:.2f}) @ {timecode_str}. Now click the contact button again to record.")
                else:
                    self.status_label.setText(f"Coordinate captured: ({logical_x:.2f}, {logical_y:.2f}) @ {timecode_str}. Ready to record contact.")
    
    def on_double_click_mapped(self, logical_x, logical_y, pixel_x, pixel_y, timecode_ms):
        """Handle double-click from coordinate_mapper - records a DOWN contact."""
        if not self.game_id:
            self.status_label.setText("No game selected - cannot record DOWN contact")
            return
        
        if not self.rally_in_progress:
            self.status_label.setText("No rally in progress - cannot record DOWN contact")
            return
        
        # Store the coordinates
        self.last_clicked_x = logical_x
        self.last_clicked_y = logical_y
        self.last_clicked_timecode = timecode_ms
        
        print(f"DEBUG: on_double_click_mapped - DOWN contact at x={logical_x}, y={logical_y}, timecode={timecode_ms}ms")
        
        # Determine which team based on Y coordinate (for the losing team)
        # Y > 300 is opponent side, Y <= 300 is our side
        if logical_y > 300:
            # Ball went down on opponent side - we scored
            losing_team_id = self.team_them_id
        else:
            # Ball went down on our side - opponent scored
            losing_team_id = self.team_us_id
        
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
        
        # Record the DOWN contact
        self.record_contact("down")
    
    def setup_ui(self):
        """Set up the UI with score display and status."""
        # Populate games dropdown
        self.populate_games_dropdown()
        
        # Create score label in status bar
        self.score_label = QLabel()
        self.ui.statusbar.addPermanentWidget(self.score_label)
        if self.game_id:
            self.update_score_display()
        
        # Create status label
        self.status_label = QLabel()
        self.ui.statusbar.addWidget(self.status_label)
        if self.game_id:
            self.update_status()
        else:
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
        
        # Always set to blank selection (index 0 is the placeholder)
        # Don't auto-select even if game_id is provided - user must select manually
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
            return
        
        # Get game data from selected item
        item_data = self.ui.comboBox.itemData(index, Qt.UserRole)
        if not item_data:
            return
        
        # Update game and team IDs
        self.game_id = item_data['game_id']
        self.team_us_id = item_data['team_us_id']
        self.team_them_id = item_data['team_them_id']
        
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
            # Database returns: corner_tl, corner_tr, corner_bl, corner_br, centerline_top, centerline_bottom
            # Coordinate mapper expects: [BL, BR, TR, TL, ML, MR]
            corner_points = [
                list(court_boundaries['corner_bl']),      # 0: BL (0,0)
                list(court_boundaries['corner_br']),      # 1: BR (300,0)
                list(court_boundaries['corner_tr']),      # 2: TR (300,600)
                list(court_boundaries['corner_tl']),      # 3: TL (0,600)
                list(court_boundaries['centerline_bottom']),  # 4: ML (0,300) - left end of centerline
                list(court_boundaries['centerline_top'])      # 5: MR (300,300) - right end of centerline
            ]
            
            if self.coordinate_mapper:
                self.coordinate_mapper.set_corner_points(corner_points)
                print(f"DEBUG: Court boundaries loaded successfully")
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
        
        # Store selected player
        self.selected_player_number = None
        self.selected_team_id = None
    
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
    
    def show_player_selection_dialog(self, team_id: int, x_coord: float, y_coord: float, pixel_x: float = None, pixel_y: float = None):
        """Show a dialog to select a player from the specified team.
        
        Args:
            team_id: The team ID to get players from
            x_coord: X coordinate of the click (logical)
            y_coord: Y coordinate of the click (logical)
            pixel_x: Pixel X coordinate for positioning dialog (optional)
            pixel_y: Pixel Y coordinate for positioning dialog (optional)
        """
        if not self.game_id:
            return
        
        # Get players for this team in this game
        if not self.db.conn:
            self.db.connect()
        
        cursor = self.db.conn.cursor()
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
        
        if not players:
            QMessageBox.warning(self, "No Players", "No players found for this team in this game.")
            return
        
        # Check if the prior contact was a serve by the opponent team
        prior_contact_was_opponent_serve = False
        if self.current_rally_id:
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
        
        # Get the team's contact count to determine which actions are allowed
        contact_count = self.get_team_contact_count(team_id)
        contact_number = contact_count + 1  # This will be the contact number for the next contact
        
        # Determine allowed actions based on whether it's after opponent serve or later in rally
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
                # 4th+ contact: repeat pattern - pass/attack/block, then set/attack/free, then attack/free
                # For 4th+ contacts, cycle back to the pattern
                cycle_contact = ((contact_number - 1) % 3) + 1
                if cycle_contact == 1:
                    allowed_actions = ['pass', 'attack', 'block']
                elif cycle_contact == 2:
                    allowed_actions = ['set', 'attack', 'freeball']
                else:  # cycle_contact == 3
                    allowed_actions = ['attack', 'freeball']
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
                # 4th+ contact: repeat pattern - pass/attack/block, then set/attack/free, then attack/free
                cycle_contact = ((contact_number - 1) % 3) + 1
                if cycle_contact == 1:
                    allowed_actions = ['pass', 'attack', 'block']
                elif cycle_contact == 2:
                    allowed_actions = ['set', 'attack', 'freeball']
                else:  # cycle_contact == 3
                    allowed_actions = ['attack', 'freeball']
        
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
            
            for action_label, action_type in actions:
                # Only show button if action is allowed for this contact number
                if action_type not in allowed_actions:
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
        if dialog.exec() == QDialog.Accepted and selected_action[0]:
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
            # Get player_id from database for this game
            if not self.db.conn:
                self.db.connect()
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
        
        # Set the selected player/team
        if player_number.startswith('o'):
            # Opponent player - use the full player number as stored in database (e.g., "o1")
            opponent_player_number = player_number  # Keep the full "o1", "o2", etc.
            self.selected_team_id = self.team_them_id
            self.selected_player_number = opponent_player_number
            # Get player_id from database for opponent player
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
            # Our team player
            self.selected_team_id = self.team_us_id
            self.selected_player_number = player_number_str
            # Get player_id from database
            if not self.db.conn:
                self.db.connect()
            player = self.db.get_player_by_number_for_game(self.game_id, self.team_us_id, player_number_str)
            if player:
                self.selected_player_id = player['player_id']
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
            
            # Set outcome for "down", "net", and "fault" contacts
            outcome = "down" if contact_type in ("down", "net", "fault") else "continue"
            
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
            
        except Exception as e:
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
        if team_id == losing_team_id:
            outcome = 'error'
            print(f"DEBUG: Contact {contact_id} ({contact_type}) assigned outcome 'error' (losing team contact)")
        
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
            
            # Reset for next rally
            self.rally_in_progress = False
            self.current_rally_id = None
            self.current_rally_number += 1
            
            # Team that won the point serves next
            self.serving_team_id = point_winner_id
            
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
    
    def update_score_display(self):
        """Update the score display in status bar."""
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
        if self.rally_in_progress:
            serving_team = "Us" if self.serving_team_id == self.team_us_id else "Them"
            self.status_label.setText(f"Rally #{self.current_rally_number} in progress (served by {serving_team}) | Select player, then contact type")
        else:
            next_serving = "Us" if self.serving_team_id == self.team_us_id else "Them"
            self.status_label.setText(f"Ready for Rally #{self.current_rally_number} | {next_serving} will serve | Start with SERVE")
    
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
            # Get the last contact type in the current rally
            if not self.db.conn:
                self.db.connect()
            
            cursor = self.db.conn.cursor()
            cursor.execute("""
                SELECT contact_type 
                FROM contacts 
                WHERE rally_id = ? 
                ORDER BY sequence_number DESC 
                LIMIT 1
            """, (self.current_rally_id,))
            
            result = cursor.fetchone()
            
            if result:
                last_contact_type = result[0]
                
                # Apply volleyball rules based on last contact type
                if last_contact_type == 'serve':
                    # After serve, only receive is allowed
                    allowed_actions = ['receive']
                elif last_contact_type == 'receive':
                    # After receive, pass, set, attack, block, freeball allowed (not receive or serve)
                    allowed_actions = ['pass', 'set', 'attack', 'block', 'freeball']
                elif last_contact_type in ['pass', 'set']:
                    # After pass/set, set, attack, block, freeball allowed
                    allowed_actions = ['set', 'attack', 'block', 'freeball']
                elif last_contact_type in ['attack', 'block', 'freeball']:
                    # After attack/block/freeball, all actions except serve
                    allowed_actions = ['receive', 'pass', 'set', 'attack', 'block', 'freeball']
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
                
                # Reset tracking state
                self.current_rally_id = None
                self.current_rally_number = 0
                self.current_sequence = 0
                self.serving_team_id = self.team_us_id  # Start with our team serving
                self.rally_in_progress = False
                self.score_us = 0
                self.score_them = 0
                self.selected_player_number = None
                self.selected_team_id = None
                self.opponent_contact_count = 0  # Reset opponent contact sequence
                
                # Update UI
                self.update_score_display()
                self.update_status()
                self.update_ui_state()
                
                QMessageBox.information(
                    self, "Game Reset",
                    f"Game has been reset successfully!\n\n"
                    f"Deleted: {rallies_deleted} rallies and {contacts_deleted} contacts."
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

