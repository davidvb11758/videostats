"""
Configuration screen for entering team names.
"""

import sys
from pathlib import Path
from PySide6.QtWidgets import (QDialog, QMessageBox, QVBoxLayout, QHBoxLayout, 
                               QLabel, QLineEdit, QPushButton, QSpacerItem, QSizePolicy,
                               QComboBox)
from PySide6.QtCore import Qt
from dbstuff.database import VideoStatsDB


class ConfigScreen(QDialog):
    """Configuration dialog for team setup."""
    
    def __init__(self, parent=None, db: VideoStatsDB = None):
        super().__init__(parent)
        self.db = db or VideoStatsDB()
        self.team_us_id = None
        self.team_them_id = None
        self.game_id = None
        
        self.setWindowTitle("Game Configuration")
        self.setGeometry(100, 100, 500, 300)
        
        # Create layout
        main_layout = QVBoxLayout(self)
        
        # Title label
        title_label = QLabel("Select teams for this game:")
        main_layout.addWidget(title_label)
        
        # Our Team
        our_team_label = QLabel("Our Team:")
        main_layout.addWidget(our_team_label)
        self.ui = type('UI', (), {})()
        self.ui.comboBoxOurTeam = QComboBox()
        self.ui.comboBoxOurTeam.setEditable(True)  # Allow typing new team name
        self.ui.comboBoxOurTeam.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)  # Don't auto-add typed text
        main_layout.addWidget(self.ui.comboBoxOurTeam)
        
        # Add New Team button for Our Team
        our_new_team_layout = QHBoxLayout()
        self.ui.lineEditNewOurTeam = QLineEdit()
        self.ui.lineEditNewOurTeam.setPlaceholderText("Enter new team name")
        our_new_team_layout.addWidget(self.ui.lineEditNewOurTeam)
        self.ui.pushButtonAddOurTeam = QPushButton("Add New Team")
        our_new_team_layout.addWidget(self.ui.pushButtonAddOurTeam)
        main_layout.addLayout(our_new_team_layout)
        
        # Opponent Team
        opponent_label = QLabel("Opponent Team:")
        main_layout.addWidget(opponent_label)
        self.ui.comboBoxOpponent = QComboBox()
        self.ui.comboBoxOpponent.setEditable(True)  # Allow typing new team name
        self.ui.comboBoxOpponent.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)  # Don't auto-add typed text
        main_layout.addWidget(self.ui.comboBoxOpponent)
        
        # Add New Team button for Opponent Team
        opponent_new_team_layout = QHBoxLayout()
        self.ui.lineEditNewOpponent = QLineEdit()
        self.ui.lineEditNewOpponent.setPlaceholderText("Enter new team name")
        opponent_new_team_layout.addWidget(self.ui.lineEditNewOpponent)
        self.ui.pushButtonAddOpponent = QPushButton("Add New Team")
        opponent_new_team_layout.addWidget(self.ui.pushButtonAddOpponent)
        main_layout.addLayout(opponent_new_team_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        
        self.ui.pushButtonCancel = QPushButton("Cancel")
        button_layout.addWidget(self.ui.pushButtonCancel)
        
        self.ui.pushButtonSave = QPushButton("Save")
        button_layout.addWidget(self.ui.pushButtonSave)
        
        main_layout.addLayout(button_layout)
        
        # Connect signals
        self.ui.pushButtonSave.clicked.connect(self.save_config)
        self.ui.pushButtonCancel.clicked.connect(self.reject)
        self.ui.pushButtonAddOurTeam.clicked.connect(lambda: self.add_new_team("our"))
        self.ui.pushButtonAddOpponent.clicked.connect(lambda: self.add_new_team("opponent"))
        
        # Populate dropdowns with existing teams
        self.populate_team_dropdowns()
        
        # Set focus to first dropdown
        self.ui.comboBoxOurTeam.setFocus()
    
    def populate_team_dropdowns(self):
        """Populate the team dropdowns with existing teams from the database."""
        try:
            if not self.db.conn:
                self.db.connect()
            
            teams = self.db.teams.get_all_teams()
            
            # Clear and populate both dropdowns
            self.ui.comboBoxOurTeam.clear()
            self.ui.comboBoxOpponent.clear()
            
            # Add teams to both dropdowns
            for team in teams:
                self.ui.comboBoxOurTeam.addItem(team['name'], team['team_id'])
                self.ui.comboBoxOpponent.addItem(team['name'], team['team_id'])
            
        except Exception as e:
            QMessageBox.warning(self, "Warning", 
                              f"Could not load existing teams:\n{str(e)}")
    
    def add_new_team(self, team_type: str):
        """Add a new team to the database and update the dropdowns.
        
        Args:
            team_type: "our" or "opponent"
        """
        if team_type == "our":
            new_team_name = self.ui.lineEditNewOurTeam.text().strip()
        else:
            new_team_name = self.ui.lineEditNewOpponent.text().strip()
        
        if not new_team_name:
            QMessageBox.warning(self, "Validation Error", 
                              "Please enter a team name.")
            return
        
        try:
            if not self.db.conn:
                self.db.connect()
            
            # Add team to database
            team_id = self.db.teams.add_team(new_team_name)
            
            # Add to both dropdowns
            self.ui.comboBoxOurTeam.addItem(new_team_name, team_id)
            self.ui.comboBoxOpponent.addItem(new_team_name, team_id)
            
            # Select the newly added team in the appropriate dropdown
            if team_type == "our":
                index = self.ui.comboBoxOurTeam.findData(team_id)
                if index >= 0:
                    self.ui.comboBoxOurTeam.setCurrentIndex(index)
                self.ui.lineEditNewOurTeam.clear()
            else:
                index = self.ui.comboBoxOpponent.findData(team_id)
                if index >= 0:
                    self.ui.comboBoxOpponent.setCurrentIndex(index)
                self.ui.lineEditNewOpponent.clear()
            
            QMessageBox.information(self, "Success", 
                                  f"Team '{new_team_name}' added successfully!")
            
        except Exception as e:
            QMessageBox.critical(self, "Database Error", 
                               f"Failed to add team:\n{str(e)}")
    
    def save_config(self):
        """Save team configuration to database."""
        # Get selected team IDs from dropdowns
        our_team_id = self.ui.comboBoxOurTeam.currentData()
        opponent_team_id = self.ui.comboBoxOpponent.currentData()
        
        # If user typed a new name in the editable combo box, create it
        our_team_name = self.ui.comboBoxOurTeam.currentText().strip()
        opponent_team_name = self.ui.comboBoxOpponent.currentText().strip()
        
        # Validate input
        if not our_team_name:
            QMessageBox.warning(self, "Validation Error", 
                              "Please select or enter a name for our team.")
            self.ui.comboBoxOurTeam.setFocus()
            return
        
        if not opponent_team_name:
            QMessageBox.warning(self, "Validation Error", 
                              "Please select or enter a name for the opponent team.")
            self.ui.comboBoxOpponent.setFocus()
            return
        
        # Check if teams are different
        if our_team_id and opponent_team_id and our_team_id == opponent_team_id:
            QMessageBox.warning(self, "Validation Error", 
                              "Our team and opponent team must be different!")
            return
        
        try:
            # Connect to database
            if not self.db.conn:
                self.db.connect()
            
            # If team_id is None, it means user typed a new team name
            if our_team_id is None:
                self.team_us_id = self.db.teams.add_team(our_team_name)
            else:
                self.team_us_id = our_team_id
            
            if opponent_team_id is None:
                self.team_them_id = self.db.teams.add_team(opponent_team_name)
            else:
                self.team_them_id = opponent_team_id
            
            # Check again after potentially creating new teams
            if self.team_us_id == self.team_them_id:
                QMessageBox.warning(self, "Validation Error", 
                                  "Our team and opponent team must be different!")
                return
            
            # Start a new game
            self.game_id = self.db.games.start_game(
                team_us_id=self.team_us_id,
                team_them_id=self.team_them_id,
                notes=None
            )
            
            # Close database connection
            self.db.close()
            
            # Accept dialog
            QMessageBox.information(self, "Success", 
                                   f"Game configured successfully!\n\n"
                                   f"Our Team: {our_team_name}\n"
                                   f"Opponent: {opponent_team_name}\n"
                                   f"Game ID: {self.game_id}")
            self.accept()
            
        except Exception as e:
            if self.db.conn:
                self.db.close()
            QMessageBox.critical(self, "Database Error", 
                               f"Failed to save configuration:\n{str(e)}")
    
    def get_team_ids(self):
        """Get the team IDs after configuration."""
        return self.team_us_id, self.team_them_id
    
    def get_game_id(self):
        """Get the game ID after configuration."""
        return self.game_id


if __name__ == "__main__":
    # Test the config screen
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    db = VideoStatsDB()
    db.initialize_database()
    
    dialog = ConfigScreen(db=db)
    if dialog.exec() == QDialog.Accepted:
        team_us_id, team_them_id = dialog.get_team_ids()
        game_id = dialog.get_game_id()
        print(f"Team US ID: {team_us_id}")
        print(f"Team Them ID: {team_them_id}")
        print(f"Game ID: {game_id}")
    
    db.close()
    sys.exit(0)


