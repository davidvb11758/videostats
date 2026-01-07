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
from datetime import datetime
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
from list_games_dialog import ListGamesDialog
from reprocess_outcomes import assign_rally_outcomes
from stats_calc import StatsCalculator
from PySide6.QtUiTools import QUiLoader
from utils import resource_path, initialize_app


class RocketsVideoStatsWindow(QMainWindow):
    """Main menu window for VideoStats application using PySide6 Designer UI."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = VideoStatsDB()
        self.db.initialize_database()
        self.db.connect()
        
        # Load UI file
        ui_file = resource_path("RocketsVideoStats.ui")
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
        
        # Track data entry window reference
        self.data_entry_window = None
        
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
        
        if hasattr(self.ui, 'btn_debug_replay'):
            self.ui.btn_debug_replay.clicked.connect(self.debug_replay_contacts)
        
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
        
        # List All Games button
        if hasattr(self.ui, 'pushButton_2'):
            self.ui.pushButton_2.clicked.connect(self.list_all_games)
        
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
                   g.team_us_id, g.team_them_id, g.notes
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
            game_id, game_date, team_us_name, team_them_name, team_us_id, team_them_id, notes = game
            
            # Format game date to show only the date (YYYY-MM-DD)
            date_display = game_date
            if game_date:
                try:
                    # Try parsing ISO format
                    if isinstance(game_date, str):
                        if 'T' in game_date:
                            date_obj = datetime.fromisoformat(game_date.replace(' ', 'T'))
                        else:
                            # Try parsing space-separated format
                            date_obj = datetime.strptime(game_date, '%Y-%m-%d %H:%M:%S')
                    else:
                        # Already a datetime object
                        date_obj = game_date
                    date_display = date_obj.strftime('%Y-%m-%d')
                except:
                    # If parsing fails, try to extract just the date part
                    if isinstance(game_date, str):
                        date_display = game_date[:10] if len(game_date) >= 10 else game_date
                    else:
                        date_display = str(game_date)
            
            # Extract opponent alias from notes field
            opponent_display = team_them_name  # Default to team name
            if notes:
                # Check if notes contains "Opponent: " prefix
                if notes.startswith("Opponent: "):
                    opponent_display = notes.replace("Opponent: ", "").strip()
                else:
                    # If notes doesn't start with "Opponent: ", use it as-is if it's not empty
                    opponent_display = notes.strip() if notes.strip() else team_them_name
            
            display_text = f"Game {game_id}: {team_us_name} vs {opponent_display} ({date_display})"
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
            ui_file = resource_path("viewpaths.ui")
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
    
    def debug_replay_contacts(self):
        """Open the debug replay contacts window for the selected game."""
        game_id = self.get_selected_game_id()
        
        if not game_id:
            QMessageBox.warning(
                self,
                "No Game Selected",
                "Please select a game from the dropdown before opening debug replay."
            )
            return
        
        try:
            from debug_replay_contacts import DebugReplayContactsWindow
            
            debug_window = DebugReplayContactsWindow(db=self.db, game_id=game_id)
            # Store reference to prevent garbage collection
            if not hasattr(self, '_debug_windows'):
                self._debug_windows = []
            self._debug_windows.append(debug_window)
            
            debug_window.show()
            debug_window.raise_()
            debug_window.activateWindow()
            
            self.update_status_label(f"Debug replay contacts opened for Game {game_id}")
            
        except Exception as e:
            import traceback
            error_msg = f"Failed to open debug replay contacts:\n{str(e)}\n\n{traceback.format_exc()}"
            QMessageBox.critical(
                self,
                "Error",
                error_msg
            )
            self.update_status_label(f"Error opening debug replay contacts: {str(e)}")
    
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
        
        # Check if game is ended
        if self.db.is_game_ended(game_id):
            QMessageBox.warning(
                self,
                "Game Ended",
                f"This game has been ended. You cannot resume data entry for ended games."
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
        ui_file = resource_path("inputTouchesVoice.ui")
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
        
        # Create data entry window (but don't show it)
        # The coordinate mapper will be created and shown automatically
        data_entry_window = DataEntryWindow(
            ui_widget=ui_widget,
            db=self.db,
            team_us_id=team_us_id,
            team_them_id=team_them_id,
            game_id=game_id,
            lock_game_selection=False  # Allow user to change game if needed when resuming
        )
        
        # Store reference to data entry window
        self.data_entry_window = data_entry_window
        
        # Don't show the data entry window - only coordinate mapper will be visible
        # Ensure coordinate mapper is visible and active
        if data_entry_window.coordinate_mapper:
            # Connect to coordinate mapper's close signal to show main menu
            data_entry_window.coordinate_mapper.window_closing.connect(self.on_coordinate_mapper_closing)
            data_entry_window.coordinate_mapper.raise_()
            data_entry_window.coordinate_mapper.activateWindow()
        
        # Hide main menu when coordinate mapper is opened
        self.hide()
        
        self.update_status_label(f"Opened Game {game_id} for data entry")
    
    def on_coordinate_mapper_closing(self):
        """Handle coordinate mapper window closing - re-display main menu."""
        # Show the main menu again
        self.show()
        self.raise_()
        self.activateWindow()
        
        # Clear the data entry window reference
        self.data_entry_window = None
        
        # Update status
        self.update_status_label("Ready")
    
    def view_reports(self):
        """Open reports dialog."""
        # Open the statistics reports window
        stats_window = StatsApp(self.db, parent=self)
        stats_window.show()
        stats_window.raise_()
        stats_window.activateWindow()
    
    def list_all_games(self):
        """Open dialog to list all games with video playback and delete functionality."""
        dialog = ListGamesDialog(self.db, parent=self)
        dialog.exec()
    
    def edit_game_setup(self):
        """Edit game setup - placeholder method."""
        QMessageBox.information(
            self,
            "Not Implemented",
            "Edit Game Setup - Not yet implemented"
        )
    
    def refresh_statistics(self):
        """Reprocess outcomes and calculate statistics for the selected game."""
        game_id = self.get_selected_game_id()
        
        if not game_id:
            QMessageBox.warning(
                self,
                "No Game Selected",
                "Please select a game from the dropdown before refreshing statistics."
            )
            return
        
        # Get game info for statistics
        if not self.db.conn:
            self.db.connect()
        
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT g.team_us_id, g.team_them_id,
                   t1.name as team_us_name, t2.name as team_them_name
            FROM games g
            INNER JOIN teams t1 ON g.team_us_id = t1.team_id
            INNER JOIN teams t2 ON g.team_them_id = t2.team_id
            WHERE g.game_id = ?
        """, (game_id,))
        
        game_info = cursor.fetchone()
        if not game_info:
            QMessageBox.warning(
                self,
                "Game Not Found",
                f"Game {game_id} not found in database."
            )
            return
        
        team_us_id, team_them_id, team_us_name, team_them_name = game_info
        
        try:
            # Step 1: Reprocess outcomes
            # Get all completed rallies for this game
            cursor.execute("""
                SELECT r.rally_id, r.point_winner_id
                FROM rallies r
                WHERE r.game_id = ? AND r.point_winner_id IS NOT NULL
                ORDER BY r.rally_id
            """, (game_id,))
            
            rallies = cursor.fetchall()
            
            if rallies:
                # Reset all outcomes to 'continue' first (except 'down' and manual outcomes)
                cursor.execute("""
                    UPDATE contacts 
                    SET outcome = 'continue'
                    WHERE rally_id IN (SELECT rally_id FROM rallies WHERE game_id = ?)
                      AND outcome != 'down' 
                      AND COALESCE(outcome_manual, 0) = 0
                """, (game_id,))
                self.db.conn.commit()
                
                # Process each rally
                for rally_id, point_winner_id in rallies:
                    assign_rally_outcomes(self.db, rally_id, point_winner_id, team_us_id, team_them_id)
                
                self.db.conn.commit()
            
            # Step 2: Calculate statistics
            stats_calculator = StatsCalculator()
            stats_calculator.calculate_game_stats(self.db, game_id)
            
            # Step 3: Get final statistics for display
            cursor.execute("SELECT COUNT(*) FROM rallies WHERE game_id = ?", (game_id,))
            num_rallies = cursor.fetchone()[0] or 0
            
            cursor.execute("""
                SELECT COUNT(*) 
                FROM contacts c
                INNER JOIN rallies r ON c.rally_id = r.rally_id
                WHERE r.game_id = ?
            """, (game_id,))
            num_contacts = cursor.fetchone()[0] or 0
            
            cursor.execute("""
                SELECT point_winner_id, COUNT(*) 
                FROM rallies 
                WHERE game_id = ? AND point_winner_id IS NOT NULL
                GROUP BY point_winner_id
            """, (game_id,))
            
            points_us = 0
            points_them = 0
            for point_winner_id, count in cursor.fetchall():
                if point_winner_id == team_us_id:
                    points_us = count
                elif point_winner_id == team_them_id:
                    points_them = count
            
            # Show success dialog
            message = (
                f"Statistics have been successfully calculated.\n\n"
                f"Game: {team_us_name} vs {team_them_name}\n\n"
                f"Statistics:\n"
                f"- {num_rallies} rallies\n"
                f"- {num_contacts} contacts\n"
                f"- Points: {team_us_name} {points_us} - {points_them} {team_them_name}"
            )
            
            QMessageBox.information(
                self,
                "Statistics Calculated",
                message
            )
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to refresh statistics:\n{str(e)}"
            )
    
    def get_game_statistics_for_dialog(self, game_id: int):
        """Get statistics for a game to display in dialogs.
        
        Returns:
            Dictionary with game statistics or None if game not found
        """
        if not self.db.conn:
            self.db.connect()
        
        cursor = self.db.conn.cursor()
        
        # Get game info (team IDs and names)
        cursor.execute("""
            SELECT g.team_us_id, g.team_them_id,
                   t1.name as team_us_name, t2.name as team_them_name
            FROM games g
            INNER JOIN teams t1 ON g.team_us_id = t1.team_id
            INNER JOIN teams t2 ON g.team_them_id = t2.team_id
            WHERE g.game_id = ?
        """, (game_id,))
        
        game_info = cursor.fetchone()
        if not game_info:
            return None
        
        team_us_id, team_them_id, team_us_name, team_them_name = game_info
        
        # Count rallies
        cursor.execute("SELECT COUNT(*) FROM rallies WHERE game_id = ?", (game_id,))
        num_rallies = cursor.fetchone()[0] or 0
        
        # Count contacts
        cursor.execute("""
            SELECT COUNT(*) 
            FROM contacts c
            INNER JOIN rallies r ON c.rally_id = r.rally_id
            WHERE r.game_id = ?
        """, (game_id,))
        num_contacts = cursor.fetchone()[0] or 0
        
        # Count points for Us and Them
        cursor.execute("""
            SELECT point_winner_id, COUNT(*) 
            FROM rallies 
            WHERE game_id = ? AND point_winner_id IS NOT NULL
            GROUP BY point_winner_id
        """, (game_id,))
        
        points_us = 0
        points_them = 0
        for point_winner_id, count in cursor.fetchall():
            if point_winner_id == team_us_id:
                points_us = count
            elif point_winner_id == team_them_id:
                points_them = count
        
        return {
            'game_id': game_id,
            'team_us_id': team_us_id,
            'team_them_id': team_them_id,
            'team_us_name': team_us_name,
            'team_them_name': team_them_name,
            'num_rallies': num_rallies,
            'num_contacts': num_contacts,
            'points_us': points_us,
            'points_them': points_them
        }
    
    def end_game(self):
        """End game with confirmation and automatic stats reprocessing."""
        game_id = self.get_selected_game_id()
        
        if not game_id:
            QMessageBox.warning(
                self,
                "No Game Selected",
                "Please select a game from the dropdown before ending the game."
            )
            return
        
        # Check if game is already ended
        if self.db.is_game_ended(game_id):
            QMessageBox.information(
                self,
                "Game Already Ended",
                f"Game {game_id} has already been ended."
            )
            return
        
        # Get game statistics
        stats = self.get_game_statistics_for_dialog(game_id)
        if not stats:
            QMessageBox.warning(
                self,
                "Game Not Found",
                f"Game {game_id} not found in database."
            )
            return
        
        # Build confirmation message with statistics
        confirmation_message = (
            f"Are you sure you want to end this game?\n\n"
            f"Game: {stats['team_us_name']} vs {stats['team_them_name']}\n\n"
            f"Game Statistics:\n"
            f"- {stats['num_rallies']} rallies\n"
            f"- {stats['num_contacts']} contacts\n"
            f"- Game Score: {stats['team_us_name']} {stats['points_us']} - {stats['points_them']} {stats['team_them_name']}\n\n"
            f"After ending the game, statistics will be automatically reprocessed and calculated.\n"
            f"You will not be able to resume data entry for this game."
        )
        
        # Confirm ending the game
        reply = QMessageBox.question(
            self,
            "End Game",
            confirmation_message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Mark game as ended
                self.db.mark_game_ended(game_id)
                
                # Automatically run reprocess stats
                # Step 1: Reprocess outcomes
                cursor = self.db.conn.cursor()
                cursor.execute("""
                    SELECT r.rally_id, r.point_winner_id
                    FROM rallies r
                    WHERE r.game_id = ? AND r.point_winner_id IS NOT NULL
                    ORDER BY r.rally_id
                """, (game_id,))
                
                rallies = cursor.fetchall()
                
                if rallies:
                    # Reset all outcomes to 'continue' first (except 'down' and manual outcomes)
                    cursor.execute("""
                        UPDATE contacts 
                        SET outcome = 'continue'
                        WHERE rally_id IN (SELECT rally_id FROM rallies WHERE game_id = ?)
                          AND outcome != 'down' 
                          AND COALESCE(outcome_manual, 0) = 0
                    """, (game_id,))
                    self.db.conn.commit()
                    
                    # Process each rally
                    for rally_id, point_winner_id in rallies:
                        assign_rally_outcomes(self.db, rally_id, point_winner_id, 
                                            stats['team_us_id'], stats['team_them_id'])
                    
                    self.db.conn.commit()
                
                # Step 2: Calculate statistics
                stats_calculator = StatsCalculator()
                stats_calculator.calculate_game_stats(self.db, game_id)
                
                # Show success message
                QMessageBox.information(
                    self,
                    "Game Ended",
                    f"Game {game_id} has been ended successfully.\n\n"
                    f"Statistics have been automatically reprocessed and calculated.\n\n"
                    f"Final Statistics:\n"
                    f"- {stats['num_rallies']} rallies\n"
                    f"- {stats['num_contacts']} contacts\n"
                    f"- Final Score: {stats['team_us_name']} {stats['points_us']} - {stats['points_them']} {stats['team_them_name']}"
                )
                
                # Refresh game combo to update any visual indicators
                self.populate_game_combo()
                
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to end game:\n{str(e)}"
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
    # One-time initialization for PyInstaller compatibility
    initialize_app()
    
    app = QApplication(sys.argv)
    
    window = RocketsVideoStatsWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

