"""
Data entry screen for tracking ball contacts during a volleyball game.
"""

from PySide6.QtWidgets import QMainWindow, QMessageBox, QLabel
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QMouseEvent
from database import VideoStatsDB
from datetime import datetime
from typing import Optional
from coordinate_mapper import CoordinateMapper


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
        
        # Setup UI first (populate games dropdown)
        self.setup_ui()
        self.connect_signals()
        self.setup_court_click_tracking()
        self.setup_coordinate_mapper()
        
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
            
            # Update status to indicate coordinate was captured
            if self.use_coordinate_mapper:
                self.status_label.setText(f"Coordinate captured: ({logical_x:.2f}, {logical_y:.2f}) @ {timecode_str}. Now click the contact button again to record.")
            else:
                self.status_label.setText(f"Coordinate captured: ({logical_x:.2f}, {logical_y:.2f}) @ {timecode_str}. Ready to record contact.")
    
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
        print(f"DEBUG: record_contact called for {contact_type}")
        if not self.game_id:
            QMessageBox.warning(self, "No Game Selected", "Please select a game first!")
            return
        
        print(f"DEBUG: record_contact - last_clicked_x={self.last_clicked_x}, last_clicked_y={self.last_clicked_y}")
        
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
            
            self.current_rally_id = self.db.start_rally(
                game_id=self.game_id,
                rally_number=self.current_rally_number,
                serving_team_id=serving_team_id
            )
            self.rally_in_progress = True
            self.current_sequence = 1
            
            # For serve, use selected team and player
            team_id = self.selected_team_id
            player_id = getattr(self, 'selected_player_id', None)
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
            
            self.db.add_contact(
                rally_id=self.current_rally_id,
                sequence_number=self.current_sequence,
                contact_type=contact_type,
                team_id=team_id,
                player_id=player_id,
                x=x_coord,
                y=y_coord,
                timecode=timecode_ms
            )
            
            print(f"DEBUG: Contact recorded successfully with x={x_coord}, y={y_coord}, timecode={timecode_ms}ms")
            
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
            
            # Reset coordinate mapper flag if it was used
            if self.use_coordinate_mapper:
                self.use_coordinate_mapper = False
                self.status_label.setText("Contact recorded. Select player for next contact. Click in Coordinate Mapper for location.")
            else:
                self.status_label.setText("Contact recorded. Select player for next contact.")
            
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
            
            # Alternate serving team
            self.serving_team_id = self.team_them_id if self.serving_team_id == self.team_us_id else self.team_us_id
            
            self.current_sequence = 0
            self.selected_player_number = None
            self.selected_team_id = None
            
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
    ui_file = Path(__file__).parent / "inputTouches.ui"
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

