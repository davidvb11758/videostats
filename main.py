"""
Main entry point for VideoStats application.
This now launches the RocketsVideoStats main menu screen.
"""

import sys
from PySide6.QtWidgets import QApplication
from RocketsVideoStats import RocketsVideoStatsWindow


def main():
    """Main entry point - launches the main menu."""
    app = QApplication(sys.argv)
    
    window = RocketsVideoStatsWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
 