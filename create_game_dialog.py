"""
Enhanced dialog for creating a new game with lineup configuration.
Allows selecting Team_US, setting starting lineup, and launching data entry.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QMessageBox, QDateEdit, QGridLayout, QGroupBox, QLineEdit, QRadioButton,
    QButtonGroup, QWidget, QFrame
)
from PySide6.QtCore import Qt, QDate, Signal
from PySide6.QtGui import QFont
from database import VideoStatsDB
from lineup_manager import LineupManager
from lineup_models import FRONT_ROW_POSITIONS, BACK_ROW_POSITIONS
from datetime import datetime
from pathlib import Path
from PySide6.QtUiTools import QUiLoader
from data_entry import DataEntryWindow


class CreateGameDialog(QDialog):
    """Dialog for creating a new game with lineup configuration."""
    
    def __init__(self, db: VideoStatsDB, parent=None):
        super().__init__(parent)
        self.db = db
        self.game_id = None
        self.team_us_id = None
        self.team_them_id = None
        self.team_us_name = ""
        self.team_them_name = ""
        self.opponent_alias = ""
        
        # Position mapping: (position_number, display_name, abbrev)
        # Layout: Top row: LF(4), MF(3), RF(2) | Bottom row: LB(5), MB(6), RB(1)
        self.position_info = {
            4: ("Left Front", "LF"),
            3: ("Middle Front", "MF"),
            2: ("Right Front", "RF"),
            5: ("Left Back", "LB"),
            6: ("Middle Back", "MB"),
            1: ("Right Back", "RB")
        }
        
        self.setWindowTitle("Create New Game")
        self.setGeometry(100, 100, 900, 800)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Game date
        date_layout = QHBoxLayout()
        date_layout.addWidget(QLabel("Game Date:"))
        self.date_edit = QDateEdit()
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        date_layout.addWidget(self.date_edit)
        date_layout.addStretch()
        layout.addLayout(date_layout)
        
        # Team selection section
        team_group = QGroupBox("Team Selection")
        team_layout = QVBoxLayout()
        
        # Team Us selection
        team_us_layout = QHBoxLayout()
        team_us_layout.addWidget(QLabel("Team Us:"))
        self.team_us_combo = QComboBox()
        self.team_us_combo.currentIndexChanged.connect(self.on_team_us_selected)
        team_us_layout.addWidget(self.team_us_combo)
        team_layout.addLayout(team_us_layout)
        
        # Opponent (always Opp1 with alias)
        opponent_layout = QHBoxLayout()
        opponent_layout.addWidget(QLabel("Opponent:"))
        opponent_label = QLabel("Opp1")
        opponent_label.setStyleSheet("font-weight: bold;")
        opponent_layout.addWidget(opponent_label)
        opponent_layout.addWidget(QLabel("Alias:"))
        self.opponent_alias_input = QLineEdit()
        self.opponent_alias_input.setPlaceholderText("Enter opponent team alias (e.g., 'State University')")
        opponent_layout.addWidget(self.opponent_alias_input)
        team_layout.addLayout(opponent_layout)
        
        team_group.setLayout(team_layout)
        layout.addWidget(team_group)
        
        # Starting Lineup section
        lineup_group = QGroupBox("Starting Lineup for Team Us")
        lineup_layout = QVBoxLayout()
        
        # Instructions
        instructions = QLabel("Select players for each position. Each player can only be selected once.")
        instructions.setWordWrap(True)
        lineup_layout.addWidget(instructions)
        
        # Position grid layout
        position_grid = QGridLayout()
        position_grid.setSpacing(15)
        position_grid.setContentsMargins(20, 10, 20, 10)
        
        # Store position widgets
        self.position_widgets = {}  # position -> (player_combo, role_combo)
        
        # Top row: LF(4), MF(3), RF(2) - Front row
        top_row_positions = [4, 3, 2]
        for col, pos in enumerate(top_row_positions):
            pos_name, pos_abbrev = self.position_info[pos]
            self._create_position_widget(position_grid, pos, pos_name, pos_abbrev, 0, col)
        
        # Add a separator line between front and back row
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        position_grid.addWidget(separator, 1, 0, 1, 6)
        
        # Bottom row: LB(5), MB(6), RB(1) - Back row
        bottom_row_positions = [5, 6, 1]
        for col, pos in enumerate(bottom_row_positions):
            pos_name, pos_abbrev = self.position_info[pos]
            self._create_position_widget(position_grid, pos, pos_name, pos_abbrev, 2, col)
        
        lineup_layout.addLayout(position_grid)
        
        # Libero selection
        libero_layout = QHBoxLayout()
        libero_layout.addWidget(QLabel("Libero:"))
        self.libero_combo = QComboBox()
        self.libero_combo.addItem("-- No Libero --", None)
        libero_layout.addWidget(self.libero_combo)
        libero_layout.addStretch()
        lineup_layout.addLayout(libero_layout)
        
        lineup_group.setLayout(lineup_layout)
        layout.addWidget(lineup_group)
        
        # Serving team selection
        serving_group = QGroupBox("Serving Team")
        serving_layout = QHBoxLayout()
        self.serving_button_group = QButtonGroup()
        
        self.serve_us_radio = QRadioButton("Team Us")
        self.serve_us_radio.setChecked(True)
        self.serve_them_radio = QRadioButton("Opponent (Opp1)")
        
        self.serving_button_group.addButton(self.serve_us_radio, 0)
        self.serving_button_group.addButton(self.serve_them_radio, 1)
        
        serving_layout.addWidget(self.serve_us_radio)
        serving_layout.addWidget(self.serve_them_radio)
        serving_layout.addStretch()
        serving_group.setLayout(serving_layout)
        layout.addWidget(serving_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_create = QPushButton("Create Game & Start Tracking")
        self.btn_create.clicked.connect(self.create_game_and_start)
        button_layout.addWidget(self.btn_cancel)
        button_layout.addWidget(self.btn_create)
        layout.addLayout(button_layout)
        
        # Populate teams
        self.populate_teams()
        
        # Initially disable lineup until team is selected
        self.set_lineup_enabled(False)
    
    def _create_position_widget(self, grid_layout, position, pos_name, pos_abbrev, row, col):
        """Create a position widget with player and role dropdowns."""
        # Adjust row for separator (row 1 is separator)
        actual_row = row if row < 1 else row + 1
        
        # Position label
        pos_label = QLabel(f"{pos_abbrev}\n({pos_name})")
        pos_label.setAlignment(Qt.AlignCenter)
        pos_label.setStyleSheet("font-weight: bold; padding: 5px; background-color: #f0f0f0; border: 1px solid #ccc;")
        grid_layout.addWidget(pos_label, actual_row, col * 2, 1, 2)
        
        # Player combo
        player_combo = QComboBox()
        player_combo.addItem("-- Select Player --", None)
        player_combo.currentIndexChanged.connect(lambda idx, p=position: self.on_player_selected(p, idx))
        grid_layout.addWidget(QLabel("Player:"), actual_row + 1, col * 2)
        grid_layout.addWidget(player_combo, actual_row + 1, col * 2 + 1)
        
        # Role combo
        role_combo = QComboBox()
        role_combo.addItems(['S', 'RS', 'RH', 'MH', 'OH', 'DS'])
        role_combo.setEditable(True)
        grid_layout.addWidget(QLabel("Role:"), actual_row + 2, col * 2)
        grid_layout.addWidget(role_combo, actual_row + 2, col * 2 + 1)
        
        self.position_widgets[position] = (player_combo, role_combo)
    
    def populate_teams(self):
        """Populate team dropdown."""
        try:
            teams = self.db.get_all_teams()
            self.team_us_combo.clear()
            self.team_us_combo.addItem("-- Select Team Us --", None)
            for team_id, team_name in teams:
                self.team_us_combo.addItem(team_name, team_id)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load teams: {str(e)}")
    
    def on_team_us_selected(self, index):
        """Handle Team Us selection."""
        team_id = self.team_us_combo.currentData()
        if team_id:
            self.populate_roster(team_id)
            self.set_lineup_enabled(True)
        else:
            self.set_lineup_enabled(False)
    
    def populate_roster(self, team_id):
        """Populate player dropdowns with team roster."""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute("""
                SELECT player_id, name, jersey, player_number, role_code
                FROM players
                WHERE team_id = ?
                ORDER BY 
                    CASE 
                        WHEN CAST(jersey AS INTEGER) IS NOT NULL 
                        THEN CAST(jersey AS INTEGER)
                        ELSE 999999
                    END,
                    jersey, player_number
            """, (team_id,))
            
            players = cursor.fetchall()
            
            # Clear all combos
            for player_combo, _ in self.position_widgets.values():
                player_combo.clear()
                player_combo.addItem("-- Select Player --", None)
            
            self.libero_combo.clear()
            self.libero_combo.addItem("-- No Libero --", None)
            
            # Populate with players
            for player in players:
                player_id, name, jersey, player_number, role_code = player
                display_name = f"#{jersey or player_number} {name or 'Unknown'}"
                if role_code:
                    display_name += f" ({role_code})"
                
                # Add to all position combos
                for player_combo, _ in self.position_widgets.values():
                    player_combo.addItem(display_name, player_id)
                
                # Add to libero combo (only if role is Lib or no role set)
                if not role_code or role_code == 'Lib':
                    self.libero_combo.addItem(display_name, player_id)
        
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load roster: {str(e)}")
    
    def set_lineup_enabled(self, enabled):
        """Enable/disable lineup controls."""
        for player_combo, role_combo in self.position_widgets.values():
            player_combo.setEnabled(enabled)
            role_combo.setEnabled(enabled)
        self.libero_combo.setEnabled(enabled)
    
    def on_player_selected(self, position, index):
        """Handle player selection - prevent duplicate selections."""
        if index <= 0:  # "-- Select Player --" selected
            return
        
        selected_player_id = self.position_widgets[position][0].currentData()
        if not selected_player_id:
            return
        
        # Check if this player is selected in another position
        for other_pos, (other_combo, _) in self.position_widgets.items():
            if other_pos != position and other_combo.currentData() == selected_player_id:
                QMessageBox.warning(
                    self,
                    "Duplicate Player",
                    "This player is already selected in another position. Please select a different player."
                )
                # Reset to "-- Select Player --"
                self.position_widgets[position][0].setCurrentIndex(0)
                return
    
    def validate_lineup(self):
        """Validate that lineup is complete and valid."""
        # Check all positions are filled
        lineup = []
        selected_players = set()
        
        for position, (player_combo, role_combo) in self.position_widgets.items():
            player_id = player_combo.currentData()
            if not player_id:
                QMessageBox.warning(
                    self,
                    "Incomplete Lineup",
                    f"Please select a player for position {self.position_info[position][1]}."
                )
                return None
            
            if player_id in selected_players:
                QMessageBox.warning(
                    self,
                    "Duplicate Player",
                    "Each player can only be in one position."
                )
                return None
            
            selected_players.add(player_id)
            role = role_combo.currentText().strip()
            if not role:
                role = 'OH'  # Default role
            
            lineup.append((position, player_id, role))
        
        # Check libero is not in starting lineup
        libero_id = self.libero_combo.currentData()
        if libero_id and libero_id in selected_players:
            QMessageBox.warning(
                self,
                "Invalid Libero",
                "The libero cannot be one of the 6 players in the starting lineup."
            )
            return None
        
        return lineup
    
    def get_or_create_opp1_team(self):
        """Get or create the Opp1 team."""
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT team_id FROM teams WHERE name = 'Opp1'")
        result = cursor.fetchone()
        
        if result:
            return result[0]
        else:
            # Create Opp1 team
            return self.db.add_team("Opp1")
    
    def create_game_and_start(self):
        """Create the game, initialize lineup, and launch data entry."""
        # Validate Team Us selection
        team_us_id = self.team_us_combo.currentData()
        if not team_us_id:
            QMessageBox.warning(self, "Validation Error", "Please select Team Us.")
            return
        
        # Get or create Opp1 team
        try:
            team_them_id = self.get_or_create_opp1_team()
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Failed to get/create Opp1 team:\n{str(e)}")
            return
        
        # Validate lineup
        lineup_data = self.validate_lineup()
        if not lineup_data:
            return
        
        # Extract lineup (position, player_id) tuples
        lineup = [(pos, player_id) for pos, player_id, _ in lineup_data]
        
        # Determine serving team
        serving = self.serve_us_radio.isChecked()
        
        # Get opponent alias
        opponent_alias = self.opponent_alias_input.text().strip()
        if not opponent_alias:
            opponent_alias = "Opp1"
        
        try:
            # Create game
            self.game_id = self.db.start_game(team_us_id, team_them_id)
            
            # Update game with opponent alias in notes field
            if opponent_alias != "Opp1":
                cursor = self.db.conn.cursor()
                cursor.execute(
                    "UPDATE games SET notes = ? WHERE game_id = ?",
                    (f"Opponent: {opponent_alias}", self.game_id)
                )
                self.db.conn.commit()
            
            # Initialize lineup using LineupManager
            lineup_manager = LineupManager(self.db)
            lineup_manager.initialize_game(team_us_id, lineup, serving=serving)
            
            # Update role_code in active_lineup for each position based on user selection
            cursor = self.db.conn.cursor()
            for pos, player_id, role in lineup_data:
                if role:
                    cursor.execute("""
                        UPDATE active_lineup
                        SET role_code = ?
                        WHERE team_id = ? AND position_number = ? AND player_id = ?
                    """, (role, team_us_id, pos, player_id))
            
            # Update libero role in players table if selected
            libero_id = self.libero_combo.currentData()
            if libero_id:
                cursor.execute(
                    "UPDATE players SET role_code = 'Lib' WHERE player_id = ?",
                    (libero_id,)
                )
            
            self.db.conn.commit()
            
            # Populate game_players for team_them (opponent)
            # Default to team_id 12 with player_ids 30, 31, 32, 33
            cursor = self.db.conn.cursor()
            default_opponent_team_id = 12
            default_opponent_player_ids = [30, 31, 32, 33]
            
            # Check if team_them_id matches the default team
            if team_them_id == default_opponent_team_id:
                for player_id in default_opponent_player_ids:
                    try:
                        self.db.add_player_to_game(self.game_id, team_them_id, player_id)
                    except Exception as e:
                        # Player might already be in game or not exist - log but continue
                        print(f"Warning: Could not add player {player_id} to game: {e}")
            
            self.db.conn.commit()
            
            # Store values for caller
            self.team_us_id = team_us_id
            self.team_them_id = team_them_id
            cursor = self.db.conn.cursor()
            cursor.execute("SELECT name FROM teams WHERE team_id = ?", (team_us_id,))
            self.team_us_name = cursor.fetchone()[0]
            self.team_them_name = opponent_alias
            
            # Launch data entry window
            self.launch_data_entry()
            
            # Accept dialog
            self.accept()
            
        except Exception as e:
            self.db.conn.rollback()
            QMessageBox.critical(
                self,
                "Database Error",
                f"Failed to create game:\n{str(e)}"
            )
    
    def launch_data_entry(self):
        """Launch the data entry window."""
        try:
            # Load data entry UI
            ui_file = Path(__file__).parent / "inputTouchesVoice.ui"
            if not ui_file.exists():
                QMessageBox.warning(
                    self,
                    "UI File Not Found",
                    f"Data entry UI file not found: {ui_file}\n"
                    "The game has been created, but data entry cannot be launched."
                )
                return
            
            loader = QUiLoader()
            ui_widget = loader.load(str(ui_file))
            
            if not ui_widget:
                QMessageBox.warning(
                    self,
                    "UI Load Error",
                    "Failed to load data entry UI file.\n"
                    "The game has been created, but data entry cannot be launched."
                )
                return
            
            # Create and show data entry window with locked game selection
            data_entry_window = DataEntryWindow(
                ui_widget=ui_widget,
                db=self.db,
                team_us_id=self.team_us_id,
                team_them_id=self.team_them_id,
                game_id=self.game_id,
                lock_game_selection=True
            )
            
            data_entry_window.show()
            
        except Exception as e:
            QMessageBox.warning(
                self,
                "Launch Error",
                f"Failed to launch data entry window:\n{str(e)}\n\n"
                "The game has been created successfully."
            )
