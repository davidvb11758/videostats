"""
Main entry point for VideoStats application.
This now launches the main menu screen.
"""

import sys
from PySide6.QtWidgets import QApplication
from main_menu import MainMenuWindow


def main():
    """Main entry point - launches the main menu."""
    app = QApplication(sys.argv)
    
    window = MainMenuWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
 