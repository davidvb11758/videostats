"""
Main menu screen for VideoStats application.
This is the opening screen that allows users to:
1. Create a new team
2. Edit an existing team
3. Create a new game
4. View ball paths for a selected game
5. Resume data entry for a selected game
6. View reports
7. Edit game setup
8. Refresh statistics
9. End game
10. Close application
"""

import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QMessageBox, QDialog
)
from PySide6.QtCore import Qt
from database import VideoStatsDB
from create_team_dialog import CreateTeamDialog
from edit_team_dialog import EditTeamDialog
from create_game_dialog import CreateGameDialog
from stats_app import StatsApp
from view_paths import ContactPathViewer
from data_entry import DataEntryWindow
from PySide6.QtUiTools import QUiLoader


class RocketsVideoStatsWindow(QMainWindow):
    """Main menu window for VideoStats application using PySide6 Designer UI."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = VideoStatsDB()
        self.db.initialize_database()
        self.db.connect()
        
        # Load UI file
        ui_file = Path(__file__).parent / "RocketsVideoStats.ui"
        if not ui_file.exists():
            QMessageBox.critical(
                None,
                "UI File Not Found",
                f"UI file not found: {ui_file}\n"
                "Please ensure RocketsVideoStats.ui exists in the same directory."
            )
            return
        
        loader = QUiLoader()
        ui_widget = loader.load(str(ui_file))
        
        if not ui_widget:
            QMessageBox.critical(
                None,
                "UI Load Error",
                "Failed to load RocketsVideoStats UI file."
            )
            return
        
        # Copy properties from loaded UI
        self.setWindowTitle(ui_widget.windowTitle() if hasattr(ui_widget, 'windowTitle') else "Rockets VideoStats")
        self.setGeometry(ui_widget.geometry())
        
        # Set central widget and other components
        self.setCentralWidget(ui_widget.centralwidget)
        if hasattr(ui_widget, 'menubar'):
            self.setMenuBar(ui_widget.menubar)
        if hasattr(ui_widget, 'statusbar'):
            self.setStatusBar(ui_widget.statusbar)
        
        # Store reference to UI widgets
        self.ui = ui_widget
        
        # Track selected game
        self.selected_game_id = None
        
        # Populate game combo box
        self.populate_game_combo()
        
        # Connect signals
        self.connect_signals()
    
    def connect_signals(self):
        """Connect UI signals to methods."""
        # Existing buttons that work as-is
        if hasattr(self.ui, 'btn_create_team'):
            self.ui.btn_create_team.clicked.connect(self.create_new_team)
        
        if hasattr(self.ui, 'btn_edit_team'):
            self.ui.btn_edit_team.clicked.connect(self.edit_existing_team)
        
        if hasattr(self.ui, 'btn_create_game'):
            self.ui.btn_create_game.clicked.connect(self.create_new_game)
        
        if hasattr(self.ui, 'btn_view_reports'):
            self.ui.btn_view_reports.clicked.connect(self.view_reports)
        
        # Modified buttons that need game_id
        if hasattr(self.ui, 'btn_view_paths'):
            self.ui.btn_view_paths.clicked.connect(self.view_ball_paths)
        
        if hasattr(self.ui, 'btn_resume_game'):
            self.ui.btn_resume_game.clicked.connect(self.resume_data_entry)
        
        # New buttons (stubs)
        if hasattr(self.ui, 'btn_edit_game_setup'):
            self.ui.btn_edit_game_setup.clicked.connect(self.edit_game_setup)
        
        if hasattr(self.ui, 'btn_refresh_statistics'):
            self.ui.btn_refresh_statistics.clicked.connect(self.refresh_statistics)
        
        if hasattr(self.ui, 'btn_end_game'):
            self.ui.btn_end_game.clicked.connect(self.end_game)
        
        if hasattr(self.ui, 'btn_close_app'):
            self.ui.btn_close_app.clicked.connect(self.close_app)
        
        # Game selection combo box
        if hasattr(self.ui, 'combo_select_game'):
            self.ui.combo_select_game.currentIndexChanged.connect(self.on_game_selected)
    
    def populate_game_combo(self):
        """Populate the game selection combo box with all games from the database."""
        if not hasattr(self.ui, 'combo_select_game'):
            return
        
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
        
        combo = self.ui.combo_select_game
        combo.clear()
        
        # Add "Select a game" as first item
        combo.addItem("Select a game")
        combo.setItemData(0, None, Qt.UserRole)
        
        for game in games:
            game_id, game_date, team_us_name, team_them_name, team_us_id, team_them_id = game
            display_text = f"Game {game_id}: {team_us_name} vs {team_them_name} ({game_date})"
            combo.addItem(display_text)
            # Store game data
            index = combo.count() - 1
            combo.setItemData(index, {
                'game_id': game_id,
                'team_us_id': team_us_id,
                'team_them_id': team_them_id,
                'team_us_name': team_us_name,
                'team_them_name': team_them_name
            }, Qt.UserRole)
    
    def on_game_selected(self, index: int):
        """Handle game selection from combo box."""
        if index < 0:
            self.selected_game_id = None
            return
        
        if hasattr(self.ui, 'combo_select_game'):
            item_data = self.ui.combo_select_game.itemData(index, Qt.UserRole)
            if item_data:
                self.selected_game_id = item_data['game_id']
            else:
                self.selected_game_id = None
    
    def get_selected_game_id(self):
        """Get the currently selected game_id, or None if no game selected."""
        return self.selected_game_id
    
    def create_new_team(self):
        """Open dialog to create a new team with roster."""
        dialog = CreateTeamDialog(self.db, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.update_status_label(f"Team '{dialog.team_name}' created successfully!")
            QMessageBox.information(
                self,
                "Team Created",
                f"Team '{dialog.team_name}' has been created with {dialog.player_count} players."
            )
    
    def edit_existing_team(self):
        """Open dialog to edit an existing team."""
        dialog = EditTeamDialog(self.db, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.update_status_label(f"Team '{dialog.team_name}' updated successfully!")
    
    def create_new_game(self):
        """Open dialog to create a new game."""
        dialog = CreateGameDialog(self.db, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.update_status_label(f"Game created successfully!")
            QMessageBox.information(
                self,
                "Game Created",
                f"Game ID: {dialog.game_id}\n"
                f"Team Us: {dialog.team_us_name}\n"
                f"Team Them: {dialog.team_them_name}"
            )
            # Refresh game combo box and auto-select newly created game
            self.populate_game_combo()
            # Find and select the newly created game
            if hasattr(self.ui, 'combo_select_game'):
                combo = self.ui.combo_select_game
                for i in range(combo.count()):
                    item_data = combo.itemData(i, Qt.UserRole)
                    if item_data and item_data.get('game_id') == dialog.game_id:
                        combo.setCurrentIndex(i)
                        break
    
    def update_status_label(self, text):
        """Update status label if it exists in the UI."""
        if hasattr(self.ui, 'status_label'):
            self.ui.status_label.setText(text)
    
    def view_ball_paths(self):
        """Open the ball paths viewer window with selected game."""
        game_id = self.get_selected_game_id()
        
        if not game_id:
            QMessageBox.warning(
                self,
                "No Game Selected",
                "Please select a game from the dropdown before viewing ball paths."
            )
            return
        
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
            
            # Create and show contact path viewer window with game_id
            path_viewer = ContactPathViewer(ui_widget=ui_widget, db=self.db, game_id=game_id)
            path_viewer.show()
            path_viewer.raise_()
            path_viewer.activateWindow()
            
            self.update_status_label(f"Ball paths viewer opened for Game {game_id}")
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to open ball paths viewer:\n{str(e)}"
            )
            self.update_status_label(f"Error opening ball paths viewer: {str(e)}")
    
    def resume_data_entry(self):
        """Open data entry window for the selected game."""
        game_id = self.get_selected_game_id()
        
        if not game_id:
            QMessageBox.warning(
                self,
                "No Game Selected",
                "Please select a game from the dropdown before resuming data entry."
            )
            return
        
        # Query database for game data using game_id
        if not self.db.conn:
            self.db.connect()
        
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT g.game_id, g.game_date, 
                   t1.name as team_us_name, t2.name as team_them_name,
                   g.team_us_id, g.team_them_id, g.notes
            FROM games g
            JOIN teams t1 ON g.team_us_id = t1.team_id
            JOIN teams t2 ON g.team_them_id = t2.team_id
            WHERE g.game_id = ?
        """, (game_id,))
        
        result = cursor.fetchone()
        
        if not result:
            QMessageBox.warning(
                self,
                "Game Not Found",
                f"Game {game_id} not found in database."
            )
            return
        
        game_id_db, game_date, team_us_name, team_them_name, team_us_id, team_them_id, notes = result
        
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
            team_us_id=team_us_id,
            team_them_id=team_them_id,
            game_id=game_id,
            lock_game_selection=False  # Allow user to change game if needed when resuming
        )
        
        data_entry_window.show()
        data_entry_window.raise_()
        data_entry_window.activateWindow()
        # Hide main menu when data entry window is opened
        self.hide()
        
        self.update_status_label(f"Opened Game {game_id} for data entry")
    
    def view_reports(self):
        """Open reports dialog."""
        # Open the statistics reports window
        stats_window = StatsApp(self.db, parent=self)
        stats_window.show()
        stats_window.raise_()
        stats_window.activateWindow()
    
    def edit_game_setup(self):
        """Edit game setup - placeholder method."""
        QMessageBox.information(
            self,
            "Not Implemented",
            "Edit Game Setup - Not yet implemented"
        )
    
    def refresh_statistics(self):
        """Refresh statistics - placeholder method."""
        QMessageBox.information(
            self,
            "Not Implemented",
            "Refresh Statistics - Not yet implemented"
        )
    
    def end_game(self):
        """End game - placeholder method."""
        QMessageBox.information(
            self,
            "Not Implemented",
            "End Game - Not yet implemented"
        )
    
    def close_app(self):
        """Close the application."""
        if self.db.conn:
            self.db.close()
        QApplication.instance().quit()
    
    def closeEvent(self, event):
        """Handle window close event."""
        if self.db.conn:
            self.db.close()
        event.accept()


def main():
    """Main entry point for VideoStats application."""
    app = QApplication(sys.argv)
    
    window = RocketsVideoStatsWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

