"""
Script to add players to an existing game.
Usage: python add_players_to_game.py [game_id]
If game_id is not provided, it will prompt you to enter it.
"""

import sys
from PySide6.QtWidgets import QApplication, QMessageBox
from dbstuff.database import VideoStatsDB
from add_players import AddPlayersDialog


def main():
    app = QApplication(sys.argv)
    
    # Get game_id from command line or prompt
    if len(sys.argv) > 1:
        try:
            game_id = int(sys.argv[1])
        except ValueError:
            QMessageBox.critical(None, "Error", f"Invalid game ID: {sys.argv[1]}. Must be a number.")
            sys.exit(1)
    else:
        # Prompt for game_id
        from PySide6.QtWidgets import QInputDialog
        game_id, ok = QInputDialog.getInt(
            None,
            "Select Game",
            "Enter Game ID:",
            8,  # Default to game 8
            1,  # Minimum
            9999,  # Maximum
            1   # Step
        )
        if not ok:
            sys.exit(0)
    
    # Initialize database
    db = VideoStatsDB()
    db.initialize_database()
    db.connect()
    
    # Get game information
    game = db.games.get_game_by_id(game_id)
    
    if not game:
        QMessageBox.critical(
            None,
            "Game Not Found",
            f"Game {game_id} not found in the database."
        )
        db.close()
        sys.exit(1)
    
    team_us_id = game['team_us_id']
    team_them_id = game['team_them_id']
    team_us_name = db.teams.get_team_name(team_us_id)
    team_them_name = db.teams.get_team_name(team_them_id)
    
    # Show add players dialog
    try:
        dialog = AddPlayersDialog(
            db=db,
            game_id=game_id,
            team_us_id=team_us_id,
            team_them_id=team_them_id,
            team_us_name=team_us_name,
            team_them_name=team_them_name
        )
        dialog.setWindowTitle(f"Add Players - Game {game_id}")
        dialog.raise_()
        dialog.activateWindow()
        dialog.exec()
    except Exception as e:
        QMessageBox.critical(
            None,
            "Error",
            f"Failed to show add players dialog:\n{str(e)}"
        )
        import traceback
        traceback.print_exc()
    
    db.close()
    sys.exit(0)


if __name__ == "__main__":
    main()


