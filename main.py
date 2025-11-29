import sys
from PySide6.QtWidgets import QApplication, QMessageBox, QDialog
from database import VideoStatsDB
from config_screen import ConfigScreen
from add_players import AddPlayersDialog

def main():
    app = QApplication(sys.argv)
    
    # Initialize database
    db = VideoStatsDB()
    db.initialize_database()
    
    # Step 1: Show config screen to create a new game and enter team names
    config_dialog = ConfigScreen(db=db)
    if config_dialog.exec() != QDialog.Accepted:
        # User cancelled config, exit application
        db.close()
        sys.exit(0)
    
    # Get team and game info from config
    team_us_id, team_them_id = config_dialog.get_team_ids()
    game_id = config_dialog.get_game_id()
    
    # Get team names from database
    db.connect()
    cursor = db.conn.cursor()
    cursor.execute("SELECT name FROM teams WHERE team_id = ?", (team_us_id,))
    result = cursor.fetchone()
    team_us_name = result[0] if result else "Our Team"
    cursor.execute("SELECT name FROM teams WHERE team_id = ?", (team_them_id,))
    result = cursor.fetchone()
    team_them_name = result[0] if result else "Opponent Team"
    # Don't close the database connection yet - the dialog might need it
    # db.close()
    
    # Step 2: Show add players dialog to enter player numbers and names for both teams
    try:
        print(f"Creating add players dialog for game_id={game_id}, team_us_id={team_us_id}, team_them_id={team_them_id}")  # Debug
        add_players_dialog = AddPlayersDialog(
            db=db,
            game_id=game_id,
            team_us_id=team_us_id,
            team_them_id=team_them_id,
            team_us_name=team_us_name,
            team_them_name=team_them_name
        )
        print("Add players dialog created, showing...")  # Debug
        # exec() automatically shows the dialog and makes it modal
        # It blocks until the dialog is closed
        add_players_dialog.raise_()  # Bring to front
        add_players_dialog.activateWindow()  # Activate
        result = add_players_dialog.exec()
        print(f"Add players dialog closed with result: {result}")  # Debug
    except Exception as e:
        QMessageBox.critical(
            None,
            "Error",
            f"Failed to show add players dialog:\n{str(e)}"
        )
        import traceback
        traceback.print_exc()
        db.close()
        sys.exit(1)
    
    # Close database connection after dialog is closed
    db.close()
    
    # Step 3: Show completion message
    QMessageBox.information(
        None,
        "Game Setup Complete",
        f"Game created successfully!\n\n"
        f"Game ID: {game_id}\n"
        f"Our Team: {team_us_name}\n"
        f"Opponent: {team_them_name}\n\n"
        f"You can now select this game from the data entry screen to start tracking."
    )
    
    sys.exit(0)

if __name__ == "__main__":
    main()
 