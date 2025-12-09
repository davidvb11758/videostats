"""
Dialog for viewing reports.
This is a placeholder that will be fully implemented in a future request.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QMessageBox
)
from PySide6.QtCore import Qt
from database import VideoStatsDB


class ViewReportsDialog(QDialog):
    """Dialog for viewing reports (placeholder)."""
    
    def __init__(self, db: VideoStatsDB, parent=None):
        super().__init__(parent)
        self.db = db
        
        self.setWindowTitle("View Reports")
        self.setGeometry(100, 100, 500, 300)
        
        layout = QVBoxLayout(self)
        
        # Placeholder message
        placeholder_label = QLabel(
            "Reports functionality will be implemented in a future update.\n\n"
            "This screen will allow you to:\n"
            "- View game statistics\n"
            "- View player statistics\n"
            "- View team statistics\n"
            "- Export reports to various formats\n"
            "- View lineup and rotation history"
        )
        placeholder_label.setWordWrap(True)
        placeholder_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(placeholder_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.reject)
        button_layout.addWidget(self.btn_close)
        layout.addLayout(button_layout)

