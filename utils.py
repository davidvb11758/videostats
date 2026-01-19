"""
Utility functions for PyInstaller compatibility.
Provides resource path resolution that works in both development and frozen (PyInstaller) modes.
"""

import sys
import os
from pathlib import Path


def is_frozen():
    """
    Check if the application is running in PyInstaller frozen mode.
    
    Returns:
        bool: True if running in PyInstaller mode, False otherwise
    """
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')


def resource_path(relative_path):
    """
    Get the absolute path to a resource file.
    Works in both development and PyInstaller frozen mode.
    
    Args:
        relative_path (str or Path): Relative path to the resource file
        
    Returns:
        Path: Absolute path to the resource file
    """
    if is_frozen():
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = Path(sys._MEIPASS)
    else:
        # Running in development mode
        base_path = Path(__file__).parent
    
    return base_path / relative_path


def get_user_data_dir():
    """
    Get the user data directory for storing application data.
    On Windows, this is typically %APPDATA%/VideoStats
    
    Returns:
        Path: Path to the user data directory
    """
    if sys.platform == 'win32':
        appdata = os.getenv('APPDATA')
        if appdata:
            user_data_dir = Path(appdata) / 'VideoStats'
        else:
            # Fallback if APPDATA is not set
            user_data_dir = Path.home() / 'AppData' / 'Roaming' / 'VideoStats'
    elif sys.platform == 'darwin':
        # macOS
        user_data_dir = Path.home() / 'Library' / 'Application Support' / 'VideoStats'
    else:
        # Linux and other Unix-like systems
        user_data_dir = Path.home() / '.videostats'
    
    return user_data_dir


def get_database_path():
    """
    Get the full path to the database file in the user data directory.
    Creates the user data directory if it doesn't exist.
    
    Returns:
        Path: Full path to the database file
    """
    user_data_dir = get_user_data_dir()
    # Ensure the directory exists
    user_data_dir.mkdir(parents=True, exist_ok=True)
    return user_data_dir / 'videostats.db'


def get_ffmpeg_path():
    """
    Get the path to the bundled ffmpeg executable.
    Works in both development and PyInstaller frozen mode.
    
    Returns:
        Path: Path to ffmpeg.exe
    """
    if sys.platform == 'win32':
        ffmpeg_path = resource_path("ffmpeg/bin/ffmpeg.exe")
    else:
        # Linux/macOS - use ffmpeg from PATH or bundled location
        ffmpeg_path = resource_path("ffmpeg/bin/ffmpeg")
    
    return ffmpeg_path


def initialize_app():
    """
    One-time initialization code for the application.
    Ensures user data directory exists and is ready for use.
    This should be called once at application startup.
    """
    user_data_dir = get_user_data_dir()
    user_data_dir.mkdir(parents=True, exist_ok=True)
    return user_data_dir


