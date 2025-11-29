"""
UI for adding players to both teams.
"""

import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QTableWidget, QTableWidgetItem, QMessageBox,
    QGroupBox, QHeaderView, QComboBox
)
from PySide6.QtCore import Qt
from database import VideoStatsDB


class AddPlayersDialog(QDialog):
    """Dialog for adding players to both teams for a specific game."""
    
    def __init__(self, parent=None, db: VideoStatsDB = None, game_id: int = None, team_us_id: int = None, team_them_id: int = None, team_us_name: str = None, team_them_name: str = None):
        super().__init__(parent)
        self.db = db or VideoStatsDB()
        self.game_id = game_id
        self.team_us_id = team_us_id
        self.team_them_id = team_them_id
        self.team_us_name = team_us_name or "Our Team"
        self.team_them_name = team_them_name or "Opponent Team"
        
        self.setWindowTitle("Add Players")
        self.setGeometry(100, 100, 800, 600)
        self.setModal(True)  # Make it modal
        
        main_layout = QVBoxLayout(self)
        
        # Create two columns for the teams
        teams_layout = QHBoxLayout()
        
        # Our Team section
        our_team_group = QGroupBox(self.team_us_name)
        our_team_layout = QVBoxLayout()
        
        # Select existing player dropdown for our team
        our_select_layout = QHBoxLayout()
        our_select_layout.addWidget(QLabel("Select Existing Player:"))
        self.our_player_combo = QComboBox()
        self.our_player_combo.setEditable(False)
        self.our_player_combo.addItem("-- Select or enter new --", None)
        self.our_player_combo.currentIndexChanged.connect(lambda: self.on_player_selected("our"))
        our_select_layout.addWidget(self.our_player_combo)
        our_team_layout.addLayout(our_select_layout)
        
        # Player number input for our team
        our_input_layout = QHBoxLayout()
        our_input_layout.addWidget(QLabel("Number:"))
        self.our_player_number = QLineEdit()
        self.our_player_number.setPlaceholderText("e.g., 1, 10, A1, 12B")
        our_input_layout.addWidget(self.our_player_number)
        
        our_input_layout.addWidget(QLabel("Name (optional):"))
        self.our_player_name = QLineEdit()
        self.our_player_name.setPlaceholderText("Player name")
        our_input_layout.addWidget(self.our_player_name)
        
        self.our_add_button = QPushButton("Add Player")
        self.our_add_button.clicked.connect(lambda: self.add_player(self.team_us_id, self.our_player_number.text(), self.our_player_name.text(), "our"))
        our_input_layout.addWidget(self.our_add_button)
        
        our_team_layout.addLayout(our_input_layout)
        
        # Table for our team players
        self.our_players_table = QTableWidget()
        self.our_players_table.setColumnCount(2)
        self.our_players_table.setHorizontalHeaderLabels(["Number", "Name"])
        self.our_players_table.horizontalHeader().setStretchLastSection(True)
        self.our_players_table.setSelectionBehavior(QTableWidget.SelectRows)
        our_team_layout.addWidget(self.our_players_table)
        
        # Delete button for our team
        self.our_delete_button = QPushButton("Delete Selected")
        self.our_delete_button.clicked.connect(lambda: self.delete_player(self.our_players_table, "our"))
        our_team_layout.addWidget(self.our_delete_button)
        
        our_team_group.setLayout(our_team_layout)
        teams_layout.addWidget(our_team_group)
        
        # Opponent Team section
        them_team_group = QGroupBox(self.team_them_name)
        them_team_layout = QVBoxLayout()
        
        # Select existing player dropdown for opponent team
        them_select_layout = QHBoxLayout()
        them_select_layout.addWidget(QLabel("Select Existing Player:"))
        self.them_player_combo = QComboBox()
        self.them_player_combo.setEditable(False)
        self.them_player_combo.addItem("-- Select or enter new --", None)
        self.them_player_combo.currentIndexChanged.connect(lambda: self.on_player_selected("them"))
        them_select_layout.addWidget(self.them_player_combo)
        them_team_layout.addLayout(them_select_layout)
        
        # Player number input for opponent team
        them_input_layout = QHBoxLayout()
        them_input_layout.addWidget(QLabel("Number:"))
        self.them_player_number = QLineEdit()
        self.them_player_number.setPlaceholderText("e.g., 1, 10, A1, 12B")
        them_input_layout.addWidget(self.them_player_number)
        
        them_input_layout.addWidget(QLabel("Name (optional):"))
        self.them_player_name = QLineEdit()
        self.them_player_name.setPlaceholderText("Player name")
        them_input_layout.addWidget(self.them_player_name)
        
        self.them_add_button = QPushButton("Add Player")
        self.them_add_button.clicked.connect(lambda: self.add_player(self.team_them_id, self.them_player_number.text(), self.them_player_name.text(), "them"))
        them_input_layout.addWidget(self.them_add_button)
        
        them_team_layout.addLayout(them_input_layout)
        
        # Table for opponent team players
        self.them_players_table = QTableWidget()
        self.them_players_table.setColumnCount(2)
        self.them_players_table.setHorizontalHeaderLabels(["Number", "Name"])
        self.them_players_table.horizontalHeader().setStretchLastSection(True)
        self.them_players_table.setSelectionBehavior(QTableWidget.SelectRows)
        them_team_layout.addWidget(self.them_players_table)
        
        # Delete button for opponent team
        self.them_delete_button = QPushButton("Delete Selected")
        self.them_delete_button.clicked.connect(lambda: self.delete_player(self.them_players_table, "them"))
        them_team_layout.addWidget(self.them_delete_button)
        
        them_team_group.setLayout(them_team_layout)
        teams_layout.addWidget(them_team_group)
        
        main_layout.addLayout(teams_layout)
        
        # Close button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)
        main_layout.addLayout(button_layout)
        
        # Load existing players
        try:
            self.load_players()
            self.load_existing_players_dropdowns()
        except Exception as e:
            # Don't fail if we can't load players - user can still add new ones
            print(f"Warning: Could not load existing players: {e}")
        
        # Set focus
        self.our_player_number.setFocus()
    
    def load_players(self):
        """Load existing players for both teams."""
        try:
            if not self.db.conn:
                self.db.connect()
            
            # Load our team players
            if self.team_us_id:
                self.load_team_players(self.team_us_id, self.our_players_table)
            
            # Load opponent team players
            if self.team_them_id:
                self.load_team_players(self.team_them_id, self.them_players_table)
        except Exception as e:
            QMessageBox.warning(self, "Warning", f"Could not load existing players:\n{str(e)}")
    
    def load_existing_players_dropdowns(self):
        """Load all existing players for both teams into the dropdowns."""
        if not self.db.conn:
            self.db.connect()
        
        cursor = self.db.conn.cursor()
        
        # Load our team players
        if self.team_us_id:
            cursor.execute(
                """SELECT player_id, player_number, name FROM players 
                   WHERE team_id = ? 
                   ORDER BY 
                       CASE 
                           WHEN CAST(player_number AS INTEGER) IS NOT NULL 
                           THEN CAST(player_number AS INTEGER)
                           ELSE 999999
                       END,
                       player_number""",
                (self.team_us_id,)
            )
            our_players = cursor.fetchall()
            for player in our_players:
                player_id, player_number, player_name = player
                display_text = f"{player_number}"
                if player_name:
                    display_text += f" - {player_name}"
                self.our_player_combo.addItem(display_text, player_id)
        
        # Load opponent team players
        if self.team_them_id:
            cursor.execute(
                """SELECT player_id, player_number, name FROM players 
                   WHERE team_id = ? 
                   ORDER BY 
                       CASE 
                           WHEN CAST(player_number AS INTEGER) IS NOT NULL 
                           THEN CAST(player_number AS INTEGER)
                           ELSE 999999
                       END,
                       player_number""",
                (self.team_them_id,)
            )
            them_players = cursor.fetchall()
            for player in them_players:
                player_id, player_number, player_name = player
                display_text = f"{player_number}"
                if player_name:
                    display_text += f" - {player_name}"
                self.them_player_combo.addItem(display_text, player_id)
    
    def on_player_selected(self, team_type: str):
        """Handle selection from the player dropdown."""
        if team_type == "our":
            combo = self.our_player_combo
            number_field = self.our_player_number
            name_field = self.our_player_name
            team_id = self.team_us_id
        else:
            combo = self.them_player_combo
            number_field = self.them_player_number
            name_field = self.them_player_name
            team_id = self.team_them_id
        
        # Get selected player_id
        player_id = combo.currentData()
        if player_id is None:
            # "-- Select or enter new --" was selected, clear fields
            number_field.clear()
            name_field.clear()
            return
        
        # Load player details from database
        if not self.db.conn:
            self.db.connect()
        
        cursor = self.db.conn.cursor()
        cursor.execute(
            "SELECT player_number, name FROM players WHERE player_id = ? AND team_id = ?",
            (player_id, team_id)
        )
        result = cursor.fetchone()
        
        if result:
            player_number, player_name = result
            number_field.setText(str(player_number))
            name_field.setText(player_name or "")
    
    def load_team_players(self, team_id: int, table: QTableWidget):
        """Load players for a specific team in this game into the table."""
        if not self.game_id:
            # Fallback to all team players if no game_id
            cursor = self.db.conn.cursor()
            cursor.execute(
                """SELECT player_id, player_number, name FROM players 
                   WHERE team_id = ? 
                   ORDER BY 
                       CASE 
                           WHEN CAST(player_number AS INTEGER) IS NOT NULL 
                           THEN CAST(player_number AS INTEGER)
                           ELSE 999999
                       END,
                       player_number""",
                (team_id,)
            )
            players = cursor.fetchall()
        else:
            # Load only players in this game
            players = self.db.get_game_players(self.game_id, team_id)
        
        table.setRowCount(len(players))
        for row, player in enumerate(players):
            table.setItem(row, 0, QTableWidgetItem(str(player[1])))  # number
            table.setItem(row, 1, QTableWidgetItem(player[2] or ""))  # name
            # Store player_id in the item for deletion
            table.item(row, 0).setData(Qt.UserRole, player[0])
    
    def add_player(self, team_id: int, player_number: str, player_name: str, team_type: str):
        """Add a player to the specified team and game roster.
        
        Args:
            team_id: The team ID
            player_number: Player number (can be alphanumeric, e.g., "1", "10", "A1", "12B")
            player_name: Player name (optional)
            team_type: "our" or "them"
        """
        if not team_id:
            QMessageBox.warning(self, "Error", "Team ID not set. Please configure teams first.")
            return
        
        if not self.game_id:
            QMessageBox.warning(self, "Error", "Game ID not set. Please configure game first.")
            return
        
        player_number = player_number.strip() if player_number else ""
        if not player_number:
            QMessageBox.warning(self, "Validation Error", "Please enter a player number.")
            if team_type == "our":
                self.our_player_number.setFocus()
            else:
                self.them_player_number.setFocus()
            return
        
        player_name = player_name.strip() if player_name else None
        
        try:
            if not self.db.conn:
                self.db.connect()
            
            # Check if player already exists for this team
            cursor = self.db.conn.cursor()
            cursor.execute(
                "SELECT player_id FROM players WHERE team_id = ? AND player_number = ?",
                (team_id, player_number)
            )
            existing_player = cursor.fetchone()
            
            player_id = None
            if existing_player:
                # Player already exists, use existing player_id
                player_id = existing_player[0]
            else:
                # Create new player
                player_id = self.db.add_player(team_id, player_number, player_name)
            
            # Add player to game roster
            self.db.add_player_to_game(self.game_id, team_id, player_id)
            
            # Refresh the appropriate table
            if team_type == "our":
                self.load_team_players(team_id, self.our_players_table)
                self.our_player_number.clear()
                self.our_player_name.clear()
                self.our_player_combo.setCurrentIndex(0)  # Reset to "-- Select or enter new --"
                self.our_player_number.setFocus()
            else:
                self.load_team_players(team_id, self.them_players_table)
                self.them_player_number.clear()
                self.them_player_name.clear()
                self.them_player_combo.setCurrentIndex(0)  # Reset to "-- Select or enter new --"
                self.them_player_number.setFocus()
            
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Failed to add player:\n{str(e)}")
    
    def delete_player(self, table: QTableWidget, team_type: str):
        """Remove selected player from the game roster."""
        current_row = table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a player to remove.")
            return
        
        player_id = table.item(current_row, 0).data(Qt.UserRole)
        player_number = table.item(current_row, 0).text()
        
        reply = QMessageBox.question(
            self, "Confirm Remove",
            f"Remove player number {player_number} from this game?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                if not self.db.conn:
                    self.db.connect()
                
                # Remove from game roster (not from players table)
                team_id = self.team_us_id if team_type == "our" else self.team_them_id
                self.db.remove_player_from_game(self.game_id, team_id, player_id)
                
                # Refresh the table
                self.load_team_players(team_id, table)
                
            except Exception as e:
                QMessageBox.critical(self, "Database Error", f"Failed to remove player:\n{str(e)}")


if __name__ == "__main__":
    # Test the dialog
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    db = VideoStatsDB()
    db.initialize_database()
    db.connect()
    
    # Get team IDs (assuming teams exist)
    cursor = db.conn.cursor()
    cursor.execute("SELECT team_id, name FROM teams LIMIT 2")
    teams = cursor.fetchall()
    
    team_us_id = teams[0][0] if len(teams) > 0 else None
    team_them_id = teams[1][0] if len(teams) > 1 else None
    team_us_name = teams[0][1] if len(teams) > 0 else "Our Team"
    team_them_name = teams[1][1] if len(teams) > 1 else "Opponent Team"
    
    dialog = AddPlayersDialog(
        db=db,
        team_us_id=team_us_id,
        team_them_id=team_them_id,
        team_us_name=team_us_name,
        team_them_name=team_them_name
    )
    dialog.exec()
    
    db.close()
    sys.exit(0)

