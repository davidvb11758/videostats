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
        
        # Load UI file
        ui_file = Path(__file__).parent / "create_game_dialog.ui"
        if not ui_file.exists():
            QMessageBox.critical(
                parent,
                "UI File Not Found",
                f"UI file not found: {ui_file}\nPlease ensure create_game_dialog.ui exists."
            )
            self.reject()
            return
        
        loader = QUiLoader()
        ui_widget = loader.load(str(ui_file))
        if not ui_widget:
            QMessageBox.critical(
                parent,
                "UI Load Error",
                f"Failed to load UI file: {ui_file}"
            )
            self.reject()
            return
        
        # Copy properties from loaded UI
        self.setWindowTitle(ui_widget.windowTitle())
        self.setGeometry(ui_widget.geometry())
        
        # Get main layout from UI and set it
        main_layout = ui_widget.layout()
        if main_layout:
            self.setLayout(main_layout)
            # Reparent all widgets to self
            for child in ui_widget.findChildren(QWidget):
                if child.parent() == ui_widget:
                    child.setParent(self)
        
        # Map UI widgets to class attributes
        self.date_edit = self.findChild(QDateEdit, "dateEdit")
        if self.date_edit:
            self.date_edit.setDate(QDate.currentDate())
        
        self.team_us_combo = self.findChild(QComboBox, "teamUsCombo")
        if self.team_us_combo:
            self.team_us_combo.currentIndexChanged.connect(self.on_team_us_selected)
        
        self.opponent_alias_input = self.findChild(QLineEdit, "opponentAliasInput")
        
        # Map position combos: position -> (player_combo, role_combo)
        self.position_widgets = {}
        position_map = {
            1: ("player1Combo", "role1Combo"),
            2: ("player2Combo", "role2Combo"),
            3: ("player3Combo", "role3Combo"),
            4: ("player4Combo", "role4Combo"),
            5: ("player5Combo", "role5Combo"),
            6: ("player6Combo", "role6Combo")
        }
        
        for pos, (player_name, role_name) in position_map.items():
            player_combo = self.findChild(QComboBox, player_name)
            role_combo = self.findChild(QComboBox, role_name)
            if player_combo and role_combo:
                player_combo.addItem("-- Select Player --", None)
                role_combo.addItems(['S', 'RS', 'RH', 'MH', 'OH', 'DS'])
                player_combo.currentIndexChanged.connect(lambda idx, p=pos: self.on_player_selected(p, idx))
                self.position_widgets[pos] = (player_combo, role_combo)
        
        self.libero_combo = self.findChild(QComboBox, "liberoCombo")
        if self.libero_combo:
            self.libero_combo.addItem("-- No Libero --", None)
        
        self.serve_us_radio = self.findChild(QRadioButton, "serveUsRadio")
        self.serve_them_radio = self.findChild(QRadioButton, "serveThemRadio")
        self.serving_button_group = QButtonGroup()
        if self.serve_us_radio and self.serve_them_radio:
            self.serving_button_group.addButton(self.serve_us_radio, 0)
            self.serving_button_group.addButton(self.serve_them_radio, 1)
        
        self.btn_cancel = self.findChild(QPushButton, "btnCancel")
        if self.btn_cancel:
            self.btn_cancel.clicked.connect(self.reject)
        self.btn_create = self.findChild(QPushButton, "btnCreate")
        if self.btn_create:
            self.btn_create.clicked.connect(self.create_game_and_start)
        
        # Populate teams
        self.populate_teams()
        
        # Initially disable lineup until team is selected
        self.set_lineup_enabled(False)
    
    
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
                        WHEN CAST(player_number AS INTEGER) IS NOT NULL 
                        THEN CAST(player_number AS INTEGER)
                        ELSE 999999
                    END,
                    player_number
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
            lineup_manager.initialize_game(self.game_id, team_us_id, lineup, serving=serving)
            
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
            
            # Populate game_players for team_us (all roster players)
            # This makes all players available for substitutions and libero replacements
            cursor = self.db.conn.cursor()
            cursor.execute("""
                SELECT player_id FROM players WHERE team_id = ?
            """, (team_us_id,))
            team_us_roster = cursor.fetchall()
            
            for (player_id,) in team_us_roster:
                try:
                    self.db.add_player_to_game(self.game_id, team_us_id, player_id)
                except Exception as e:
                    # Player might already be in game - log but continue
                    print(f"Warning: Could not add team_us player {player_id} to game: {e}")
            
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
