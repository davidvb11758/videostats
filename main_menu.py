"""
Main menu screen for VideoStats application.
This is the opening screen that allows users to:
1. Create a new team
2. Edit an existing team
3. Create a new game
4. Resume data entry for an existing game
5. View reports
"""

import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QMessageBox, QListWidget, QListWidgetItem, QDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from database import VideoStatsDB
from create_team_dialog import CreateTeamDialog
from edit_team_dialog import EditTeamDialog
from create_game_dialog import CreateGameDialog
from view_reports_dialog import ViewReportsDialog
from stats_app import StatsApp
from view_paths import ContactPathViewer
from data_entry import DataEntryWindow
from PySide6.QtUiTools import QUiLoader


class MainMenuWindow(QMainWindow):
    """Main menu window for VideoStats application."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = VideoStatsDB()
        self.db.initialize_database()
        self.db.connect()
        
        self.setWindowTitle("VideoStats - Main Menu")
        self.setGeometry(100, 100, 800, 600)
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(30, 30, 30, 30)
        
        # Title
        title_label = QLabel("VideoStats - Volleyball Statistics")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        # Add some spacing
        main_layout.addSpacing(20)
        
        # Button layout
        button_layout = QVBoxLayout()
        button_layout.setSpacing(15)
        
        # Create New Team button
        self.btn_create_team = QPushButton("1. Create New Team")
        self.btn_create_team.setMinimumHeight(50)
        self.btn_create_team.clicked.connect(self.create_new_team)
        button_layout.addWidget(self.btn_create_team)
        
        # Edit Existing Team button
        self.btn_edit_team = QPushButton("2. Edit Existing Team")
        self.btn_edit_team.setMinimumHeight(50)
        self.btn_edit_team.clicked.connect(self.edit_existing_team)
        button_layout.addWidget(self.btn_edit_team)
        
        # Create New Game button
        self.btn_create_game = QPushButton("3. Create New Game")
        self.btn_create_game.setMinimumHeight(50)
        self.btn_create_game.clicked.connect(self.create_new_game)
        button_layout.addWidget(self.btn_create_game)
        
        # View Ball Paths button
        self.btn_view_paths = QPushButton("4. View Ball Paths")
        self.btn_view_paths.setMinimumHeight(50)
        self.btn_view_paths.clicked.connect(self.view_ball_paths)
        button_layout.addWidget(self.btn_view_paths)
        
        # Resume Data Entry button
        self.btn_resume_game = QPushButton("5. Resume Data Entry for Existing Game")
        self.btn_resume_game.setMinimumHeight(50)
        self.btn_resume_game.clicked.connect(self.resume_data_entry)
        button_layout.addWidget(self.btn_resume_game)
        
        # View Reports button
        self.btn_view_reports = QPushButton("6. View Reports")
        self.btn_view_reports.setMinimumHeight(50)
        self.btn_view_reports.clicked.connect(self.view_reports)
        button_layout.addWidget(self.btn_view_reports)
        
        # Delete Game button
        self.btn_delete_game = QPushButton("7. Delete Game")
        self.btn_delete_game.setMinimumHeight(50)
        self.btn_delete_game.clicked.connect(self.delete_game)
        button_layout.addWidget(self.btn_delete_game)
        
        main_layout.addLayout(button_layout)
        
        # Add stretch to push buttons to top
        main_layout.addStretch()
        
        # Status label
        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.status_label)
    
    def create_new_team(self):
        """Open dialog to create a new team with roster."""
        dialog = CreateTeamDialog(self.db, parent=self)
        if dialog.exec() == QDialog.Accepted:
            self.status_label.setText(f"Team '{dialog.team_name}' created successfully!")
            QMessageBox.information(
                self,
                "Team Created",
                f"Team '{dialog.team_name}' has been created with {dialog.player_count} players."
            )
    
    def edit_existing_team(self):
        """Open dialog to edit an existing team."""
        dialog = EditTeamDialog(self.db, parent=self)
        if dialog.exec() == QDialog.Accepted:
            self.status_label.setText(f"Team '{dialog.team_name}' updated successfully!")
    
    def create_new_game(self):
        """Open dialog to create a new game."""
        dialog = CreateGameDialog(self.db, parent=self)
        if dialog.exec() == QDialog.Accepted:
            self.status_label.setText(f"Game created successfully!")
            QMessageBox.information(
                self,
                "Game Created",
                f"Game ID: {dialog.game_id}\n"
                f"Team Us: {dialog.team_us_name}\n"
                f"Team Them: {dialog.team_them_name}"
            )
    
    def view_ball_paths(self):
        """Open the ball paths viewer window."""
        try:
            # Load UI file
            ui_file = Path(__file__).parent / "viewpaths.ui"
            if not ui_file.exists():
                QMessageBox.critical(
                    self,
                    "UI File Not Found",
                    f"UI file not found: {ui_file}\n"
                    "Please ensure viewpaths.ui exists in the same directory."
                )
                return
            
            loader = QUiLoader()
            ui_widget = loader.load(str(ui_file))
            
            if not ui_widget:
                QMessageBox.critical(
                    self,
                    "UI Load Error",
                    "Failed to load view paths UI file."
                )
                return
            
            # Create and show contact path viewer window
            path_viewer = ContactPathViewer(ui_widget=ui_widget, db=self.db)
            path_viewer.show()
            path_viewer.raise_()
            path_viewer.activateWindow()
            
            self.status_label.setText("Ball paths viewer opened")
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to open ball paths viewer:\n{str(e)}"
            )
            self.status_label.setText(f"Error opening ball paths viewer: {str(e)}")
    
    def resume_data_entry(self):
        """Open data entry window for an existing game."""
        # Get list of games
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT g.game_id, g.game_date, 
                   t1.name as team_us_name, t2.name as team_them_name,
                   g.team_us_id, g.team_them_id, g.notes
            FROM games g
            JOIN teams t1 ON g.team_us_id = t1.team_id
            JOIN teams t2 ON g.team_them_id = t2.team_id
            ORDER BY g.game_date DESC, g.game_id DESC
        """)
        games = cursor.fetchall()
        
        if not games:
            QMessageBox.information(
                self,
                "No Games",
                "No games found. Please create a game first."
            )
            return
        
        # Show game selection dialog
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QPushButton, QLabel
        
        game_dialog = QDialog(self)
        game_dialog.setWindowTitle("Select Game")
        game_dialog.setGeometry(200, 200, 500, 400)
        
        layout = QVBoxLayout(game_dialog)
        
        label = QLabel("Select a game to resume:")
        layout.addWidget(label)
        
        game_list = QListWidget()
        for game in games:
            game_id, game_date, team_us, team_them, team_us_id, team_them_id, notes = game
            date_str = game_date if game_date else "Unknown date"
            
            # Extract opponent alias from notes field
            # Notes format is "Opponent: {alias}" or just the alias
            opponent_display = team_them  # Default to team name
            if notes:
                # Check if notes contains "Opponent: " prefix
                if notes.startswith("Opponent: "):
                    opponent_display = notes.replace("Opponent: ", "").strip()
                else:
                    opponent_display = notes.strip()
            
            item_text = f"Game {game_id} - {date_str}\n  {team_us} vs {opponent_display}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, {
                'game_id': game_id,
                'team_us_id': team_us_id,
                'team_them_id': team_them_id,
                'team_us_name': team_us,
                'team_them_name': team_them
            })
            game_list.addItem(item)
        
        layout.addWidget(game_list)
        
        button_layout = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(game_dialog.reject)
        btn_ok = QPushButton("Open")
        btn_ok.clicked.connect(game_dialog.accept)
        button_layout.addWidget(btn_cancel)
        button_layout.addWidget(btn_ok)
        layout.addLayout(button_layout)
        
        if game_dialog.exec() != QDialog.Accepted:
            return
        
        selected_item = game_list.currentItem()
        if not selected_item:
            return
        
        game_data = selected_item.data(Qt.UserRole)
        
        # Load data entry UI
        ui_file = Path(__file__).parent / "inputTouchesVoice.ui"
        if not ui_file.exists():
            QMessageBox.critical(
                self,
                "Error",
                f"UI file not found: {ui_file}\n"
                "Please ensure inputTouchesVoice.ui exists in the same directory."
            )
            return
        
        loader = QUiLoader()
        ui_widget = loader.load(str(ui_file))
        
        if not ui_widget:
            QMessageBox.critical(
                self,
                "Error",
                "Failed to load data entry UI file."
            )
            return
        
        # Create and show data entry window
        data_entry_window = DataEntryWindow(
            ui_widget=ui_widget,
            db=self.db,
            team_us_id=game_data['team_us_id'],
            team_them_id=game_data['team_them_id'],
            game_id=game_data['game_id'],
            lock_game_selection=False  # Allow user to change game if needed when resuming
        )
        
        data_entry_window.show()
        data_entry_window.raise_()
        data_entry_window.activateWindow()
        # Hide main menu when data entry window is opened
        self.hide()
        self.status_label.setText(f"Opened Game {game_data['game_id']} for data entry")
    
    def view_reports(self):
        """Open reports dialog."""
        # Open the statistics reports window
        stats_window = StatsApp(self.db, parent=self)
        stats_window.show()
        stats_window.raise_()
        stats_window.activateWindow()
    
    def delete_game(self):
        """Delete a game and all related data."""
        # Get list of games
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT g.game_id, g.game_date, 
                   t1.name as team_us_name, t2.name as team_them_name,
                   g.team_us_id, g.team_them_id, g.notes
            FROM games g
            JOIN teams t1 ON g.team_us_id = t1.team_id
            JOIN teams t2 ON g.team_them_id = t2.team_id
            ORDER BY g.game_date DESC, g.game_id DESC
        """)
        games = cursor.fetchall()
        
        if not games:
            QMessageBox.information(
                self,
                "No Games",
                "No games found to delete."
            )
            return
        
        # Show game selection dialog
        game_dialog = QDialog(self)
        game_dialog.setWindowTitle("Delete Game")
        game_dialog.setGeometry(200, 200, 500, 400)
        
        layout = QVBoxLayout(game_dialog)
        
        label = QLabel("Select a game to delete:")
        layout.addWidget(label)
        
        game_list = QListWidget()
        for game in games:
            game_id, game_date, team_us, team_them, team_us_id, team_them_id, notes = game
            date_str = game_date if game_date else "Unknown date"
            
            # Extract opponent alias from notes field
            # Notes format is "Opponent: {alias}" or just the alias
            opponent_display = team_them  # Default to team name
            if notes:
                # Check if notes contains "Opponent: " prefix
                if notes.startswith("Opponent: "):
                    opponent_display = notes.replace("Opponent: ", "").strip()
                else:
                    opponent_display = notes.strip()
            
            item_text = f"Game {game_id} - {date_str}\n  {team_us} vs {opponent_display}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, {
                'game_id': game_id,
                'team_us_id': team_us_id,
                'team_them_id': team_them_id,
                'team_us_name': team_us,
                'team_them_name': team_them,
                'opponent_display': opponent_display,
                'game_date': date_str
            })
            game_list.addItem(item)
        
        layout.addWidget(game_list)
        
        button_layout = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(game_dialog.reject)
        btn_delete = QPushButton("Delete")
        btn_delete.clicked.connect(game_dialog.accept)
        button_layout.addWidget(btn_cancel)
        button_layout.addWidget(btn_delete)
        layout.addLayout(button_layout)
        
        if game_dialog.exec() != QDialog.Accepted:
            return
        
        selected_item = game_list.currentItem()
        if not selected_item:
            return
        
        game_data = selected_item.data(Qt.UserRole)
        game_id = game_data['game_id']
        
        # Confirm deletion
        opponent_display = game_data.get('opponent_display', game_data['team_them_name'])
        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete Game {game_id}?\n\n"
            f"Team Us: {game_data['team_us_name']}\n"
            f"Opponent: {opponent_display}\n"
            f"Date: {game_data['game_date']}\n\n"
            "This will delete ALL related data including:\n"
            "- All contacts\n"
            "- All rallies\n"
            "- All game players\n"
            "- All player statistics\n"
            "- All substitutions\n"
            "- All libero actions\n"
            "- Rotation state for both teams\n\n"
            "This action CANNOT be undone!",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # Perform deletion
        try:
            deleted_counts = self.db.delete_game(game_id)
            
            # Show success message with details
            summary = (
                f"Game {game_id} deleted successfully!\n\n"
                f"Deleted:\n"
                f"- {deleted_counts['contacts']} contacts\n"
                f"- {deleted_counts['rallies']} rallies\n"
                f"- {deleted_counts['game_players']} game players\n"
                f"- {deleted_counts['player_stats']} player statistics\n"
                f"- {deleted_counts['substitutions']} substitutions\n"
                f"- {deleted_counts['libero_actions']} libero actions\n"
                f"- {deleted_counts.get('active_lineup', 0)} active lineup records\n"
                f"- {deleted_counts['rotation_state']} rotation state records\n"
                f"- {deleted_counts['game']} game record"
            )
            
            QMessageBox.information(
                self,
                "Game Deleted",
                summary
            )
            
            self.status_label.setText(f"Game {game_id} deleted successfully")
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Deletion Failed",
                f"Failed to delete game {game_id}:\n{str(e)}"
            )
            self.status_label.setText(f"Failed to delete game {game_id}")
    
    def closeEvent(self, event):
        """Handle window close event."""
        if self.db.conn:
            self.db.close()
        event.accept()


def main():
    """Main entry point for VideoStats application."""
    app = QApplication(sys.argv)
    
    window = MainMenuWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

