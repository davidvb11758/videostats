"""
View contact paths for a volleyball game.
Displays contacts as dots connected by lines with arrowheads.
"""

import sys
import math
from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QMessageBox, QApplication, QGraphicsScene, 
    QGraphicsView, QGraphicsEllipseItem, QGraphicsLineItem, 
    QGraphicsPathItem, QGraphicsRectItem, QVBoxLayout, QHBoxLayout, QWidget,
    QListWidget, QListWidgetItem, QCheckBox, QLabel, QGroupBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt, QPointF, QRectF, QUrl
from PySide6.QtGui import QPen, QBrush, QColor, QPainterPath, QPolygonF, QPainter
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
from PySide6.QtUiTools import QUiLoader
from database import VideoStatsDB
from typing import Optional, List, Tuple


class ContactPathViewer(QMainWindow):
    """Main window for viewing contact paths."""
    
    def __init__(self, ui_widget, db: VideoStatsDB):
        super().__init__()
        
        # Copy properties from loaded UI
        self.setWindowTitle("View Contact Paths")
        self.setGeometry(ui_widget.geometry())
        
        # Set central widget and other components
        self.setCentralWidget(ui_widget.centralwidget)
        if hasattr(ui_widget, 'menubar'):
            self.setMenuBar(ui_widget.menubar)
        if hasattr(ui_widget, 'statusbar'):
            self.setStatusBar(ui_widget.statusbar)
        
        # Store reference to UI widgets
        self.ui = ui_widget
        self.db = db
        self.game_id = None
        self.team_us_id = None
        self.team_them_id = None
        
        # Graphics scene for drawing contacts
        self.scene = None
        self.graphics_view = None
        self.court_width = 440  # Scaled up to make total ~900px tall
        self.court_height = 880  # Scaled up to make total ~900px tall
        self.apron_size = 10
        self.centerline_item = None  # Store reference to centerline for redrawing
        
        # Player list widget for multi-selection
        self.player_list_widget = None
        
        # Team filter checkboxes
        self.team_filter_checkbox_a = None
        self.team_filter_checkbox_b = None
        
        # Display mode (drawing or video)
        self.display_mode = 'drawing'  # 'drawing' or 'video'
        
        # Video player components
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        self.video_item = None
        
        # Contact list table for video mode
        self.contact_table = None
        
        # Setup UI
        self.setup_graphics_view()
        self.setup_filter_widgets()
        self.setup_contact_table()
        self.populate_games_dropdown()
        self.connect_signals()
        
        # Initialize display mode UI (default is drawing mode)
        self.update_display_mode_ui()
        
        # Player list will be populated when game is selected
    
    def setup_graphics_view(self):
        """Set up QGraphicsView for drawing contacts. Creates it in outerCourt if available, otherwise creates standalone on left side."""
        # Court dimensions: 440 units wide, 880 units tall
        # With 10-unit apron on all sides: total is 460 x 900
        total_width = self.court_width + (self.apron_size * 2)  # 460
        total_height = self.court_height + (self.apron_size * 2)  # 900
        
        # Create graphics scene with total dimensions including apron
        self.scene = QGraphicsScene(0, 0, total_width, total_height, self)
        
        # Try to embed in outerCourt if it exists
        if hasattr(self.ui, 'outerCourt'):
            # Get outerCourt dimensions and position
            outer_court = self.ui.outerCourt
            court_rect = outer_court.geometry()
            
            # Create graphics view and embed it in outerCourt
            self.graphics_view = QGraphicsView(self.scene, outer_court)
            self.graphics_view.setGeometry(0, 0, court_rect.width(), court_rect.height())
        else:
            # Create standalone graphics view widget on the left side
            # Get or create central widget layout
            central = self.ui.centralwidget if hasattr(self.ui, 'centralwidget') else None
            if central:
                # Get or create layout
                layout = central.layout()
                if not layout:
                    # Create horizontal layout to place court on left
                    layout = QHBoxLayout(central)
                    layout.setContentsMargins(10, 10, 10, 10)
                    central.setLayout(layout)
                else:
                    # Check if it's already a horizontal layout, if not we might need to wrap
                    pass
                
                # Create graphics view with fixed size to ensure controls remain visible
                self.graphics_view = QGraphicsView(self.scene)
                self.graphics_view.setFixedSize(640, 1000)  # Fixed size to not cover controls
                
                # Insert at beginning of layout (left side)
                layout.insertWidget(0, self.graphics_view)
            else:
                # Fallback: create standalone
                self.graphics_view = QGraphicsView(self.scene)
                self.graphics_view.setFixedSize(640, 1000)
        
        # Configure graphics view
        self.graphics_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.graphics_view.setBackgroundBrush(QBrush(QColor(223, 223, 223)))
        self.graphics_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.graphics_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.graphics_view.show()
        
        # Draw court background
        self.draw_court_background()
    
    def draw_court_background(self):
        """Draw the volleyball court background as viewed from above."""
        if not self.scene:
            print("DEBUG: draw_court_background - scene is None!")
            return
        
        # Check if court is already drawn (look for centerline)
        if self.centerline_item and self.centerline_item in self.scene.items():
            print("DEBUG: Court background already drawn, skipping")
            return
        
        # Use instance variables for court dimensions
        court_width = self.court_width
        court_height = self.court_height
        apron_size = self.apron_size
        
        # Draw outer apron (white) - covers entire scene
        apron_rect = QRectF(0, 0, court_width + (apron_size * 2), court_height + (apron_size * 2))
        apron_item = self.scene.addRect(apron_rect, QPen(QColor(255, 255, 255), 1), 
                                       QBrush(QColor(255, 255, 255)))  # White
        
        # Draw volleyball court (very light blue) - positioned with 10-unit apron around it
        court_rect = QRectF(apron_size, apron_size, court_width, court_height)
        court_item = self.scene.addRect(court_rect, QPen(QColor(100, 100, 100), 2), 
                                        QBrush(QColor(173, 216, 230)))  # Very light blue
        
        # Draw centerline (net line) - horizontal line at middle of court height
        centerline_y = apron_size + (court_height / 2)
        self.centerline_item = self.scene.addLine(
            apron_size, centerline_y,
            apron_size + court_width, centerline_y,
            QPen(QColor(100, 100, 100), 2)
        )
        
        print(f"DEBUG: draw_court_background - Court drawn: {court_width}x{court_height} with {apron_size}-unit apron")
    
    def setup_filter_widgets(self):
        """Setup player list and team filter widgets."""
        # Use the player list widget from the UI file
        if hasattr(self.ui, 'playerListWidget'):
            self.player_list_widget = self.ui.playerListWidget
        else:
            # Fallback: create player list widget if not in UI
            self.player_list_widget = QListWidget()
            self.player_list_widget.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        
        # Use the team filter checkboxes from the UI file
        if hasattr(self.ui, 'checkBoxShowTeamA'):
            self.team_filter_checkbox_a = self.ui.checkBoxShowTeamA
        else:
            # Fallback: create checkbox if not in UI
            self.team_filter_checkbox_a = QCheckBox("Show Team A")
            self.team_filter_checkbox_a.setChecked(True)
        
        if hasattr(self.ui, 'checkBoxShowTeamB'):
            self.team_filter_checkbox_b = self.ui.checkBoxShowTeamB
        else:
            # Fallback: create checkbox if not in UI
            self.team_filter_checkbox_b = QCheckBox("Show Team B")
            self.team_filter_checkbox_b.setChecked(True)
    
    def setup_contact_table(self):
        """Setup table widget for displaying contacts in video mode."""
        # Try to use table from UI file, otherwise create it
        if hasattr(self.ui, 'contactTableWidget'):
            self.contact_table = self.ui.contactTableWidget
            print("DEBUG: Using contactTableWidget from UI file")
        else:
            print("DEBUG: Creating new contact table widget")
            # Create table widget if not in UI
            self.contact_table = QTableWidget()
            
            # Position table in the same place as graphics_view
            # Try to embed in outerCourt if it exists (same as graphics_view)
            if hasattr(self.ui, 'outerCourt'):
                outer_court = self.ui.outerCourt
                court_rect = outer_court.geometry()
                
                # Make contact table a child of outerCourt (same as graphics_view)
                self.contact_table.setParent(outer_court)
                self.contact_table.setGeometry(0, 0, court_rect.width(), court_rect.height())
                print(f"DEBUG: Contact table embedded in outerCourt at (0,0,{court_rect.width()},{court_rect.height()})")
            else:
                # Add to layout if outerCourt doesn't exist
                central = self.ui.centralwidget if hasattr(self.ui, 'centralwidget') else None
                if central:
                    layout = central.layout()
                    if layout:
                        # Match the graphics_view size
                        self.contact_table.setFixedSize(640, 1000)
                        print(f"DEBUG: Adding contact table to existing layout: {type(layout)}")
                        # Insert at position 0 (same as graphics_view)
                        layout.insertWidget(0, self.contact_table)
                    else:
                        print("DEBUG: No layout found in central widget")
        
        if not self.contact_table:
            print("ERROR: Failed to create/find contact table!")
            return
        
        # Configure table
        self.contact_table.setColumnCount(5)
        self.contact_table.setHorizontalHeaderLabels(['Timecode', 'Player #', 'Player Name', 'Contact Type', 'Outcome'])
        
        # Set column widths
        header = self.contact_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # Timecode
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Player #
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # Player Name
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Contact Type
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Outcome
        
        # Set selection mode
        self.contact_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.contact_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        
        # Hide by default (shown only in video mode)
        self.contact_table.setVisible(False)
        print(f"DEBUG: Contact table setup complete, initial visibility: {self.contact_table.isVisible()}")
    
    def populate_games_dropdown(self):
        """Populate the games comboBox with all games from the database."""
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
        
        if hasattr(self.ui, 'comboBox'):
            self.ui.comboBox.clear()
            
            # Add "Select a game" as first item
            self.ui.comboBox.addItem("Select a game")
            self.ui.comboBox.setItemData(0, None, Qt.UserRole)
            
            for game in games:
                game_id, game_date, team_us_name, team_them_name, team_us_id, team_them_id = game
                display_text = f"Game {game_id}: {team_us_name} vs {team_them_name} ({game_date})"
                self.ui.comboBox.addItem(display_text)
                # Store game data
                index = self.ui.comboBox.count() - 1
                self.ui.comboBox.setItemData(index, {
                    'game_id': game_id,
                    'team_us_id': team_us_id,
                    'team_them_id': team_them_id,
                    'team_us_name': team_us_name,
                    'team_them_name': team_them_name
                }, Qt.UserRole)
    
    def populate_player_list(self):
        """Populate the player list widget with players from our team for the selected game."""
        if not self.game_id or not self.team_us_id:
            return
        
        if not self.player_list_widget:
            return
        
        if not self.db.conn:
            self.db.connect()
        
        # Get players for our team in this game
        players = self.db.get_game_players(self.game_id, self.team_us_id)
        
        self.player_list_widget.clear()
        
        # Add "All Players" option
        all_item = QListWidgetItem("All Players")
        all_item.setData(Qt.UserRole, None)  # None indicates "all players"
        self.player_list_widget.addItem(all_item)
        all_item.setSelected(True)  # Select by default
        
        for player in players:
            player_id, player_number, player_name, team_id = player
            display_text = f"{player_number}"
            if player_name:
                display_text += f" - {player_name}"
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, player_id)
            self.player_list_widget.addItem(item)
        
        # Connect itemClicked signal for smart selection behavior
        self.player_list_widget.itemClicked.connect(self.on_player_item_clicked)
    
    def on_player_item_clicked(self, item):
        """Handle smart selection: deselect 'All Players' when individual players are clicked, and vice versa."""
        if not self.player_list_widget or not item:
            return
        
        # Block signals temporarily to avoid recursive calls
        self.player_list_widget.blockSignals(True)
        
        try:
            clicked_player_id = item.data(Qt.UserRole)
            
            if clicked_player_id is None:
                # "All Players" was clicked
                if item.isSelected():
                    # "All Players" was just selected - deselect all individual players
                    for i in range(1, self.player_list_widget.count()):
                        player_item = self.player_list_widget.item(i)
                        if player_item:
                            player_item.setSelected(False)
                else:
                    # "All Players" was just deselected
                    # If no other players are selected, re-select "All Players" (can't have nothing selected)
                    has_selection = False
                    for i in range(1, self.player_list_widget.count()):
                        if self.player_list_widget.item(i).isSelected():
                            has_selection = True
                            break
                    if not has_selection:
                        item.setSelected(True)
            else:
                # An individual player was clicked
                if item.isSelected():
                    # Individual player was just selected - deselect "All Players"
                    all_players_item = self.player_list_widget.item(0)
                    if all_players_item:
                        all_players_item.setSelected(False)
                else:
                    # Individual player was just deselected
                    # If no players are selected now, select "All Players"
                    has_selection = False
                    for i in range(1, self.player_list_widget.count()):
                        player_item = self.player_list_widget.item(i)
                        if player_item and player_item.isSelected():
                            has_selection = True
                            break
                    if not has_selection:
                        all_players_item = self.player_list_widget.item(0)
                        if all_players_item:
                            all_players_item.setSelected(True)
        
        finally:
            # Re-enable signals
            self.player_list_widget.blockSignals(False)
    
    def connect_signals(self):
        """Connect UI signals to handlers."""
        if hasattr(self.ui, 'comboBox'):
            self.ui.comboBox.currentIndexChanged.connect(self.on_game_selected)
        
        if hasattr(self.ui, 'pushButtonDisplayContacts'):
            self.ui.pushButtonDisplayContacts.clicked.connect(self.display_contacts)
        
        if hasattr(self.ui, 'pushButtonClearPlot'):
            self.ui.pushButtonClearPlot.clicked.connect(self.clear_contacts)
        
        # Connect display mode radio buttons
        if hasattr(self.ui, 'radioButtonDisplayDrawing'):
            self.ui.radioButtonDisplayDrawing.toggled.connect(self.on_display_mode_changed)
        
        if hasattr(self.ui, 'radioButtonViewVideo'):
            self.ui.radioButtonViewVideo.toggled.connect(self.on_display_mode_changed)
        
        # Connect table row click to seek video
        if self.contact_table:
            self.contact_table.cellClicked.connect(self.on_contact_row_clicked)
    
    def on_game_selected(self, index: int):
        """Handle game selection from dropdown."""
        if index < 0:
            return
        
        if hasattr(self.ui, 'comboBox'):
            item_data = self.ui.comboBox.itemData(index, Qt.UserRole)
            if not item_data:
                # "Select a game" or invalid selection - clear everything
                self.game_id = None
                self.team_us_id = None
                self.team_them_id = None
                if hasattr(self.ui, 'teamNameUs'):
                    self.ui.teamNameUs.setText('')
                if hasattr(self.ui, 'teamNameThem'):
                    self.ui.teamNameThem.setText('')
                if self.player_list_widget:
                    self.player_list_widget.clear()
                return
            
            self.game_id = item_data['game_id']
            self.team_us_id = item_data['team_us_id']
            self.team_them_id = item_data['team_them_id']
            
            # Update team name labels
            if hasattr(self.ui, 'teamNameUs'):
                self.ui.teamNameUs.setText(item_data['team_us_name'])
            if hasattr(self.ui, 'teamNameThem'):
                self.ui.teamNameThem.setText(item_data['team_them_name'])
            
            # Populate player list for our team
            self.populate_player_list()
    
    def on_display_mode_changed(self):
        """Handle display mode radio button changes."""
        # Determine which mode is selected
        if hasattr(self.ui, 'radioButtonViewVideo') and self.ui.radioButtonViewVideo.isChecked():
            self.display_mode = 'video'
            print("DEBUG: Display mode changed to VIDEO")
        else:
            self.display_mode = 'drawing'
            print("DEBUG: Display mode changed to DRAWING")
        
        # Update UI visibility
        self.update_display_mode_ui()
        
        # Note: We don't load video automatically anymore
        # Video loading will happen when user clicks a contact in the table
    
    def update_display_mode_ui(self):
        """Update UI visibility based on display mode."""
        print(f"DEBUG: update_display_mode_ui called, mode = {self.display_mode}")
        
        if self.display_mode == 'drawing':
            # Show court drawing (graphics view), hide contact table
            if self.graphics_view:
                self.graphics_view.setVisible(True)
                print("DEBUG: Graphics view visible = True")
            if self.contact_table:
                self.contact_table.setVisible(False)
                print("DEBUG: Contact table visible = False")
            # Make sure court background is drawn
            self.draw_court_background()
        else:  # video mode
            # Hide court drawing (graphics view), show contact table in its place
            if self.graphics_view:
                self.graphics_view.setVisible(False)
                print("DEBUG: Graphics view visible = False (hidden for video mode)")
            if self.contact_table:
                self.contact_table.setVisible(True)
                print(f"DEBUG: Contact table visible = True, isVisible={self.contact_table.isVisible()}")
            else:
                print("DEBUG: WARNING - contact_table is None!")
    
    def load_video_for_game(self):
        """Load video file for the selected game."""
        if not self.game_id:
            return
        
        if not self.db.conn:
            self.db.connect()
        
        # Get video path from database
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT video_file_path FROM games WHERE game_id = ?", (self.game_id,))
        result = cursor.fetchone()
        
        if not result or not result[0]:
            QMessageBox.warning(self, "No Video", "No video file associated with this game.")
            return
        
        video_path = result[0]
        
        # Create video item if not exists
        if not self.video_item:
            self.video_item = QGraphicsVideoItem()
            # Size video to fit the scene (with apron)
            total_width = self.court_width + (self.apron_size * 2)
            total_height = self.court_height + (self.apron_size * 2)
            self.video_item.setSize(QRectF(0, 0, total_width, total_height).size())
            self.scene.addItem(self.video_item)
            self.video_item.setZValue(-1)
            self.video_item.setPos(0, 0)
        
        # Set video output and load video
        self.media_player.setVideoOutput(self.video_item)
        self.media_player.setSource(QUrl.fromLocalFile(video_path))
        self.video_item.setVisible(True)
        
        print(f"DEBUG: Loaded video: {video_path}")
    
    def on_contact_row_clicked(self, row, column):
        """Handle contact table row click - seek video to timecode."""
        if not self.contact_table or row < 0:
            return
        
        # Get timecode from first column (stored in milliseconds as user data)
        timecode_item = self.contact_table.item(row, 0)
        if timecode_item:
            timecode_ms = timecode_item.data(Qt.UserRole)
            if timecode_ms is not None:
                # Seek video to this timecode
                self.media_player.setPosition(timecode_ms)
                # Pause video at this position
                self.media_player.pause()
                print(f"DEBUG: Seeked to timecode: {timecode_ms}ms")
    
    def display_contacts(self):
        """Display contacts for the selected game with filtering."""
        if not self.game_id:
            QMessageBox.warning(self, "No Game Selected", "Please select a game first!")
            return
        
        print(f"DEBUG: display_contacts called, mode = {self.display_mode}")
        
        # Route to appropriate display method based on mode
        if self.display_mode == 'video':
            print("DEBUG: Routing to display_contacts_video_mode()")
            self.display_contacts_video_mode()
        else:
            print("DEBUG: Routing to display_contacts_drawing_mode()")
            self.display_contacts_drawing_mode()
    
    def display_contacts_drawing_mode(self):
        """Display contacts in drawing mode (existing functionality)."""
        if not self.scene:
            QMessageBox.warning(self, "Graphics Error", "Graphics view not initialized!")
            return
        
        # Clear previous contacts
        self.clear_contacts()
        
        # Get filter criteria - multiple players
        selected_player_ids = []
        all_players_selected = False
        
        if self.player_list_widget:
            selected_items = self.player_list_widget.selectedItems()
            for item in selected_items:
                player_id = item.data(Qt.UserRole)
                if player_id is None:
                    # "All Players" is selected
                    all_players_selected = True
                    break
                else:
                    selected_player_ids.append(player_id)
        
        # Get team filter criteria
        show_team_a = self.team_filter_checkbox_a.isChecked() if self.team_filter_checkbox_a else True
        show_team_b = self.team_filter_checkbox_b.isChecked() if self.team_filter_checkbox_b else True
        
        # Determine which teams to show
        team_ids_to_show = []
        if show_team_a:
            team_ids_to_show.append(self.team_us_id)
        if show_team_b:
            team_ids_to_show.append(self.team_them_id)
        
        if not team_ids_to_show:
            QMessageBox.warning(self, "No Teams Selected", "Please select at least one team to display!")
            return
        
        # Get selected contact types from checkboxes
        selected_contact_types = []
        contact_type_mapping = {
            'serve': 'serve',
            'receive': 'receive',
            'pass': 'pass',
            'set': 'set',
            'attack': 'attack',
            'freeball': 'freeball',
            'block': 'block',
            'down': 'down'  # Ball hit the floor
        }
        
        for contact_type_key, contact_type_value in contact_type_mapping.items():
            checkbox_name = f'checkBox_{contact_type_key}_A'
            if hasattr(self.ui, checkbox_name):
                checkbox = getattr(self.ui, checkbox_name)
                if checkbox.isChecked():
                    selected_contact_types.append(contact_type_value)
        
        # Get selected outcomes from checkboxes
        selected_outcomes = []
        outcome_mapping = {
            'continue': 'continue',
            'ace': 'ace',
            'kill': 'kill',
            'stuff': 'stuff',
            'error': 'error',
            'down': 'down'
        }
        
        for outcome_key, outcome_value in outcome_mapping.items():
            checkbox_name = f'checkBox_outcome_{outcome_key}'
            if hasattr(self.ui, checkbox_name):
                checkbox = getattr(self.ui, checkbox_name)
                if checkbox.isChecked():
                    selected_outcomes.append(outcome_value)
        
        # Determine if a filter is applied
        has_player_filter = (not all_players_selected) and len(selected_player_ids) > 0
        has_contact_type_filter = len(selected_contact_types) < len(contact_type_mapping.values())
        has_outcome_filter = len(selected_outcomes) > 0 and len(selected_outcomes) < len(outcome_mapping.values())
        has_team_filter = len(team_ids_to_show) < 2
        has_filter = has_player_filter or has_contact_type_filter or has_outcome_filter or has_team_filter
        
        # If no contact types selected, show all
        if not selected_contact_types:
            selected_contact_types = list(contact_type_mapping.values())
        
        # If no outcomes selected, show all
        if not selected_outcomes:
            selected_outcomes = list(outcome_mapping.values())
        
        # Query contacts for this game with filters
        if not self.db.conn:
            self.db.connect()
        
        cursor = self.db.conn.cursor()
        
        # First, get the selected player's contacts (filtered)
        query_filtered = """
            SELECT 
                c.contact_id,
                c.rally_id,
                c.sequence_number,
                c.contact_type,
                c.x,
                c.y,
                r.rally_number,
                p.player_number,
                p.name as player_name,
                t.team_id,
                t.name as team_name,
                c.outcome
            FROM contacts c
            INNER JOIN rallies r ON c.rally_id = r.rally_id
            LEFT JOIN players p ON c.player_id = p.player_id
            INNER JOIN teams t ON c.team_id = t.team_id
            WHERE r.game_id = ?
              AND c.x IS NOT NULL 
              AND c.y IS NOT NULL
              AND c.contact_type IN ({})
              AND c.outcome IN ({})
        """.format(','.join(['?'] * len(selected_contact_types)), ','.join(['?'] * len(selected_outcomes)))
        
        params_filtered = [self.game_id] + selected_contact_types + selected_outcomes
        
        # Add team filter
        if len(team_ids_to_show) < 2:
            # Only one team selected
            query_filtered += " AND c.team_id IN ({})".format(','.join(['?'] * len(team_ids_to_show)))
            params_filtered.extend(team_ids_to_show)
        
        # Add player filter if specific players are selected
        # Note: Floor contacts (contacts without player_id) are excluded when filtering by player
        if has_player_filter and not all_players_selected:
            query_filtered += " AND c.player_id IN ({})".format(','.join(['?'] * len(selected_player_ids)))
            params_filtered.extend(selected_player_ids)
        
        query_filtered += " ORDER BY r.rally_number, c.sequence_number"
        
        cursor.execute(query_filtered, params_filtered)
        filtered_contacts = cursor.fetchall()
        
        if not filtered_contacts:
            QMessageBox.information(self, "No Contacts", 
                                   "No contacts match the selected filter criteria.")
            return
        
        # Now get ALL contacts in the same rallies (to find next contact after each filtered contact)
        # Get unique rally_ids from filtered contacts
        rally_ids = [contact[1] for contact in filtered_contacts]
        rally_ids_str = ','.join(['?'] * len(rally_ids))
        
        query_all = f"""
            SELECT 
                c.contact_id,
                c.rally_id,
                c.sequence_number,
                c.contact_type,
                c.x,
                c.y,
                r.rally_number,
                p.player_number,
                p.name as player_name,
                t.team_id,
                t.name as team_name,
                c.outcome
            FROM contacts c
            INNER JOIN rallies r ON c.rally_id = r.rally_id
            LEFT JOIN players p ON c.player_id = p.player_id
            INNER JOIN teams t ON c.team_id = t.team_id
            WHERE c.rally_id IN ({rally_ids_str})
              AND c.x IS NOT NULL 
              AND c.y IS NOT NULL
            ORDER BY r.rally_number, c.sequence_number
        """
        
        cursor.execute(query_all, rally_ids)
        all_contacts = cursor.fetchall()
        
        # Create a lookup map: (rally_id, sequence_number) -> contact
        all_contacts_map = {}
        for contact in all_contacts:
            rally_id = contact[1]
            seq_num = contact[2]
            all_contacts_map[(rally_id, seq_num)] = contact
        
        # Draw contacts and connecting lines
        self.draw_contact_paths(filtered_contacts, all_contacts_map, has_filter)
        
        QMessageBox.information(self, "Contacts Displayed", 
                               f"Displayed {len(filtered_contacts)} contacts matching the filter criteria.")
    
    def display_contacts_video_mode(self):
        """Display contacts in video mode - show table with contact list."""
        if not self.contact_table:
            QMessageBox.warning(self, "UI Error", "Contact table not initialized!")
            return
        
        # Clear previous table data
        self.contact_table.setRowCount(0)
        
        # Get filter criteria (same as drawing mode)
        selected_player_ids = []
        all_players_selected = False
        
        if self.player_list_widget:
            selected_items = self.player_list_widget.selectedItems()
            for item in selected_items:
                player_id = item.data(Qt.UserRole)
                if player_id is None:
                    all_players_selected = True
                    break
                else:
                    selected_player_ids.append(player_id)
        
        # Get team filter criteria
        show_team_a = self.team_filter_checkbox_a.isChecked() if self.team_filter_checkbox_a else True
        show_team_b = self.team_filter_checkbox_b.isChecked() if self.team_filter_checkbox_b else True
        
        team_ids_to_show = []
        if show_team_a:
            team_ids_to_show.append(self.team_us_id)
        if show_team_b:
            team_ids_to_show.append(self.team_them_id)
        
        if not team_ids_to_show:
            QMessageBox.warning(self, "No Teams Selected", "Please select at least one team to display!")
            return
        
        # Get selected contact types
        selected_contact_types = []
        contact_type_mapping = {
            'serve': 'serve',
            'receive': 'receive',
            'pass': 'pass',
            'set': 'set',
            'attack': 'attack',
            'freeball': 'freeball',
            'block': 'block',
            'down': 'down'
        }
        
        for contact_type_key, contact_type_value in contact_type_mapping.items():
            checkbox_name = f'checkBox_{contact_type_key}_A'
            if hasattr(self.ui, checkbox_name):
                checkbox = getattr(self.ui, checkbox_name)
                if checkbox.isChecked():
                    selected_contact_types.append(contact_type_value)
        
        # Get selected outcomes
        selected_outcomes = []
        outcome_mapping = {
            'continue': 'continue',
            'ace': 'ace',
            'kill': 'kill',
            'stuff': 'stuff',
            'error': 'error',
            'down': 'down'
        }
        
        for outcome_key, outcome_value in outcome_mapping.items():
            checkbox_name = f'checkBox_outcome_{outcome_key}'
            if hasattr(self.ui, checkbox_name):
                checkbox = getattr(self.ui, checkbox_name)
                if checkbox.isChecked():
                    selected_outcomes.append(outcome_value)
        
        # If no contact types selected, show all
        if not selected_contact_types:
            selected_contact_types = list(contact_type_mapping.values())
        
        # If no outcomes selected, show all
        if not selected_outcomes:
            selected_outcomes = list(outcome_mapping.values())
        
        # Query contacts
        if not self.db.conn:
            self.db.connect()
        
        cursor = self.db.conn.cursor()
        
        query = """
            SELECT 
                c.contact_id,
                c.timecode,
                p.player_number,
                p.name as player_name,
                c.contact_type,
                c.outcome,
                r.rally_number,
                c.sequence_number
            FROM contacts c
            INNER JOIN rallies r ON c.rally_id = r.rally_id
            LEFT JOIN players p ON c.player_id = p.player_id
            INNER JOIN teams t ON c.team_id = t.team_id
            WHERE r.game_id = ?
              AND c.contact_type IN ({})
              AND c.outcome IN ({})
        """.format(','.join(['?'] * len(selected_contact_types)), ','.join(['?'] * len(selected_outcomes)))
        
        params = [self.game_id] + selected_contact_types + selected_outcomes
        
        # Add team filter
        if len(team_ids_to_show) < 2:
            query += " AND c.team_id IN ({})".format(','.join(['?'] * len(team_ids_to_show)))
            params.extend(team_ids_to_show)
        
        # Add player filter
        if not all_players_selected and len(selected_player_ids) > 0:
            query += " AND c.player_id IN ({})".format(','.join(['?'] * len(selected_player_ids)))
            params.extend(selected_player_ids)
        
        query += " ORDER BY r.rally_number, c.sequence_number"
        
        cursor.execute(query, params)
        contacts = cursor.fetchall()
        
        print(f"DEBUG: display_contacts_video_mode - Found {len(contacts)} contacts")
        
        if not contacts:
            QMessageBox.information(self, "No Contacts", 
                                   "No contacts match the selected filter criteria.")
            return
        
        # Make sure table is visible
        if self.contact_table:
            self.contact_table.setVisible(True)
            print(f"DEBUG: Contact table visibility: {self.contact_table.isVisible()}")
        
        # Populate table
        self.contact_table.setRowCount(len(contacts))
        print(f"DEBUG: Set table row count to {len(contacts)}")
        
        for row_idx, contact in enumerate(contacts):
            (contact_id, timecode_ms, player_number, player_name, 
             contact_type, outcome, rally_number, sequence_number) = contact
            
            # Format timecode as HH:MM:SS.mmm
            timecode_str = self.format_timecode(timecode_ms) if timecode_ms is not None else "--:--:--.---"
            
            # Create table items
            timecode_item = QTableWidgetItem(timecode_str)
            timecode_item.setData(Qt.UserRole, timecode_ms)  # Store actual timecode for seeking
            
            player_num_item = QTableWidgetItem(player_number if player_number else "")
            player_name_item = QTableWidgetItem(player_name if player_name else "")
            contact_type_item = QTableWidgetItem(contact_type)
            outcome_item = QTableWidgetItem(outcome)
            
            # Set items in table
            self.contact_table.setItem(row_idx, 0, timecode_item)
            self.contact_table.setItem(row_idx, 1, player_num_item)
            self.contact_table.setItem(row_idx, 2, player_name_item)
            self.contact_table.setItem(row_idx, 3, contact_type_item)
            self.contact_table.setItem(row_idx, 4, outcome_item)
            
            if row_idx == 0:
                print(f"DEBUG: First row - timecode={timecode_str}, player={player_number}, type={contact_type}")
        
        QMessageBox.information(self, "Contacts Displayed", 
                               f"Displaying {len(contacts)} contacts in table.")
    
    def format_timecode(self, timecode_ms):
        """Format timecode from milliseconds to HH:MM:SS.mmm"""
        if timecode_ms is None:
            return "--:--:--.---"
        
        total_seconds = timecode_ms // 1000
        milliseconds = timecode_ms % 1000
        
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
    
    def clear_contacts(self):
        """Clear contacts - graphics in drawing mode, table in video mode."""
        if self.display_mode == 'video':
            # Clear contact table
            if self.contact_table:
                self.contact_table.setRowCount(0)
        else:
            # Clear graphics items (drawing mode)
            self.clear_contacts_drawing()
    
    def clear_contacts_drawing(self):
        """Clear all contact graphics items from the scene, but keep court background and centerline."""
        if not self.scene:
            return
        
        # Remove all items except the court background and centerline
        # Keep items that represent the court (rectangles) and the centerline
        items_to_remove = []
        for item in self.scene.items():
            # Remove ellipses (contact dots), rectangles (floor contacts), lines (except centerline), and paths (arrows)
            if isinstance(item, QGraphicsEllipseItem):
                items_to_remove.append(item)
            elif isinstance(item, QGraphicsRectItem):
                # Remove floor contact squares, but keep court background rectangles
                # Court background rectangles are added directly to scene, so check if it's a contact square
                # Contact squares are small (8x8), court rectangles are large (300x600 or 320x620)
                rect = item.rect()
                if rect.width() < 20 and rect.height() < 20:  # Small rectangles are floor contacts
                    items_to_remove.append(item)
            elif isinstance(item, QGraphicsLineItem):
                # Don't remove the centerline
                if item != self.centerline_item:
                    items_to_remove.append(item)
            elif isinstance(item, QGraphicsPathItem):
                items_to_remove.append(item)
        
        for item in items_to_remove:
            self.scene.removeItem(item)
        
        # Redraw centerline if it was removed or doesn't exist
        if self.centerline_item is None or self.centerline_item not in self.scene.items():
            court_width = self.court_width
            court_height = self.court_height
            apron_size = self.apron_size
            centerline_y = apron_size + (court_height / 2)
            self.centerline_item = self.scene.addLine(
                apron_size, centerline_y,
                apron_size + court_width, centerline_y,
                QPen(QColor(100, 100, 100), 2)
            )
    
    def draw_contact_paths(self, filtered_contacts: List[Tuple], all_contacts_map: dict, has_filter: bool = False):
        """Draw contact dots and vectors (arrows) to next sequential contact.
        
        Args:
            filtered_contacts: List of contacts matching the filter criteria (to draw as dots)
            all_contacts_map: Dictionary mapping (rally_id, sequence_number) -> contact for all contacts
                             in the same rallies (to find next sequential contact)
            has_filter: True if a filter is applied (player or contact type), False otherwise (unused now)
        """
        if not self.scene:
            return
        
        # Court dimensions: 440 x 880 with 10-unit apron
        court_width = getattr(self, 'court_width', 440)
        court_height = getattr(self, 'court_height', 880)
        apron_size = getattr(self, 'apron_size', 10)
        
        # Create a set of filtered contact (rally_id, seq_num) tuples for quick lookup
        # This helps us determine if a contact should be drawn as a dot
        filtered_contacts_set = set()
        for contact in filtered_contacts:
            rally_id = contact[1]
            seq_num = contact[2]
            filtered_contacts_set.add((rally_id, seq_num))
        
        # Find min and max sequence numbers for each rally to identify first/last contacts
        rally_first_seq = {}  # rally_id -> min sequence_number
        rally_last_seq = {}   # rally_id -> max sequence_number
        for (rally_id, seq_num), contact in all_contacts_map.items():
            if rally_id not in rally_first_seq or seq_num < rally_first_seq[rally_id]:
                rally_first_seq[rally_id] = seq_num
            if rally_id not in rally_last_seq or seq_num > rally_last_seq[rally_id]:
                rally_last_seq[rally_id] = seq_num
        
        # Convert coordinates from database (0-300 x 0-600, lower-left origin) 
        # to scene coordinates (with apron offset, top-left origin)
        # Database coordinates are in the original 300x600 system, need to scale to current court size
        db_court_width = 300
        db_court_height = 600
        scale_x = court_width / db_court_width  # 440/300 = 1.467
        scale_y = court_height / db_court_height  # 880/600 = 1.467
        
        for contact in filtered_contacts:
            (contact_id, rally_id, seq_num, contact_type, x, y, 
             rally_number, player_number, player_name, team_id, team_name, outcome) = contact
            
            # Check if this is a floor contact (ball hit the floor - has coordinates but no player)
            is_floor_contact = (player_number is None and player_name is None)
            
            # Scale database coordinates to current court size
            scaled_x = x * scale_x
            scaled_y = y * scale_y
            
            # Convert y from lower-left origin (stored in DB: 0 at bottom, 600 at top)
            # to top-left origin (Qt Graphics: 0 at top, 880 at bottom)
            # Then add apron offset
            draw_y = apron_size + (court_height - scaled_y)
            draw_x = apron_size + scaled_x
            
            current_point = QPointF(draw_x, draw_y)
            
            # Determine dot color and line color based on outcome
            # kill = green, continue = medium gray, error = red, ace = bright green, down = dark gray, stuff = blue dot/green line
            outcome_colors = {
                'kill': QColor(0, 200, 0),        # Green
                'ace': QColor(0, 255, 0),         # Bright green
                'stuff': QColor(0, 150, 255),     # Bright blue (dot)
                'error': QColor(255, 0, 0),       # Red
                'continue': QColor(128, 128, 128), # Medium gray
                'down': QColor(64, 64, 64)        # Dark gray
            }
            
            # Get color based on outcome (default to medium gray if outcome not recognized)
            dot_color = outcome_colors.get(outcome, QColor(128, 128, 128))
            
            # Line color: stuff blocks use green (like kills), others use the dot color
            if outcome == 'stuff':
                line_color = QColor(0, 200, 0)  # Green for stuff block lines
            else:
                line_color = dot_color  # Use the same color for the line/vector
            
            # Draw contact dot at the origin of the contact
            # For floor contacts, use a square instead of a circle to make them visually distinct
            dot_radius = 4
            if is_floor_contact:
                # Draw a square for floor contacts
                dot = self.scene.addRect(
                    draw_x - dot_radius, draw_y - dot_radius, 
                    dot_radius * 2, dot_radius * 2,
                    QPen(QColor(0, 0, 0), 1),
                    QBrush(dot_color)
                )
            else:
                # Draw a circle for regular contacts
                dot = self.scene.addEllipse(
                    draw_x - dot_radius, draw_y - dot_radius, 
                    dot_radius * 2, dot_radius * 2,
                    QPen(QColor(0, 0, 0), 1),
                    QBrush(dot_color)
                )
            
            # Always draw a vector from this contact to the next sequential contact
            # The next contact may or may not match the filter
            next_seq = seq_num + 1
            next_contact = all_contacts_map.get((rally_id, next_seq))
            
            if next_contact:
                # Get next contact coordinates (even if it doesn't match the filter)
                (next_contact_id, next_rally_id, next_seq_num, next_contact_type, 
                 next_x, next_y, next_rally_number, next_player_number, 
                 next_player_name, next_team_id, next_team_name, next_outcome) = next_contact
                
                # Scale and convert coordinates (same as above)
                next_scaled_x = next_x * scale_x
                next_scaled_y = next_y * scale_y
                next_draw_y = apron_size + (court_height - next_scaled_y)
                next_draw_x = apron_size + next_scaled_x
                next_point = QPointF(next_draw_x, next_draw_y)
                
                # Determine line style based on contact_type
                # receive, pass, block = medium dash line
                # set = dotted line
                # attack, freeball = solid line
                pen = QPen(line_color, 2)
                if contact_type in ['receive', 'pass', 'block']:
                    pen.setStyle(Qt.PenStyle.DashLine)
                elif contact_type == 'set':
                    pen.setStyle(Qt.PenStyle.DotLine)
                elif contact_type in ['attack', 'freeball']:
                    pen.setStyle(Qt.PenStyle.SolidLine)
                else:
                    # Default to solid line for other types (serve, down)
                    pen.setStyle(Qt.PenStyle.SolidLine)
                
                # Draw vector (line with arrowhead) from current contact to next sequential contact
                line = self.scene.addLine(
                    current_point.x(), current_point.y(),
                    next_point.x(), next_point.y(),
                    pen
                )
                
                # Draw arrowhead at the end of the line (pointing to next contact location)
                self.draw_arrowhead(current_point, next_point, line_color)
    
    def draw_arrowhead(self, start_point: QPointF, end_point: QPointF, color: QColor):
        """Draw an arrowhead at the end point pointing from start to end."""
        if not self.scene:
            return
        
        # Calculate direction vector
        dx = end_point.x() - start_point.x()
        dy = end_point.y() - start_point.y()
        
        # Skip if points are too close
        distance = math.sqrt(dx * dx + dy * dy)
        if distance < 5:
            return
        
        # Calculate angle
        angle = math.atan2(dy, dx)
        
        # Arrowhead parameters
        arrow_length = 15
        arrow_width = 8
        
        # Create arrowhead polygon (triangle pointing right, will be rotated)
        arrowhead = QPolygonF([
            QPointF(0, 0),
            QPointF(-arrow_length, -arrow_width / 2),
            QPointF(-arrow_length, arrow_width / 2)
        ])
        
        # Transform arrowhead to end point with correct rotation
        from PySide6.QtGui import QTransform
        transform = QTransform()
        transform.translate(end_point.x(), end_point.y())
        transform.rotate(math.degrees(angle))
        arrowhead = transform.map(arrowhead)
        
        # Draw arrowhead as filled polygon
        arrow_path = QPainterPath()
        arrow_path.addPolygon(arrowhead)
        arrow_item = self.scene.addPath(arrow_path, QPen(color, 1), QBrush(color))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Initialize database
    db = VideoStatsDB()
    db.initialize_database()
    db.connect()
    
    # Load UI
    ui_file = Path(__file__).parent / "viewPaths.ui"
    loader = QUiLoader()
    ui_widget = loader.load(str(ui_file))
    
    if ui_widget:
        window = ContactPathViewer(ui_widget=ui_widget, db=db)
        window.show()
        sys.exit(app.exec())
    else:
        print("Failed to load UI file")
        sys.exit(1)

