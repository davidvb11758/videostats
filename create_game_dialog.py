"""
Enhanced dialog for creating a new game with lineup configuration.
Allows selecting Team_US, setting starting lineup, and launching data entry.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QMessageBox, QDateEdit, QGridLayout, QGroupBox, QLineEdit, QRadioButton,
    QButtonGroup, QWidget, QFrame, QScrollArea
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
from utils import resource_path
import json


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
        ui_file = resource_path("create_game_dialog.ui")
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
            self.libero_combo.currentIndexChanged.connect(self.on_libero_selected)
        
        # Non-starter players widgets
        self.non_starter_group = self.findChild(QGroupBox, "nonStarterGroup")
        self.non_starter_scroll = self.findChild(QScrollArea, "nonStarterScrollArea")
        self.non_starter_grid = None
        self.non_starter_widgets = {}  # {player_id: (label, role_combo)}
        if self.non_starter_scroll:
            scroll_widget = self.non_starter_scroll.findChild(QWidget, "nonStarterScrollAreaWidgetContents")
            if scroll_widget:
                self.non_starter_grid = scroll_widget.findChild(QGridLayout, "nonStarterGrid")
        
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
            self.update_non_starter_players()
        else:
            self.set_lineup_enabled(False)
            self.clear_non_starter_players()
    
    def populate_roster(self, team_id):
        """Populate player dropdowns with team roster."""
        try:
            cursor = self.db.conn.cursor()
            cursor.execute("""
                SELECT player_id, name, jersey, player_number
                FROM players
                WHERE team_id = %s
                ORDER BY name ASC
            """, (team_id,))
            
            players = cursor.fetchall()
            
            # Clear all combos
            for player_combo, _ in self.position_widgets.values():
                player_combo.blockSignals(True)
                player_combo.clear()
                player_combo.addItem("-- Select Player --", None)
                player_combo.blockSignals(False)
            
            self.libero_combo.blockSignals(True)
            self.libero_combo.clear()
            self.libero_combo.addItem("-- No Libero --", None)
            self.libero_combo.blockSignals(False)
            
            # Populate with players - use a set to track added player_ids per combo to prevent duplicates
            for player_combo, _ in self.position_widgets.values():
                added_player_ids = set()
                player_combo.blockSignals(True)
                for player in players:
                    player_id, name, jersey, player_number = player
                    # Skip if already added (safety check)
                    if player_id in added_player_ids:
                        continue
                    added_player_ids.add(player_id)
                    player_name = name or 'Unknown'
                    jersey_number = jersey or player_number
                    role = ''
                    
                    # Format: "player name (jersey # role)"
                    if role:
                        display_name = f"{player_name} ({jersey_number} {role})"
                    else:
                        display_name = f"{player_name} ({jersey_number})"
                    
                    player_combo.addItem(display_name, player_id)
                player_combo.blockSignals(False)
            
            # Populate libero combo
            added_libero_ids = set()
            self.libero_combo.blockSignals(True)
            for player in players:
                player_id, name, jersey, player_number = player
                # Skip if already added (safety check)
                if player_id in added_libero_ids:
                    continue
                added_libero_ids.add(player_id)
                player_name = name or 'Unknown'
                jersey_number = jersey or player_number
                role = ''
                
                # Format: "player name (jersey # role)"
                if role:
                    display_name = f"{player_name} ({jersey_number} {role})"
                else:
                    display_name = f"{player_name} ({jersey_number})"
                
                self.libero_combo.addItem(display_name, player_id)
            self.libero_combo.blockSignals(False)
        
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load roster: {str(e)}")
    
    def update_libero_combo(self):
        """Update libero combo to exclude players in the starting lineup."""
        if not self.libero_combo:
            return
        
        # Get currently selected libero
        current_libero_id = self.libero_combo.currentData()
        current_libero_index = self.libero_combo.currentIndex()
        
        # Get all players currently in starting lineup
        lineup_player_ids = set()
        for player_combo, _ in self.position_widgets.values():
            player_id = player_combo.currentData()
            if player_id:
                lineup_player_ids.add(player_id)
        
        # Rebuild libero combo, excluding lineup players
        self.libero_combo.blockSignals(True)
        self.libero_combo.clear()
        self.libero_combo.addItem("-- No Libero --", None)
        
        # Get team ID
        team_id = self.team_us_combo.currentData()
        if not team_id:
            self.libero_combo.blockSignals(False)
            return
        
        try:
            cursor = self.db.conn.cursor()
            cursor.execute("""
                SELECT player_id, name, jersey, player_number
                FROM players
                WHERE team_id = %s
                ORDER BY name ASC
            """, (team_id,))
            
            players = cursor.fetchall()
            
            for player in players:
                player_id, name, jersey, player_number = player
                # Skip if player is in starting lineup
                if player_id in lineup_player_ids:
                    continue
                
                player_name = name or 'Unknown'
                jersey_number = jersey or player_number
                role = ''
                
                # Format: "player name (jersey # role)"
                if role:
                    display_name = f"{player_name} ({jersey_number} {role})"
                else:
                    display_name = f"{player_name} ({jersey_number})"
                
                self.libero_combo.addItem(display_name, player_id)
            
            # Restore previous selection if still valid
            if current_libero_id and current_libero_id not in lineup_player_ids:
                for i in range(self.libero_combo.count()):
                    if self.libero_combo.itemData(i) == current_libero_id:
                        self.libero_combo.setCurrentIndex(i)
                        break
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to update libero combo: {str(e)}")
        
        self.libero_combo.blockSignals(False)
        # Update non-starter players list after libero combo update
        self.update_non_starter_players()
    
    def on_libero_selected(self, index):
        """Handle libero selection - update starting lineup combos to exclude libero."""
        if index <= 0:  # "-- No Libero --" selected
            # Libero deselected, update all position combos to include all players
            self.update_position_combos()
            self.update_non_starter_players()
            return
        
        libero_id = self.libero_combo.currentData()
        if not libero_id:
            return
        
        # Check if libero is selected in any starting lineup position
        for position, (player_combo, _) in self.position_widgets.items():
            if player_combo.currentData() == libero_id:
                QMessageBox.warning(
                    self,
                    "Invalid Selection",
                    "This player is in the starting lineup. The libero cannot be one of the 6 starting players."
                )
                # Reset libero to "-- No Libero --"
                self.libero_combo.blockSignals(True)
                self.libero_combo.setCurrentIndex(0)
                self.libero_combo.blockSignals(False)
                return
        
        # Update position combos to exclude libero
        self.update_position_combos()
        # Update non-starter players list (exclude libero)
        self.update_non_starter_players()
    
    def update_position_combos(self):
        """Update all position combos to exclude the selected libero."""
        libero_id = self.libero_combo.currentData() if self.libero_combo else None
        
        # Get team ID
        team_id = self.team_us_combo.currentData()
        if not team_id:
            return
        
        try:
            cursor = self.db.conn.cursor()
            cursor.execute("""
                SELECT player_id, name, jersey, player_number
                FROM players
                WHERE team_id = %s
                ORDER BY name ASC
            """, (team_id,))
            
            players = cursor.fetchall()
            
            # Get currently selected players for each position
            current_selections = {}
            for pos, (player_combo, _) in self.position_widgets.items():
                current_selections[pos] = player_combo.currentData()
            
            # Rebuild each position combo
            for position, (player_combo, _) in self.position_widgets.items():
                player_combo.blockSignals(True)
                player_combo.clear()
                player_combo.addItem("-- Select Player --", None)
                
                for player in players:
                    player_id, name, jersey, player_number = player
                    
                    # Skip if this is the libero
                    if libero_id and player_id == libero_id:
                        continue
                    
                    player_name = name or 'Unknown'
                    jersey_number = jersey or player_number
                    role = ''
                    
                    # Format: "player name (jersey # role)"
                    if role:
                        display_name = f"{player_name} ({jersey_number} {role})"
                    else:
                        display_name = f"{player_name} ({jersey_number})"
                    
                    player_combo.addItem(display_name, player_id)
                
                # Restore previous selection if still valid
                if current_selections.get(position):
                    for i in range(player_combo.count()):
                        if player_combo.itemData(i) == current_selections[position]:
                            player_combo.setCurrentIndex(i)
                            break
                
                player_combo.blockSignals(False)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to update position combos: {str(e)}")
    
    def set_lineup_enabled(self, enabled):
        """Enable/disable lineup controls."""
        for player_combo, role_combo in self.position_widgets.values():
            player_combo.setEnabled(enabled)
            role_combo.setEnabled(enabled)
        self.libero_combo.setEnabled(enabled)
        if self.non_starter_group:
            self.non_starter_group.setEnabled(enabled)
    
    def clear_non_starter_players(self):
        """Clear all non-starter player widgets."""
        if not self.non_starter_grid:
            return
        
        # Remove all widgets from the grid
        while self.non_starter_grid.count():
            item = self.non_starter_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.non_starter_widgets.clear()
    
    def update_non_starter_players(self):
        """Update the list of non-starter players (excluding libero and starting lineup)."""
        if not self.non_starter_grid:
            return
        
        team_id = self.team_us_combo.currentData()
        if not team_id:
            self.clear_non_starter_players()
            return
        
        # Get all players in starting lineup
        starting_player_ids = set()
        for player_combo, _ in self.position_widgets.values():
            player_id = player_combo.currentData()
            if player_id:
                starting_player_ids.add(player_id)
        
        # Get libero ID
        libero_id = self.libero_combo.currentData()
        
        try:
            if not self.db.conn:
                self.db.connect()
            cursor = self.db.conn.cursor()
            cursor.execute("""
                SELECT player_id, name, jersey, player_number
                FROM players
                WHERE team_id = %s
                ORDER BY name ASC
            """, (team_id,))
            
            all_players = cursor.fetchall()
            
            # Filter to non-starter players (exclude starting lineup and libero)
            non_starter_players = []
            for player in all_players:
                player_id, name, jersey, player_number = player
                # Skip if in starting lineup or is libero
                if player_id in starting_player_ids or player_id == libero_id:
                    continue
                non_starter_players.append(player)
            
            # Clear existing widgets
            self.clear_non_starter_players()
            
            # Create widgets for each non-starter player
            for row, player in enumerate(non_starter_players):
                player_id, name, jersey, player_number = player
                player_name = name or 'Unknown'
                jersey_number = jersey or player_number
                
                # Create label
                label = QLabel(f"{player_name} ({jersey_number}):")
                label.setMinimumWidth(150)
                
                # Create role combo
                role_combo = QComboBox()
                role_combo.addItems(['S', 'RS', 'RH', 'MH', 'OH', 'DS'])
                role_combo.setEditable(True)
                # Default to empty (user must select)
                
                # Add to grid
                self.non_starter_grid.addWidget(label, row, 0)
                self.non_starter_grid.addWidget(role_combo, row, 1)
                
                # Store reference
                self.non_starter_widgets[player_id] = (label, role_combo)
        
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to update non-starter players: {str(e)}")
    
    def on_player_selected(self, position, index):
        """Handle player selection - prevent duplicate selections and libero conflicts."""
        if index <= 0:  # "-- Select Player --" selected
            # Player deselected, update libero combo to include this player again
            self.update_libero_combo()
            return
        
        selected_player_id = self.position_widgets[position][0].currentData()
        if not selected_player_id:
            return
        
        # Check if this player is the selected libero
        libero_id = self.libero_combo.currentData()
        if libero_id and selected_player_id == libero_id:
            QMessageBox.warning(
                self,
                "Invalid Selection",
                "This player is selected as the libero. The libero cannot be in the starting lineup."
            )
            # Reset to "-- Select Player --"
            self.position_widgets[position][0].setCurrentIndex(0)
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
        
        # Update libero combo to exclude this player
        self.update_libero_combo()
        # Update non-starter players list
        self.update_non_starter_players()
    
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
        
        # Get game date from dateEdit widget
        game_date = None
        if self.date_edit:
            qdate = self.date_edit.date()
            # Convert QDate to datetime (set time to midnight)
            game_date = datetime(qdate.year(), qdate.month(), qdate.day())
        
        try:
            # Create game
            self.game_id = self.db.start_game(team_us_id, team_them_id, game_date=game_date)
            
            # Update game with opponent alias in notes field
            if opponent_alias != "Opp1":
                cursor = self.db.conn.cursor()
                cursor.execute(
                    "UPDATE games SET notes = %s WHERE game_id = %s",
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
                        SET role_code = %s
                        WHERE team_id = %s AND position_number = %s AND player_id = %s
                    """, (role, team_us_id, pos, player_id))
            
            # Update libero role in players table if selected
            libero_id = self.libero_combo.currentData()
            if libero_id:
                cursor.execute(
                    "UPDATE players SET role_code = 'Lib' WHERE player_id = %s",
                    (libero_id,)
                )
            
            self.db.conn.commit()
            
            # Populate game_players for team_us (all roster players)
            # This makes all players available for substitutions and libero replacements
            cursor = self.db.conn.cursor()
            cursor.execute("""
                SELECT player_id FROM players WHERE team_id = %s
            """, (team_us_id,))
            team_us_roster = cursor.fetchall()
            
            # Get role codes for starting lineup players
            starting_roles = {}
            for pos, player_id, role in lineup_data:
                starting_roles[player_id] = role
            
            # Get role codes for non-starter players
            non_starter_roles = {}
            for player_id, (label, role_combo) in self.non_starter_widgets.items():
                role = role_combo.currentText().strip()
                if role:
                    non_starter_roles[player_id] = role
            
            # Get libero role (always 'Lib')
            libero_id = self.libero_combo.currentData()
            if libero_id:
                non_starter_roles[libero_id] = 'Lib'
            
            for (player_id,) in team_us_roster:
                try:
                    # Get role code for this player
                    game_role_code = None
                    if player_id in starting_roles:
                        game_role_code = starting_roles[player_id]
                    elif player_id in non_starter_roles:
                        game_role_code = non_starter_roles[player_id]
                    
                    self.db.add_player_to_game(self.game_id, team_us_id, player_id, game_role_code)
                except Exception as e:
                    # Player might already be in game - log but continue
                    print(f"Warning: Could not add team_us player {player_id} to game: {e}")
            
            self.db.conn.commit()
            
            # Update initial_setup event to use game_role_code instead of role_code
            # The initial_setup event was created before game_players was populated,
            # so we need to update it now that game_role_code is available
            cursor = self.db.conn.cursor()
            cursor.execute("""
                SELECT id, payload
                FROM events
                WHERE game_id = %s AND team_id = %s AND event_type = 'initial_setup'
                ORDER BY created_at DESC, id DESC
                LIMIT 1
            """, (self.game_id, team_us_id))
            event_result = cursor.fetchone()
            if event_result:
                event_id, payload_json = event_result
                try:
                    payload = json.loads(payload_json) if isinstance(payload_json, str) else payload_json
                    lineup_snapshot = payload.get('lineup', {})
                    
                    # Update each player's role_code in the snapshot to use game_role_code
                    updated = False
                    for pos, player_data in lineup_snapshot.items():
                        player_id = player_data.get('player_id')
                        if player_id:
                            # Get game_role_code from game_players
                            cursor.execute("""
                                SELECT game_role_code
                                FROM game_players
                                WHERE game_id = %s AND team_id = %s AND player_id = %s
                            """, (self.game_id, team_us_id, player_id))
                            result = cursor.fetchone()
                            if result and result[0]:
                                # Update role_code in snapshot to use game_role_code
                                player_data['role_code'] = result[0]
                                updated = True
                    
                    # If we updated any roles, save the updated payload back to the event
                    if updated:
                        updated_payload_json = json.dumps(payload)
                        cursor.execute("""
                            UPDATE events
                            SET payload = %s
                            WHERE id = %s
                        """, (updated_payload_json, event_id))
                        self.db.conn.commit()
                        print(f"DEBUG: Updated initial_setup event {event_id} to use game_role_code")
                except Exception as e:
                    print(f"Warning: Could not update initial_setup event: {e}")
                    # Don't fail the whole operation if this update fails
            
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
            cursor.execute("SELECT name FROM teams WHERE team_id = %s", (team_us_id,))
            self.team_us_name = cursor.fetchone()[0]
            self.team_them_name = opponent_alias
            
            # Launch coordinate mapper (data entry window created but not shown)
            self.launch_coordinate_mapper()
            
            # Accept dialog
            self.accept()
            
        except Exception as e:
            self.db.conn.rollback()
            QMessageBox.critical(
                self,
                "Database Error",
                f"Failed to create game:\n{str(e)}"
            )
    
    def launch_coordinate_mapper(self):
        """Launch the coordinate mapper window (data entry window created but not shown)."""
        try:
            # Load data entry UI
            ui_file = resource_path("inputTouchesVoice.ui")
            if not ui_file.exists():
                QMessageBox.warning(
                    self,
                    "UI File Not Found",
                    f"Data entry UI file not found: {ui_file}\n"
                    "The game has been created, but coordinate mapper cannot be launched."
                )
                return
            
            loader = QUiLoader()
            ui_widget = loader.load(str(ui_file))
            
            if not ui_widget:
                QMessageBox.warning(
                    self,
                    "UI Load Error",
                    "Failed to load data entry UI file.\n"
                    "The game has been created, but coordinate mapper cannot be launched."
                )
                return
            
            # Create data entry window (but don't show it)
            # The coordinate mapper will be created and shown automatically
            data_entry_window = DataEntryWindow(
                ui_widget=ui_widget,
                db=self.db,
                team_us_id=self.team_us_id,
                team_them_id=self.team_them_id,
                game_id=self.game_id,
                lock_game_selection=True
            )
            
            # Don't show the data entry window - only coordinate mapper will be visible
            # Ensure coordinate mapper is visible and active
            if data_entry_window.coordinate_mapper:
                data_entry_window.coordinate_mapper.raise_()
                data_entry_window.coordinate_mapper.activateWindow()
            
        except Exception as e:
            QMessageBox.warning(
                self,
                "Launch Error",
                f"Failed to launch coordinate mapper:\n{str(e)}\n\n"
                "The game has been created successfully."
            )

