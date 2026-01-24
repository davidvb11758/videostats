import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QComboBox, QListWidget, 
                             QTabWidget, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QPushButton, QMessageBox)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor
from dbstuff.database import VideoStatsDB


class StatsApp(QMainWindow):
    def __init__(self, db: VideoStatsDB, parent=None):
        super().__init__(parent)
        self.db = db
        if not self.db.conn:
            self.db.connect()
        self.selected_team_id = None
        self.selected_game_ids = []
        self.init_ui()
        self.load_teams()
        
    def init_ui(self):
        self.setWindowTitle('Iowa RocketsVolleyball Game Statistics')
        # Set smaller initial size and make window resizable
        self.setGeometry(100, 100, 1400, 800)
        self.setMinimumSize(800, 500)  # Allow resizing but set minimum size
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(5)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Controls section - create a container widget
        controls_widget = QWidget()
        controls_widget.setFixedHeight(120)
        controls_widget.setStyleSheet("""
            QWidget {
                background: #f8f9fa;
                border-radius: 4px;
            }
        """)
        controls_layout = QHBoxLayout(controls_widget)
        controls_layout.setSpacing(8)
        controls_layout.setContentsMargins(8, 5, 8, 5)
        
        # Team selection
        team_label = QLabel('Select Team:')
        team_label.setFont(QFont('', 9, QFont.Bold))
        team_label.setStyleSheet("color: #333;")
        team_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.team_combo = QComboBox()
        self.team_combo.setMinimumWidth(200)
        self.team_combo.setStyleSheet("""
            QComboBox {
                background: white;
                border: 2px solid #ddd;
                border-radius: 4px;
                padding: 5px;
                font-size: 14px;
            }
            QComboBox:hover {
                border-color: #667eea;
            }
            QComboBox::drop-down {
                border: none;
            }
        """)
        self.team_combo.currentIndexChanged.connect(self.on_team_changed)
        
        # Game selection
        game_label = QLabel('Select Games (Ctrl+Click for multiple):')
        game_label.setFont(QFont('', 9, QFont.Bold))
        game_label.setStyleSheet("color: #333;")
        game_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.game_list = QListWidget()
        self.game_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.game_list.setMinimumWidth(400)
        self.game_list.setMaximumHeight(100)
        self.game_list.setStyleSheet("""
            QListWidget {
                background: white;
                border: 2px solid #ddd;
                border-radius: 4px;
                font-size: 14px;
            }
            QListWidget::item {
                padding: 2px;
            }
            QListWidget::item:selected {
                background: #667eea;
                color: white;
            }
            QListWidget::item:hover {
                background: #e9ecef;
            }
        """)
        self.game_list.itemSelectionChanged.connect(self.on_games_changed)
        
        controls_layout.addWidget(team_label)
        controls_layout.addWidget(self.team_combo, alignment=Qt.AlignTop)
        controls_layout.addWidget(game_label)
        controls_layout.addWidget(self.game_list)
        controls_layout.addStretch()
        
        # Add close button
        self.btn_close = QPushButton("Close")
        self.btn_close.setMinimumSize(100, 40)
        self.btn_close.setStyleSheet("""
            QPushButton {
                background: white;
                color: #333;
                border: 2px solid #ddd;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #f8f9fa;
                border-color: #667eea;
            }
            QPushButton:pressed {
                background: #e9ecef;
            }
        """)
        self.btn_close.clicked.connect(self.close)
        controls_layout.addWidget(self.btn_close)
        
        main_layout.addWidget(controls_widget)
        
        # Tab widget for reports
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                border-radius: 4px;
                background: white;
            }
            QTabBar::tab {
                background: #f8f9fa;
                color: #666;
                padding: 8px 16px;
                border: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: white;
                color: #667eea;
                border-bottom: 2px solid #667eea;
            }
            QTabBar::tab:hover {
                background: #e9ecef;
            }
        """)
        
        # Report 1: Passing, Serve-Receive, Serve
        self.report1_table = self.create_report1_table()
        self.tabs.addTab(self.report1_table, 'Passing & Serve-Receive & Serve')
        
        # Report 2: Attacking, Setting, Blocking
        self.report2_table = self.create_report2_table()
        self.tabs.addTab(self.report2_table, 'Attacking & Setting & Blocking')
        
        main_layout.addWidget(self.tabs)
        
        # Set background
        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #667eea, stop:1 #764ba2);
                border: none;
            }
            QWidget {
                background: transparent;
            }
        """)
        
    def create_report1_table(self):
        table = QTableWidget()
        table.setColumnCount(16)
        
        # Hide the default horizontal header - we'll use table rows as headers
        table.horizontalHeader().setVisible(False)
        
        # Style the table
        table.setStyleSheet("""
            QTableWidget {
                background: white;
                border: none;
                gridline-color: #e9ecef;
            }
            QTableWidget::item {
                padding: 3px;
                border-right: 1px solid #e9ecef;
            }
        """)
        
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        
        # Make columns resizable and responsive
        for i in range(16):
            table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
            table.horizontalHeader().resizeSection(i, 80)
        
        # Make table responsive
        table.horizontalHeader().setStretchLastSection(False)
        
        return table
        
    def create_report2_table(self):
        table = QTableWidget()
        table.setColumnCount(12)
        
        # Hide the default horizontal header - we'll use table rows as headers
        table.horizontalHeader().setVisible(False)
        
        # Style the table (same as report1)
        table.setStyleSheet("""
            QTableWidget {
                background: white;
                border: 1px solid #ddd;
                gridline-color: #e9ecef;
            }
            QTableWidget::item {
                padding: 5px;
                border-right: 1px solid #e9ecef;
            }
        """)
        
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        
        # Make columns resizable and responsive
        for i in range(12):
            table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
            table.horizontalHeader().resizeSection(i, 80)
        
        # Make table responsive
        table.horizontalHeader().setStretchLastSection(False)
        
        return table
        
    def load_teams(self):
        if not self.db.conn:
            self.db.connect()
        cursor = self.db.conn.cursor()
        teams = cursor.execute('SELECT team_id, name FROM teams ORDER BY name').fetchall()
        
        self.team_combo.clear()
        self.team_combo.addItem('-- Select a Team --', None)
        for team in teams:
            self.team_combo.addItem(team['name'], team['team_id'])
            
    def on_team_changed(self):
        team_id = self.team_combo.currentData()
        self.selected_team_id = team_id
        self.selected_game_ids = []
        self.game_list.clear()
        
        if team_id:
            self.load_games(team_id)
        else:
            self.clear_tables()
            
    def load_games(self, team_id):
        if not self.db.conn:
            self.db.connect()
        cursor = self.db.conn.cursor()
        games = cursor.execute(
            'SELECT game_id, game_date, team_us_id, team_them_id, notes FROM games WHERE team_us_id = %s OR team_them_id = %s ORDER BY game_date DESC',
            (team_id, team_id)
        ).fetchall()
        
        self.game_list.clear()
        for game in games:
            from datetime import datetime
            try:
                # Try parsing ISO format
                if 'T' in game['game_date']:
                    date_obj = datetime.fromisoformat(game['game_date'].replace(' ', 'T'))
                else:
                    # Try parsing space-separated format
                    date_obj = datetime.strptime(game['game_date'], '%Y-%m-%d %H:%M:%S')
                date_str = date_obj.strftime('%Y-%m-%d')
            except:
                date_str = game['game_date'][:10] if len(game['game_date']) >= 10 else game['game_date']
            
            # Extract opponent alias from notes field
            notes = game['notes'] if game['notes'] is not None else ''
            opponent_display = "Opp1"  # Default
            if notes:
                # Check if notes contains "Opponent: " prefix
                if notes.startswith("Opponent: "):
                    opponent_display = notes.replace("Opponent: ", "").strip()
                else:
                    opponent_display = notes.strip()
            
            item_text = f'Game {game["game_id"]} - {date_str} ({opponent_display})'
            self.game_list.addItem(item_text)
            self.game_list.item(self.game_list.count() - 1).setData(Qt.UserRole, game['game_id'])
            
    def on_games_changed(self):
        selected_items = self.game_list.selectedItems()
        self.selected_game_ids = [item.data(Qt.UserRole) for item in selected_items]
        
        if self.selected_game_ids and self.selected_team_id:
            self.load_stats()
        else:
            self.clear_tables()
            
    def load_stats(self):
        if not self.selected_team_id or not self.selected_game_ids:
            return
        
        if not self.db.conn:
            self.db.connect()
        cursor = self.db.conn.cursor()
        
        # Get players and stats - ONLY for players on the selected team
        # Filter by team_id to ensure we only get players from the selected team
        placeholders = ','.join('%s' * len(self.selected_game_ids))
        query = f'''
            SELECT 
                p.player_id,
                p.player_number,
                p.name,
                ps.receive_attempts,
                ps.receive_0,
                ps.receive_1,
                ps.receive_2,
                ps.receive_3,
                ps.receive_avg_rating,
                ps.attack_attempts,
                ps.attack_kills,
                ps.attack_errors,
                ps.attack_kill_pct,
                ps.attack_hitting_pct,
                ps.attack_efficiency,
                ps.set_attempts,
                ps.set_assists,
                ps.serve_attempts,
                ps.serve_aces,
                ps.serve_errors,
                ps.serve_ace_pct,
                ps.serve_in_pct,
                ps.dig_attempts,
                ps.dig_successful,
                ps.block_solo
            FROM players p
            LEFT JOIN player_stats ps ON p.player_id = ps.player_id 
                AND ps.game_id IN ({placeholders})
            WHERE p.team_id = %s
            ORDER BY CAST(p.player_number AS INTEGER), p.player_number
        '''
        
        # Execute query with selected game IDs and team ID
        # This ensures we only get players from the selected team
        players = cursor.execute(query, self.selected_game_ids + [self.selected_team_id]).fetchall()
        
        # Calculate team totals - ONLY for players on the selected team
        # Filter by team_id to ensure totals only include stats from the selected team
        totals_query = f'''
            SELECT 
                SUM(ps.receive_attempts) as receive_attempts,
                SUM(ps.receive_0) as receive_0,
                SUM(ps.receive_1) as receive_1,
                SUM(ps.receive_2) as receive_2,
                SUM(ps.receive_3) as receive_3,
                CASE 
                    WHEN SUM(ps.receive_attempts) > 0 
                    THEN (SUM(ps.receive_1) * 1.0 + SUM(ps.receive_2) * 2.0 + SUM(ps.receive_3) * 3.0) / SUM(ps.receive_attempts)
                    ELSE 0.0
                END as receive_avg_rating,
                SUM(ps.attack_attempts) as attack_attempts,
                SUM(ps.attack_kills) as attack_kills,
                SUM(ps.attack_errors) as attack_errors,
                SUM(ps.attack_kills) * 100.0 / NULLIF(SUM(ps.attack_attempts), 0) as attack_kill_pct,
                (SUM(ps.attack_kills) - SUM(ps.attack_errors)) * 100.0 / NULLIF(SUM(ps.attack_attempts), 0) as attack_hitting_pct,
                (SUM(ps.attack_kills) - SUM(ps.attack_errors)) * 100.0 / NULLIF(SUM(ps.attack_attempts), 0) as attack_efficiency,
                SUM(ps.set_attempts) as set_attempts,
                SUM(ps.set_assists) as set_assists,
                SUM(ps.serve_attempts) as serve_attempts,
                SUM(ps.serve_aces) as serve_aces,
                SUM(ps.serve_errors) as serve_errors,
                SUM(ps.serve_aces) * 100.0 / NULLIF(SUM(ps.serve_attempts), 0) as serve_ace_pct,
                (SUM(ps.serve_attempts) - SUM(ps.serve_errors)) * 100.0 / NULLIF(SUM(ps.serve_attempts), 0) as serve_in_pct,
                SUM(ps.dig_attempts) as dig_attempts,
                SUM(ps.dig_successful) as dig_successful,
                SUM(ps.block_solo) as block_solo
            FROM player_stats ps
            INNER JOIN players p ON ps.player_id = p.player_id
            WHERE p.team_id = %s AND ps.game_id IN ({placeholders})
        '''
        
        # Execute totals query with team ID and selected game IDs
        # This ensures totals only include stats from players on the selected team
        totals = cursor.execute(totals_query, [self.selected_team_id] + self.selected_game_ids).fetchone()
        
        # Aggregate stats by player
        # Note: All players in the result set are already filtered by team_id in the query
        player_stats = {}
        for player in players:
            pid = player['player_id']
            # Only process players (all should already be from selected team due to WHERE clause)
            if pid not in player_stats:
                player_stats[pid] = {
                    'player_id': pid,
                    'player_number': player['player_number'],
                    'name': player['name'],
                    'receive_attempts': 0,
                    'receive_0': 0,
                    'receive_1': 0,
                    'receive_2': 0,
                    'receive_3': 0,
                    'receive_avg_rating': 0.0,
                    'attack_attempts': 0,
                    'attack_kills': 0,
                    'attack_errors': 0,
                    'attack_kill_pct': 0.0,
                    'attack_hitting_pct': 0.0,
                    'attack_efficiency': 0.0,
                    'set_attempts': 0,
                    'set_assists': 0,
                    'serve_attempts': 0,
                    'serve_aces': 0,
                    'serve_errors': 0,
                    'serve_ace_pct': 0.0,
                    'serve_in_pct': 0.0,
                    'dig_attempts': 0,
                    'dig_successful': 0,
                    'block_solo': 0
                }
            
            # Aggregate stats
            for key in ['receive_attempts', 'receive_0', 'receive_1', 'receive_2', 'receive_3',
                       'attack_attempts', 'attack_kills', 'attack_errors',
                       'set_attempts', 'set_assists',
                       'serve_attempts', 'serve_aces', 'serve_errors',
                       'dig_attempts', 'dig_successful', 'block_solo']:
                if player[key] is not None:
                    player_stats[pid][key] += player[key]
        
        # Calculate percentages and averages
        for pid, stats in player_stats.items():
            if stats['receive_attempts'] > 0:
                stats['receive_avg_rating'] = (
                    stats['receive_0'] * 0 + 
                    stats['receive_1'] * 1 + 
                    stats['receive_2'] * 2 + 
                    stats['receive_3'] * 3
                ) / stats['receive_attempts']
            
            if stats['attack_attempts'] > 0:
                stats['attack_kill_pct'] = (stats['attack_kills'] / stats['attack_attempts']) * 100
                stats['attack_hitting_pct'] = ((stats['attack_kills'] - stats['attack_errors']) / stats['attack_attempts']) * 100
                stats['attack_efficiency'] = ((stats['attack_kills'] - stats['attack_errors']) / stats['attack_attempts']) * 100
            
            if stats['serve_attempts'] > 0:
                stats['serve_ace_pct'] = (stats['serve_aces'] / stats['serve_attempts']) * 100
                stats['serve_in_pct'] = ((stats['serve_attempts'] - stats['serve_errors']) / stats['serve_attempts']) * 100
        
        # Sort by jersey number
        players_list = sorted(player_stats.values(), 
                            key=lambda x: int(x['player_number']) if x['player_number'].isdigit() else 999)
        
        # Format totals
        team_totals = {
            'receive_attempts': totals['receive_attempts'] or 0,
            'receive_0': totals['receive_0'] or 0,
            'receive_1': totals['receive_1'] or 0,
            'receive_2': totals['receive_2'] or 0,
            'receive_3': totals['receive_3'] or 0,
            'receive_avg_rating': round(totals['receive_avg_rating'] or 0.0, 2),
            'attack_attempts': totals['attack_attempts'] or 0,
            'attack_kills': totals['attack_kills'] or 0,
            'attack_errors': totals['attack_errors'] or 0,
            'attack_kill_pct': round(totals['attack_kill_pct'] or 0.0, 1),
            'attack_hitting_pct': round(totals['attack_hitting_pct'] or 0.0, 1),
            'attack_efficiency': round(totals['attack_efficiency'] or 0.0, 1),
            'set_attempts': totals['set_attempts'] or 0,
            'set_assists': totals['set_assists'] or 0,
            'serve_attempts': totals['serve_attempts'] or 0,
            'serve_aces': totals['serve_aces'] or 0,
            'serve_errors': totals['serve_errors'] or 0,
            'serve_ace_pct': round(totals['serve_ace_pct'] or 0.0, 1),
            'serve_in_pct': round(totals['serve_in_pct'] or 0.0, 1),
            'dig_attempts': totals['dig_attempts'] or 0,
            'dig_successful': totals['dig_successful'] or 0,
            'block_solo': totals['block_solo'] or 0
        }
        
        # Populate tables
        self.populate_report1(players_list, team_totals)
        self.populate_report2(players_list, team_totals)
        
    def populate_report1(self, players, totals):
        table = self.report1_table
        if not players:
            # Set header rows only
            table.setRowCount(2)
            return
        
        # Set up header rows + data rows + summary row
        table.setRowCount(2 + len(players) + 1)  # 2 header rows + players + summary
        
        # Section header row (row 0)
        section_headers = ['', '', 'Passing', '', '', 'Serve-Receive', '', '', '', '', '', 'Serve', '', '', '', '']
        for col, header in enumerate(section_headers):
            item = QTableWidgetItem(header)
            item.setTextAlignment(Qt.AlignCenter)
            font = item.font()
            font.setBold(True)
            font.setPointSize(10)
            item.setFont(font)
            item.setBackground(QColor(220, 220, 220))
            table.setItem(0, col, item)
        
        # Merge cells for section headers
        table.setSpan(0, 2, 1, 3)  # Passing spans 3 columns
        table.setSpan(0, 5, 1, 6)  # Serve-Receive spans 6 columns
        table.setSpan(0, 11, 1, 5)  # Serve spans 5 columns
        
        # Column header row (row 1)
        headers = [
            '#', 'Player',
            'Att', 'Successful', 'Success %',  # Passing
            'Att', '0', '1', '2', '3', 'Avg',  # Serve-Receive
            'Att', 'Aces', 'Errors', 'Ace %', 'In %'  # Serve
        ]
        for col, header in enumerate(headers):
            item = QTableWidgetItem(header)
            item.setTextAlignment(Qt.AlignCenter)
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            item.setBackground(QColor(240, 240, 240))
            table.setItem(1, col, item)
        
        # Data rows start at row 2
        data_start_row = 2
        
        for idx, player in enumerate(players):
            row = data_start_row + idx
            dig_success_pct = f"{(player['dig_successful'] / player['dig_attempts']):.3f}" if player['dig_attempts'] > 0 else '0.000'
            
            items = [
                player['player_number'],
                player['name'],
                str(player['dig_attempts']),
                str(player['dig_successful']),
                dig_success_pct,
                str(player['receive_attempts']),
                str(player['receive_0']),
                str(player['receive_1']),
                str(player['receive_2']),
                str(player['receive_3']),
                f"{player['receive_avg_rating']:.2f}",
                str(player['serve_attempts']),
                str(player['serve_aces']),
                str(player['serve_errors']),
                f"{(player['serve_ace_pct'] / 100):.3f}",
                f"{(player['serve_in_pct'] / 100):.3f}"
            ]
            
            for col, value in enumerate(items):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if col in [0, 1]:  # Jersey number and name
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                if col in [4, 14, 15]:  # Percentage columns
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                    item.setForeground(QColor(102, 126, 234))
                table.setItem(row, col, item)
        
        # Summary row
        row = data_start_row + len(players)
        dig_success_pct = f"{(totals['dig_successful'] / totals['dig_attempts']):.3f}" if totals['dig_attempts'] > 0 else '0.000'
        
        summary_items = [
            'TOTAL',
            'TEAM',
            str(totals['dig_attempts']),
            str(totals['dig_successful']),
            dig_success_pct,
            str(totals['receive_attempts']),
            str(totals['receive_0']),
            str(totals['receive_1']),
            str(totals['receive_2']),
            str(totals['receive_3']),
            f"{totals['receive_avg_rating']:.2f}",
            str(totals['serve_attempts']),
            str(totals['serve_aces']),
            str(totals['serve_errors']),
            f"{(totals['serve_ace_pct'] / 100):.3f}",
            f"{(totals['serve_in_pct'] / 100):.3f}"
        ]
        
        for col, value in enumerate(summary_items):
            item = QTableWidgetItem(str(value))
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            item.setBackground(QColor(248, 249, 250))
            if col in [0, 1]:
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            if col in [4, 14, 15]:
                item.setForeground(QColor(102, 126, 234))
            table.setItem(row, col, item)
            
    def populate_report2(self, players, totals):
        table = self.report2_table
        if not players:
            # Set header rows only
            table.setRowCount(2)
            return
        
        # Set up header rows + data rows + summary row
        table.setRowCount(2 + len(players) + 1)  # 2 header rows + players + summary
        
        # Section header row (row 0)
        section_headers = ['', '', 'Attacking', '', '', '', '', '', 'Setting', '', '', 'Blocking']
        for col, header in enumerate(section_headers):
            item = QTableWidgetItem(header)
            item.setTextAlignment(Qt.AlignCenter)
            font = item.font()
            font.setBold(True)
            font.setPointSize(10)
            item.setFont(font)
            item.setBackground(QColor(220, 220, 220))
            table.setItem(0, col, item)
        
        # Merge cells for section headers
        table.setSpan(0, 2, 1, 6)  # Attacking spans 6 columns
        table.setSpan(0, 8, 1, 3)  # Setting spans 3 columns
        table.setSpan(0, 11, 1, 1)  # Blocking spans 1 column
        
        # Column header row (row 1)
        headers = [
            '#', 'Player',
            'Att', 'Kills', 'Errors', 'Kill %', 'Hit %', 'Eff',  # Attacking
            'Att', 'Assists', 'Assist %',  # Setting
            'Solo'  # Blocking
        ]
        for col, header in enumerate(headers):
            item = QTableWidgetItem(header)
            item.setTextAlignment(Qt.AlignCenter)
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            item.setBackground(QColor(240, 240, 240))
            table.setItem(1, col, item)
        
        # Data rows start at row 2
        data_start_row = 2
        
        for idx, player in enumerate(players):
            row = data_start_row + idx
            set_assist_pct = f"{(player['set_assists'] / player['set_attempts']):.3f}" if player['set_attempts'] > 0 else '0.000'
            
            items = [
                player['player_number'],
                player['name'],
                str(player['attack_attempts']),
                str(player['attack_kills']),
                str(player['attack_errors']),
                f"{(player['attack_kill_pct'] / 100):.3f}",
                f"{(player['attack_hitting_pct'] / 100):.3f}",
                f"{(player['attack_efficiency'] / 100):.3f}",
                str(player['set_attempts']),
                str(player['set_assists']),
                set_assist_pct,
                str(player['block_solo'])
            ]
            
            for col, value in enumerate(items):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if col in [0, 1]:  # Jersey number and name
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                if col in [5, 6, 7, 10]:  # Percentage columns
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                    item.setForeground(QColor(102, 126, 234))
                table.setItem(row, col, item)
        
        # Summary row
        row = data_start_row + len(players)
        set_assist_pct = f"{(totals['set_assists'] / totals['set_attempts']):.3f}" if totals['set_attempts'] > 0 else '0.000'
        
        summary_items = [
            'TOTAL',
            'TEAM',
            str(totals['attack_attempts']),
            str(totals['attack_kills']),
            str(totals['attack_errors']),
            f"{(totals['attack_kill_pct'] / 100):.3f}",
            f"{(totals['attack_hitting_pct'] / 100):.3f}",
            f"{(totals['attack_efficiency'] / 100):.3f}",
            str(totals['set_attempts']),
            str(totals['set_assists']),
            set_assist_pct,
            str(totals['block_solo'])
        ]
        
        for col, value in enumerate(summary_items):
            item = QTableWidgetItem(str(value))
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            item.setBackground(QColor(248, 249, 250))
            if col in [0, 1]:
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            if col in [5, 6, 7, 10]:
                item.setForeground(QColor(102, 126, 234))
            table.setItem(row, col, item)
            
    def clear_tables(self):
        # Keep header rows when clearing
        self.report1_table.setRowCount(2)
        self.report2_table.setRowCount(2)


def main():
    app = QApplication(sys.argv)
    from database import VideoStatsDB
    db = VideoStatsDB()
    db.initialize_database()
    db.connect()
    window = StatsApp(db)
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()


