"""
Dialog for creating a new team with roster.
Allows entering team name and adding players with jersey, name, and position/role.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QMessageBox, QComboBox, QHeaderView
)
from PySide6.QtCore import Qt
from database import VideoStatsDB
from typing import Optional


class CreateTeamDialog(QDialog):
    """Dialog for creating a new team with roster."""
    
    def __init__(self, db: VideoStatsDB, parent=None):
        super().__init__(parent)
        self.db = db
        self.team_id = None
        self.team_name = ""
        self.player_count = 0
        
        self.setWindowTitle("Create New Team")
        self.setGeometry(100, 100, 700, 600)
        
        layout = QVBoxLayout(self)
        
        # Team name section
        team_layout = QHBoxLayout()
        team_layout.addWidget(QLabel("Team Name:"))
        self.team_name_input = QLineEdit()
        self.team_name_input.setPlaceholderText("Enter team name")
        team_layout.addWidget(self.team_name_input)
        layout.addLayout(team_layout)
        
        # Roster section
        roster_label = QLabel("Roster:")
        layout.addWidget(roster_label)
        
        # Table for roster
        self.roster_table = QTableWidget()
        self.roster_table.setColumnCount(3)
        self.roster_table.setHorizontalHeaderLabels(["Jersey", "Name", "Position/Role"])
        self.roster_table.horizontalHeader().setStretchLastSection(True)
        self.roster_table.setAlternatingRowColors(True)
        layout.addWidget(self.roster_table)
        
        # Buttons for roster management
        roster_buttons = QHBoxLayout()
        self.btn_add_player = QPushButton("Add Player")
        self.btn_add_player.clicked.connect(self.add_player_row)
        self.btn_remove_player = QPushButton("Remove Selected")
        self.btn_remove_player.clicked.connect(self.remove_player_row)
        roster_buttons.addWidget(self.btn_add_player)
        roster_buttons.addWidget(self.btn_remove_player)
        roster_buttons.addStretch()
        layout.addLayout(roster_buttons)
        
        # Role codes dropdown options
        self.role_codes = ['S', 'RS', 'RH', 'MH', 'OH', 'Lib', 'DS']
        
        # Dialog buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_save = QPushButton("Save Team")
        self.btn_save.clicked.connect(self.save_team)
        button_layout.addWidget(self.btn_cancel)
        button_layout.addWidget(self.btn_save)
        layout.addLayout(button_layout)
        
        # Add initial empty row
        self.add_player_row()
    
    def add_player_row(self):
        """Add a new row to the roster table."""
        row = self.roster_table.rowCount()
        self.roster_table.insertRow(row)
        
        # Jersey number
        jersey_item = QTableWidgetItem()
        jersey_item.setTextAlignment(Qt.AlignCenter)
        self.roster_table.setItem(row, 0, jersey_item)
        
        # Name
        name_item = QTableWidgetItem()
        self.roster_table.setItem(row, 1, name_item)
        
        # Position/Role combo box
        role_combo = QComboBox()
        role_combo.addItems([''] + self.role_codes)
        role_combo.setEditable(True)
        self.roster_table.setCellWidget(row, 2, role_combo)
    
    def remove_player_row(self):
        """Remove selected row(s) from roster table."""
        current_row = self.roster_table.currentRow()
        if current_row >= 0:
            self.roster_table.removeRow(current_row)
        else:
            QMessageBox.information(self, "No Selection", "Please select a row to remove.")
    
    def save_team(self):
        """Save the team and roster to database."""
        # Validate team name
        team_name = self.team_name_input.text().strip()
        if not team_name:
            QMessageBox.warning(self, "Validation Error", "Please enter a team name.")
            return
        
        # Validate roster
        players = []
        for row in range(self.roster_table.rowCount()):
            jersey_item = self.roster_table.item(row, 0)
            name_item = self.roster_table.item(row, 1)
            role_widget = self.roster_table.cellWidget(row, 2)
            
            jersey = jersey_item.text().strip() if jersey_item else ""
            name = name_item.text().strip() if name_item else ""
            role = role_widget.currentText().strip() if role_widget else ""
            
            if jersey or name:  # At least one field filled
                if not jersey:
                    QMessageBox.warning(
                        self,
                        "Validation Error",
                        f"Player at row {row + 1} is missing a jersey number."
                    )
                    return
                players.append((jersey, name, role))
        
        if not players:
            QMessageBox.warning(self, "Validation Error", "Please add at least one player to the roster.")
            return
        
        try:
            # Create team
            self.team_id = self.db.add_team(team_name)
            
            # Add players
            for jersey, name, role in players:
                player_id = self.db.add_player(self.team_id, jersey, name if name else None)
                
                # Set role_code and jersey if provided
                if role or jersey:
                    cursor = self.db.conn.cursor()
                    updates = []
                    params = []
                    
                    if role:
                        updates.append("role_code = %s")
                        params.append(role)
                    
                    # Try to convert jersey to integer for jersey column
                    try:
                        jersey_int = int(jersey)
                        updates.append("jersey = %s")
                        params.append(jersey_int)
                    except ValueError:
                        pass  # Keep jersey as text in player_number
                    
                    if updates:
                        params.append(player_id)
                        cursor.execute(
                            f"UPDATE players SET {', '.join(updates)} WHERE player_id = %s",
                            params
                        )
            
            self.db.conn.commit()
            
            self.team_name = team_name
            self.player_count = len(players)
            self.accept()
            
        except Exception as e:
            self.db.conn.rollback()
            QMessageBox.critical(
                self,
                "Database Error",
                f"Failed to save team:\n{str(e)}"
            )


