"""
Main entry point for Highlight Collection Manager.
"""

import sys
from PySide6.QtWidgets import QApplication
from database import VideoStatsDB
from ui.highlight_manager import HighlightCollectionManager


def main():
    """Main entry point."""
    app = QApplication(sys.argv)
    
    # Initialize database
    db = VideoStatsDB()
    db.initialize_database()
    db.connect()
    
    # Create collection tables if they don't exist
    db.create_collection_tables()
    
    # Create and show window
    window = HighlightCollectionManager(db)
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

