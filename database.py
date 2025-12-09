"""
SQLite database structure for VideoStats volleyball tracking application.
Tracks player ball contacts from serve through rally end.
"""

import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional


class VideoStatsDB:
    """Database manager for VideoStats volleyball tracking."""
    
    def __init__(self, db_path: str = "videostats.db"):
        self.db_path = db_path
        self.conn = None
        
    def connect(self):
        """Connect to the database."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        return self.conn
    
    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def create_tables(self):
        """Create all database tables."""
        if not self.conn:
            self.connect()
        
        cursor = self.conn.cursor()
        
        # Teams table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS teams (
                team_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Players table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS players (
                player_id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER,
                player_number TEXT NOT NULL,
                name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (team_id) REFERENCES teams(team_id),
                UNIQUE(team_id, player_number)
            )
        """)
        
        # Games table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS games (
                game_id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                team_us_id INTEGER NOT NULL,
                team_them_id INTEGER NOT NULL,
                notes TEXT,
                video_file_path TEXT,
                still_image_path TEXT,
                court_corner_tl_x REAL,
                court_corner_tl_y REAL,
                court_corner_tr_x REAL,
                court_corner_tr_y REAL,
                court_corner_bl_x REAL,
                court_corner_bl_y REAL,
                court_corner_br_x REAL,
                court_corner_br_y REAL,
                court_centerline_top_x REAL,
                court_centerline_top_y REAL,
                court_centerline_bottom_x REAL,
                court_centerline_bottom_y REAL,
                court_y200_left_x REAL,
                court_y200_left_y REAL,
                court_y200_right_x REAL,
                court_y200_right_y REAL,
                court_y400_left_x REAL,
                court_y400_left_y REAL,
                court_y400_right_x REAL,
                court_y400_right_y REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (team_us_id) REFERENCES teams(team_id),
                FOREIGN KEY (team_them_id) REFERENCES teams(team_id),
                CHECK (team_us_id != team_them_id)
            )
        """)
        
        # Game Players table - links players to specific games
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS game_players (
                game_player_id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER NOT NULL,
                team_id INTEGER NOT NULL,
                player_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (game_id) REFERENCES games(game_id) ON DELETE CASCADE,
                FOREIGN KEY (team_id) REFERENCES teams(team_id),
                FOREIGN KEY (player_id) REFERENCES players(player_id),
                UNIQUE(game_id, team_id, player_id)
            )
        """)
        
        # Rallies table - tracks each rally from serve to point
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rallies (
                rally_id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER NOT NULL,
                rally_number INTEGER NOT NULL,
                serving_team_id INTEGER NOT NULL,
                point_winner_id INTEGER,
                rally_start_time TIMESTAMP,
                rally_end_time TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (game_id) REFERENCES games(game_id),
                FOREIGN KEY (serving_team_id) REFERENCES teams(team_id),
                FOREIGN KEY (point_winner_id) REFERENCES teams(team_id),
                UNIQUE(game_id, rally_number)
            )
        """)
        
        # Contacts table - tracks each ball contact in a rally
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contacts (
                contact_id INTEGER PRIMARY KEY AUTOINCREMENT,
                rally_id INTEGER NOT NULL,
                sequence_number INTEGER NOT NULL,
                player_id INTEGER,
                contact_type TEXT NOT NULL CHECK(contact_type IN ('serve', 'pass', 'set', 'attack', 'block', 'receive', 'freeball', 'down', 'net', 'fault')),
                team_id INTEGER NOT NULL,
                x INTEGER,
                y INTEGER,
                timecode INTEGER,
                outcome TEXT DEFAULT 'continue' CHECK(outcome IN ('continue', 'ace', 'kill', 'error', 'down', 'stuff', 'assist')),
                rating INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (rally_id) REFERENCES rallies(rally_id),
                FOREIGN KEY (player_id) REFERENCES players(player_id),
                FOREIGN KEY (team_id) REFERENCES teams(team_id)
            )
        """)
        
        # Player Statistics table - tracks statistics by game and by player
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS player_stats (
                stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER NOT NULL,
                player_id INTEGER NOT NULL,
                -- Receive statistics
                receive_attempts INTEGER DEFAULT 0,
                receive_0 INTEGER DEFAULT 0,
                receive_1 INTEGER DEFAULT 0,
                receive_2 INTEGER DEFAULT 0,
                receive_3 INTEGER DEFAULT 0,
                receive_avg_rating REAL DEFAULT 0.0,
                -- Attack statistics
                attack_attempts INTEGER DEFAULT 0,
                attack_kills INTEGER DEFAULT 0,
                attack_errors INTEGER DEFAULT 0,
                attack_kill_pct REAL DEFAULT 0.0,
                attack_hitting_pct REAL DEFAULT 0.0,
                attack_efficiency REAL DEFAULT 0.0,
                -- Set statistics
                set_attempts INTEGER DEFAULT 0,
                set_assists INTEGER DEFAULT 0,
                -- Serve statistics
                serve_attempts INTEGER DEFAULT 0,
                serve_aces INTEGER DEFAULT 0,
                serve_errors INTEGER DEFAULT 0,
                serve_ace_pct REAL DEFAULT 0.0,
                serve_in_pct REAL DEFAULT 0.0,
                -- Dig statistics
                dig_attempts INTEGER DEFAULT 0,
                dig_successful INTEGER DEFAULT 0,
                -- Block statistics
                block_solo INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (game_id) REFERENCES games(game_id) ON DELETE CASCADE,
                FOREIGN KEY (player_id) REFERENCES players(player_id),
                UNIQUE(game_id, player_id)
            )
        """)
        
        # Positions table (static - immutable position definitions)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                number INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                abbrev TEXT NOT NULL,
                row TEXT NOT NULL CHECK(row IN ('Front', 'Back')),
                side TEXT NOT NULL CHECK(side IN ('Left', 'Middle', 'Right')),
                x INTEGER NOT NULL,
                y INTEGER NOT NULL
            )
        """)
        
        # Active lineup table - who is currently in each position
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS active_lineup (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER NOT NULL REFERENCES teams(team_id),
                position_number INTEGER NOT NULL REFERENCES positions(number),
                player_id INTEGER NOT NULL REFERENCES players(player_id),
                role_code TEXT NOT NULL,
                is_server BOOLEAN DEFAULT 0,
                placed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(team_id, position_number)
            )
        """)
        
        # Rotation state table - current rotation index and term of service
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rotation_state (
                team_id INTEGER PRIMARY KEY REFERENCES teams(team_id),
                rotation_order TEXT NOT NULL, -- JSON array e.g. [1,6,5,4,3,2]
                rotation_index INTEGER NOT NULL DEFAULT 0,
                serving BOOLEAN DEFAULT 0,
                term_of_service_start TIMESTAMP NULL
            )
        """)
        
        # Events log table (generic)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER NOT NULL REFERENCES teams(team_id),
                event_type TEXT NOT NULL CHECK(event_type IN ('rotation', 'substitution', 'libero', 'server_change', 'initial_setup')),
                payload TEXT NOT NULL, -- JSON
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Substitutions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS substitutions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER NOT NULL REFERENCES teams(team_id),
                out_player_id INTEGER NOT NULL REFERENCES players(player_id),
                in_player_id INTEGER NOT NULL REFERENCES players(player_id),
                out_position INTEGER NULL,
                in_position INTEGER NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Libero actions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS libero_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER NOT NULL REFERENCES teams(team_id),
                libero_id INTEGER NOT NULL REFERENCES players(player_id),
                replaced_player_id INTEGER NOT NULL REFERENCES players(player_id),
                replaced_position INTEGER NOT NULL,
                action TEXT NOT NULL CHECK(action IN ('enter', 'exit')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes for better query performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_contacts_rally ON contacts(rally_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_contacts_player ON contacts(player_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_contacts_type ON contacts(contact_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rallies_game ON rallies(game_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_players_team ON players(team_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_game_players_game ON game_players(game_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_game_players_team ON game_players(team_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_game_players_player ON game_players(player_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_player_stats_game ON player_stats(game_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_player_stats_player ON player_stats(player_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_active_lineup_team ON active_lineup(team_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_active_lineup_player ON active_lineup(player_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_team ON events(team_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_substitutions_team ON substitutions(team_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_libero_actions_team ON libero_actions(team_id)")
        
        # Populate positions table with static data if empty
        cursor.execute("SELECT COUNT(*) FROM positions")
        if cursor.fetchone()[0] == 0:
            positions_data = [
                (1, 'Right Back', 'RB', 'Back', 'Right', 299, 0),
                (2, 'Right Front', 'RF', 'Front', 'Right', 299, 299),
                (3, 'Middle Front', 'MF', 'Front', 'Middle', 150, 299),
                (4, 'Left Front', 'LF', 'Front', 'Left', 0, 299),
                (5, 'Left Back', 'LB', 'Back', 'Left', 0, 0),
                (6, 'Middle Back', 'MB', 'Back', 'Middle', 150, 0)
            ]
            cursor.executemany(
                "INSERT INTO positions (number, name, abbrev, row, side, x, y) VALUES (?, ?, ?, ?, ?, ?, ?)",
                positions_data
            )
        
        self.conn.commit()
        print("Database tables created successfully!")
    
    def initialize_database(self):
        """Initialize the database with tables."""
        self.connect()
        self.create_tables()
        self.add_constraints_to_existing_tables()
        self.close()
    
    def add_constraints_to_existing_tables(self):
        """Add constraints to existing tables if they don't have them."""
        cursor = self.conn.cursor()
        
        # Check if games table exists and if it has the constraint
        # SQLite doesn't support adding CHECK constraints to existing tables easily
        # So we'll rely on application-level validation for existing databases
        # New databases will have the constraint from CREATE TABLE
        
        # Verify existing games don't violate the constraint
        cursor.execute("""
            SELECT game_id, team_us_id, team_them_id 
            FROM games 
            WHERE team_us_id = team_them_id
        """)
        violations = cursor.fetchall()
        if violations:
            print(f"Warning: Found {len(violations)} games with duplicate teams. These should be fixed manually.")
        
        # Migrate player_number from INTEGER to TEXT if needed
        # Check if players table exists and has INTEGER player_number
        cursor.execute("""
            SELECT sql FROM sqlite_master 
            WHERE type='table' AND name='players'
        """)
        result = cursor.fetchone()
        if result and result[0] and 'player_number INTEGER' in result[0]:
            # Need to migrate - SQLite doesn't support ALTER COLUMN, so recreate table
            print("Migrating player_number column from INTEGER to TEXT...")
            try:
                # Create new table with TEXT column
                cursor.execute("""
                    CREATE TABLE players_new (
                        player_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        team_id INTEGER,
                        player_number TEXT NOT NULL,
                        name TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (team_id) REFERENCES teams(team_id),
                        UNIQUE(team_id, player_number)
                    )
                """)
                
                # Copy data (SQLite will convert INTEGER to TEXT automatically)
                cursor.execute("""
                    INSERT INTO players_new 
                    SELECT player_id, team_id, CAST(player_number AS TEXT), name, created_at
                    FROM players
                """)
                
                # Drop old table and rename new one
                cursor.execute("DROP TABLE players")
                cursor.execute("ALTER TABLE players_new RENAME TO players")
                
                # Recreate indexes
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_players_team ON players(team_id)")
                
                self.conn.commit()
                print("Migration completed successfully!")
            except Exception as e:
                self.conn.rollback()
                print(f"Migration failed: {e}. You may need to manually migrate the database.")
        
        # Migrate contact_type constraint if needed
        # Check if contacts table exists and has old constraint
        cursor.execute("""
            SELECT sql FROM sqlite_master 
            WHERE type='table' AND name='contacts'
        """)
        result = cursor.fetchone()
        if result and result[0]:
            # Check if it has the old constraint with 'opp' or missing 'receive'/'freeball'/'down'
            sql = result[0]
            if "'opp'" in sql or "'receive'" not in sql or "'freeball'" not in sql or "'down'" not in sql or "'net'" not in sql or "'fault'" not in sql:
                print("Migrating contact_type constraint in contacts table...")
                try:
                    # Create new table with updated constraint
                    cursor.execute("""
                        CREATE TABLE contacts_new (
                            contact_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            rally_id INTEGER NOT NULL,
                            sequence_number INTEGER NOT NULL,
                            player_id INTEGER,
                            contact_type TEXT NOT NULL CHECK(contact_type IN ('serve', 'pass', 'set', 'attack', 'block', 'receive', 'freeball', 'down', 'net', 'fault')),
                            team_id INTEGER NOT NULL,
                            x INTEGER,
                            y INTEGER,
                            timecode INTEGER,
                            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (rally_id) REFERENCES rallies(rally_id),
                            FOREIGN KEY (player_id) REFERENCES players(player_id),
                            FOREIGN KEY (team_id) REFERENCES teams(team_id)
                        )
                    """)
                    
                    # Copy data, but filter out any 'opp' contact_types (they shouldn't exist, but just in case)
                    # Include x, y, and timecode columns if they exist in the old table
                    cursor.execute("PRAGMA table_info(contacts)")
                    old_columns = [row[1] for row in cursor.fetchall()]
                    has_x = 'x' in old_columns
                    has_y = 'y' in old_columns
                    has_timecode = 'timecode' in old_columns
                    
                    # Build SELECT statement based on which columns exist
                    select_cols = "contact_id, rally_id, sequence_number, player_id, "
                    select_cols += "CASE WHEN contact_type = 'opp' THEN 'receive' ELSE contact_type END as contact_type, "
                    select_cols += "team_id"
                    if has_x:
                        select_cols += ", x"
                    else:
                        select_cols += ", NULL as x"
                    if has_y:
                        select_cols += ", y"
                    else:
                        select_cols += ", NULL as y"
                    if has_timecode:
                        select_cols += ", timecode"
                    else:
                        select_cols += ", NULL as timecode"
                    select_cols += ", timestamp, created_at"
                    
                    cursor.execute(f"""
                        INSERT INTO contacts_new 
                        SELECT {select_cols}
                        FROM contacts
                        WHERE contact_type IN ('serve', 'pass', 'set', 'attack', 'block', 'receive', 'freeball', 'down', 'net', 'fault', 'opp')
                    """)
                    
                    # Drop old table and rename new one
                    cursor.execute("DROP TABLE contacts")
                    cursor.execute("ALTER TABLE contacts_new RENAME TO contacts")
                    
                    # Recreate indexes
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_contacts_rally ON contacts(rally_id)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_contacts_player ON contacts(player_id)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_contacts_type ON contacts(contact_type)")
                    
                    self.conn.commit()
                    print("Contact type constraint migration completed successfully!")
                except Exception as e:
                    self.conn.rollback()
                    print(f"Migration failed: {e}. You may need to manually migrate the database.")
        
        # Add x, y coordinate columns to contacts table if they don't exist
        cursor.execute("PRAGMA table_info(contacts)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'x' not in columns:
            print("Adding x coordinate column to contacts table...")
            try:
                cursor.execute("ALTER TABLE contacts ADD COLUMN x INTEGER")
                self.conn.commit()
                print("x coordinate column added successfully!")
            except Exception as e:
                print(f"Failed to add x column: {e}")
        if 'y' not in columns:
            print("Adding y coordinate column to contacts table...")
            try:
                cursor.execute("ALTER TABLE contacts ADD COLUMN y INTEGER")
                self.conn.commit()
                print("y coordinate column added successfully!")
            except Exception as e:
                print(f"Failed to add y column: {e}")
        
        # Add timecode column to contacts table if it doesn't exist
        # Need to refresh columns list after adding x and y
        cursor.execute("PRAGMA table_info(contacts)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'timecode' not in columns:
            print("Adding timecode column to contacts table...")
            try:
                cursor.execute("ALTER TABLE contacts ADD COLUMN timecode INTEGER")
                self.conn.commit()
                print("timecode column added successfully!")
            except Exception as e:
                print(f"Failed to add timecode column: {e}")
        
        # Add rating column to contacts table if it doesn't exist
        cursor.execute("PRAGMA table_info(contacts)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'rating' not in columns:
            print("Adding rating column to contacts table...")
            try:
                cursor.execute("ALTER TABLE contacts ADD COLUMN rating INTEGER")
                self.conn.commit()
                print("rating column added successfully!")
            except Exception as e:
                print(f"Failed to add rating column: {e}")
        
        # Add outcome column to contacts table if it doesn't exist
        if 'outcome' not in columns:
            print("Adding outcome column to contacts table...")
            try:
                cursor.execute("ALTER TABLE contacts ADD COLUMN outcome TEXT DEFAULT 'continue' CHECK(outcome IN ('continue', 'ace', 'kill', 'error', 'down', 'stuff'))")
                self.conn.commit()
                print("outcome column added successfully!")
            except Exception as e:
                print(f"Failed to add outcome column: {e}")
        else:
            # Check if the outcome column has the old constraint (without 'stuff' or 'assist')
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='contacts'")
            result = cursor.fetchone()
            if result and result[0]:
                sql = result[0]
                # Check if 'stuff' or 'assist' is missing from the outcome constraint
                if "'stuff'" not in sql or "'assist'" not in sql:
                    missing = []
                    if "'stuff'" not in sql:
                        missing.append("'stuff'")
                    if "'assist'" not in sql:
                        missing.append("'assist'")
                    print(f"Migrating outcome column constraint to include {', '.join(missing)}...")
                    try:
                        # Create new table with updated constraint
                        cursor.execute("""
                            CREATE TABLE contacts_new (
                                contact_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                rally_id INTEGER NOT NULL,
                                sequence_number INTEGER NOT NULL,
                                player_id INTEGER,
                                contact_type TEXT NOT NULL CHECK(contact_type IN ('serve', 'pass', 'set', 'attack', 'block', 'receive', 'freeball', 'down', 'net', 'fault')),
                                team_id INTEGER NOT NULL,
                                x INTEGER,
                                y INTEGER,
                                timecode INTEGER,
                                outcome TEXT DEFAULT 'continue' CHECK(outcome IN ('continue', 'ace', 'kill', 'error', 'down', 'stuff', 'assist')),
                                rating INTEGER,
                                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                FOREIGN KEY (rally_id) REFERENCES rallies(rally_id),
                                FOREIGN KEY (player_id) REFERENCES players(player_id),
                                FOREIGN KEY (team_id) REFERENCES teams(team_id)
                            )
                        """)
                        
                        # Copy data - check if rating column exists in old table
                        cursor.execute("PRAGMA table_info(contacts)")
                        old_columns = [row[1] for row in cursor.fetchall()]
                        has_rating = 'rating' in old_columns
                        
                        select_cols = "contact_id, rally_id, sequence_number, player_id, contact_type, team_id, x, y, timecode, outcome"
                        if has_rating:
                            select_cols += ", rating"
                        else:
                            select_cols += ", NULL as rating"
                        select_cols += ", timestamp, created_at"
                        
                        cursor.execute(f"""
                            INSERT INTO contacts_new 
                            SELECT {select_cols}
                            FROM contacts
                        """)
                        
                        # Drop old table and rename new one
                        cursor.execute("DROP TABLE contacts")
                        cursor.execute("ALTER TABLE contacts_new RENAME TO contacts")
                        
                        # Recreate indexes
                        cursor.execute("CREATE INDEX IF NOT EXISTS idx_contacts_rally ON contacts(rally_id)")
                        cursor.execute("CREATE INDEX IF NOT EXISTS idx_contacts_player ON contacts(player_id)")
                        cursor.execute("CREATE INDEX IF NOT EXISTS idx_contacts_type ON contacts(contact_type)")
                        
                        self.conn.commit()
                        print("Outcome column constraint migration completed successfully!")
                    except Exception as e:
                        self.conn.rollback()
                        print(f"Migration failed: {e}. You may need to manually migrate the database.")
        
        # Add video_file_path column to games table if it doesn't exist
        cursor.execute("PRAGMA table_info(games)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'video_file_path' not in columns:
            print("Adding video_file_path column to games table...")
            try:
                cursor.execute("ALTER TABLE games ADD COLUMN video_file_path TEXT")
                self.conn.commit()
                print("video_file_path column added successfully!")
            except Exception as e:
                print(f"Failed to add video_file_path column: {e}")
        
        # Add still_image_path column to games table if it doesn't exist
        if 'still_image_path' not in columns:
            print("Adding still_image_path column to games table...")
            try:
                cursor.execute("ALTER TABLE games ADD COLUMN still_image_path TEXT")
                self.conn.commit()
                print("still_image_path column added successfully!")
            except Exception as e:
                print(f"Failed to add still_image_path column: {e}")
        
        # Add court boundary columns to games table if they don't exist
        court_columns = [
            'court_corner_tl_x', 'court_corner_tl_y',
            'court_corner_tr_x', 'court_corner_tr_y',
            'court_corner_bl_x', 'court_corner_bl_y',
            'court_corner_br_x', 'court_corner_br_y',
            'court_centerline_top_x', 'court_centerline_top_y',
            'court_centerline_bottom_x', 'court_centerline_bottom_y',
            'court_y200_left_x', 'court_y200_left_y',
            'court_y200_right_x', 'court_y200_right_y',
            'court_y400_left_x', 'court_y400_left_y',
            'court_y400_right_x', 'court_y400_right_y'
        ]
        for col in court_columns:
            if col not in columns:
                print(f"Adding {col} column to games table...")
                try:
                    cursor.execute(f"ALTER TABLE games ADD COLUMN {col} REAL")
                    self.conn.commit()
                    print(f"{col} column added successfully!")
                except Exception as e:
                    print(f"Failed to add {col} column: {e}")
        
        # Add homography_matrix column to games table if it doesn't exist
        if 'homography_matrix' not in columns:
            print("Adding homography_matrix column to games table...")
            try:
                cursor.execute("ALTER TABLE games ADD COLUMN homography_matrix TEXT")
                self.conn.commit()
                print("homography_matrix column added successfully!")
            except Exception as e:
                print(f"Failed to add homography_matrix column: {e}")
        
        # The game_players table will be created automatically if it doesn't exist
        # No migration needed as it's a new table
        
        # Check if player_stats table exists, if not create it
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='player_stats'
        """)
        if not cursor.fetchone():
            print("Creating player_stats table...")
            cursor.execute("""
                CREATE TABLE player_stats (
                    stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_id INTEGER NOT NULL,
                    player_id INTEGER NOT NULL,
                    -- Receive statistics
                    receive_attempts INTEGER DEFAULT 0,
                    receive_0 INTEGER DEFAULT 0,
                    receive_1 INTEGER DEFAULT 0,
                    receive_2 INTEGER DEFAULT 0,
                    receive_3 INTEGER DEFAULT 0,
                    receive_avg_rating REAL DEFAULT 0.0,
                    -- Attack statistics
                    attack_attempts INTEGER DEFAULT 0,
                    attack_kills INTEGER DEFAULT 0,
                    attack_errors INTEGER DEFAULT 0,
                    attack_kill_pct REAL DEFAULT 0.0,
                    attack_hitting_pct REAL DEFAULT 0.0,
                    attack_efficiency REAL DEFAULT 0.0,
                    -- Set statistics
                    set_attempts INTEGER DEFAULT 0,
                    set_assists INTEGER DEFAULT 0,
                    -- Serve statistics
                    serve_attempts INTEGER DEFAULT 0,
                    serve_aces INTEGER DEFAULT 0,
                    serve_errors INTEGER DEFAULT 0,
                    serve_ace_pct REAL DEFAULT 0.0,
                    serve_in_pct REAL DEFAULT 0.0,
                    -- Dig statistics
                    dig_attempts INTEGER DEFAULT 0,
                    dig_successful INTEGER DEFAULT 0,
                    -- Block statistics
                    block_solo INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (game_id) REFERENCES games(game_id) ON DELETE CASCADE,
                    FOREIGN KEY (player_id) REFERENCES players(player_id),
                    UNIQUE(game_id, player_id)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_player_stats_game ON player_stats(game_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_player_stats_player ON player_stats(player_id)")
            self.conn.commit()
            print("player_stats table created successfully!")
        
        # Add new columns to players table for lineup management
        cursor.execute("PRAGMA table_info(players)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'role_code' not in columns:
            print("Adding role_code column to players table...")
            try:
                cursor.execute("ALTER TABLE players ADD COLUMN role_code TEXT")
                self.conn.commit()
                print("role_code column added successfully!")
            except Exception as e:
                print(f"Failed to add role_code column: {e}")
        
        if 'is_active' not in columns:
            print("Adding is_active column to players table...")
            try:
                cursor.execute("ALTER TABLE players ADD COLUMN is_active BOOLEAN DEFAULT 0")
                self.conn.commit()
                print("is_active column added successfully!")
            except Exception as e:
                print(f"Failed to add is_active column: {e}")
        
        if 'jersey' not in columns:
            print("Adding jersey column to players table...")
            try:
                cursor.execute("ALTER TABLE players ADD COLUMN jersey INTEGER")
                self.conn.commit()
                print("jersey column added successfully!")
            except Exception as e:
                print(f"Failed to add jersey column: {e}")
        
        # Ensure positions table is populated
        cursor.execute("SELECT COUNT(*) FROM positions")
        if cursor.fetchone()[0] == 0:
            print("Populating positions table...")
            positions_data = [
                (1, 'Right Back', 'RB', 'Back', 'Right', 299, 0),
                (2, 'Right Front', 'RF', 'Front', 'Right', 299, 299),
                (3, 'Middle Front', 'MF', 'Front', 'Middle', 150, 299),
                (4, 'Left Front', 'LF', 'Front', 'Left', 0, 299),
                (5, 'Left Back', 'LB', 'Back', 'Left', 0, 0),
                (6, 'Middle Back', 'MB', 'Back', 'Middle', 150, 0)
            ]
            cursor.executemany(
                "INSERT INTO positions (number, name, abbrev, row, side, x, y) VALUES (?, ?, ?, ?, ?, ?, ?)",
                positions_data
            )
            self.conn.commit()
            print("Positions table populated successfully!")
    
    # Helper methods for common operations
    
    def add_team(self, name: str) -> int:
        """Add a team and return team_id."""
        if not self.conn:
            self.connect()
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO teams (name) VALUES (?)", (name,))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_all_teams(self) -> list:
        """Get all teams from the database.
        
        Returns:
            List of tuples (team_id, name) ordered by name
        """
        if not self.conn:
            self.connect()
        cursor = self.conn.cursor()
        cursor.execute("SELECT team_id, name FROM teams ORDER BY name")
        return cursor.fetchall()
    
    def get_team_by_id(self, team_id: int) -> Optional[sqlite3.Row]:
        """Get a team by ID."""
        if not self.conn:
            self.connect()
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM teams WHERE team_id = ?", (team_id,))
        return cursor.fetchone()
    
    def add_player(self, team_id: int, player_number: str, name: Optional[str] = None) -> int:
        """Add a player and return player_id.
        
        Args:
            team_id: The team ID
            player_number: Player number (can be alphanumeric, e.g., "1", "10", "A1", "12B")
            name: Optional player name
        """
        if not self.conn:
            self.connect()
        cursor = self.conn.cursor()
        # Convert to string to ensure alphanumeric support
        player_number_str = str(player_number).strip()
        cursor.execute(
            "INSERT INTO players (team_id, player_number, name) VALUES (?, ?, ?)",
            (team_id, player_number_str, name)
        )
        self.conn.commit()
        return cursor.lastrowid
    
    def start_game(self, team_us_id: int, team_them_id: int, notes: Optional[str] = None) -> int:
        """Start a new game and return game_id.
        
        Raises ValueError if both teams are the same.
        """
        if team_us_id == team_them_id:
            raise ValueError("A game must have two different teams. team_us_id and team_them_id cannot be the same.")
        
        if not self.conn:
            self.connect()
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO games (team_us_id, team_them_id, notes) VALUES (?, ?, ?)",
            (team_us_id, team_them_id, notes)
        )
        self.conn.commit()
        return cursor.lastrowid
    
    def start_rally(self, game_id: int, rally_number: int, serving_team_id: int) -> int:
        """Start a new rally and return rally_id."""
        if not self.conn:
            self.connect()
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO rallies (game_id, rally_number, serving_team_id, rally_start_time)
               VALUES (?, ?, ?, ?)""",
            (game_id, rally_number, serving_team_id, datetime.now())
        )
        self.conn.commit()
        return cursor.lastrowid
    
    def add_contact(self, rally_id: int, sequence_number: int, contact_type: str, 
                   team_id: int, player_id: Optional[int] = None, 
                   x: Optional[int] = None, y: Optional[int] = None,
                   timecode: Optional[int] = None,
                   outcome: str = 'continue', rating: Optional[int] = None) -> int:
        """Add a ball contact and return contact_id.
        
        Args:
            rally_id: The rally ID
            sequence_number: The sequence number within the rally
            contact_type: Type of contact (serve, pass, set, attack, etc.)
            team_id: The team ID
            player_id: Optional player ID
            x: Optional x coordinate on the court
            y: Optional y coordinate on the court
            timecode: Optional video timecode in milliseconds
            outcome: Outcome of the contact (continue, ace, kill, error, down, stuff). Defaults to 'continue'
            rating: Optional rating (integer) for the contact
        """
        if not self.conn:
            self.connect()
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO contacts (rally_id, sequence_number, contact_type, team_id, player_id, x, y, timecode, outcome, rating)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (rally_id, sequence_number, contact_type, team_id, player_id, x, y, timecode, outcome, rating)
        )
        self.conn.commit()
        return cursor.lastrowid
    
    def end_rally(self, rally_id: int, point_winner_id: int):
        """End a rally and record the point winner."""
        if not self.conn:
            self.connect()
        cursor = self.conn.cursor()
        cursor.execute(
            """UPDATE rallies 
               SET point_winner_id = ?, rally_end_time = ?
               WHERE rally_id = ?""",
            (point_winner_id, datetime.now(), rally_id)
        )
        self.conn.commit()
    
    def update_contact_outcome(self, contact_id: int, outcome: str):
        """Update the outcome of a contact.
        
        Args:
            contact_id: The contact ID to update
            outcome: The outcome value (continue, ace, kill, error, down, stuff)
        """
        if not self.conn:
            self.connect()
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE contacts SET outcome = ? WHERE contact_id = ?",
            (outcome, contact_id)
        )
        self.conn.commit()
    
    def get_rally_contacts(self, rally_id: int) -> list:
        """Get all contacts for a rally, ordered by sequence number.
        
        Args:
            rally_id: The rally ID
            
        Returns:
            List of contact rows
        """
        if not self.conn:
            self.connect()
        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT contact_id, rally_id, sequence_number, player_id, contact_type, 
                      team_id, x, y, outcome, timestamp
               FROM contacts 
               WHERE rally_id = ?
               ORDER BY sequence_number""",
            (rally_id,)
        )
        return cursor.fetchall()
    
    def delete_game_rallies_and_contacts(self, game_id: int) -> tuple[int, int]:
        """Delete all rallies and contacts for a given game.
        
        Args:
            game_id: The ID of the game to delete rallies and contacts for
            
        Returns:
            Tuple of (contacts_deleted, rallies_deleted) counts
        """
        if not self.conn:
            self.connect()
        
        cursor = self.conn.cursor()
        
        # First, delete all contacts for rallies in this game
        cursor.execute("""
            DELETE FROM contacts 
            WHERE rally_id IN (
                SELECT rally_id FROM rallies WHERE game_id = ?
            )
        """, (game_id,))
        contacts_deleted = cursor.rowcount
        
        # Then, delete all rallies for this game
        cursor.execute("DELETE FROM rallies WHERE game_id = ?", (game_id,))
        rallies_deleted = cursor.rowcount
        
        self.conn.commit()
        
        return (contacts_deleted, rallies_deleted)
    
    def get_player_by_number(self, team_id: int, player_number: str) -> Optional[sqlite3.Row]:
        """Get a player by team and number.
        
        Args:
            team_id: The team ID
            player_number: Player number (can be alphanumeric)
        """
        if not self.conn:
            self.connect()
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM players WHERE team_id = ? AND player_number = ?",
            (team_id, str(player_number).strip())
        )
        return cursor.fetchone()
    
    def get_current_rally_sequence(self, rally_id: int) -> int:
        """Get the next sequence number for a rally."""
        if not self.conn:
            self.connect()
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT MAX(sequence_number) FROM contacts WHERE rally_id = ?",
            (rally_id,)
        )
        result = cursor.fetchone()[0]
        return (result or 0) + 1
    
    def add_player_to_game(self, game_id: int, team_id: int, player_id: int) -> int:
        """Add a player to a specific game's roster and return game_player_id."""
        if not self.conn:
            self.connect()
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO game_players (game_id, team_id, player_id) VALUES (?, ?, ?)",
                (game_id, team_id, player_id)
            )
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # Player already in game roster
            cursor.execute(
                "SELECT game_player_id FROM game_players WHERE game_id = ? AND team_id = ? AND player_id = ?",
                (game_id, team_id, player_id)
            )
            result = cursor.fetchone()
            return result[0] if result else None
    
    def get_game_players(self, game_id: int, team_id: int) -> list:
        """Get all players for a specific team in a specific game."""
        if not self.conn:
            self.connect()
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT p.player_id, p.player_number, p.name, p.team_id
            FROM players p
            INNER JOIN game_players gp ON p.player_id = gp.player_id
            WHERE gp.game_id = ? AND gp.team_id = ?
            ORDER BY 
                CASE 
                    WHEN CAST(p.player_number AS INTEGER) IS NOT NULL 
                    THEN CAST(p.player_number AS INTEGER)
                    ELSE 999999
                END,
                p.player_number
        """, (game_id, team_id))
        return cursor.fetchall()
    
    def remove_player_from_game(self, game_id: int, team_id: int, player_id: int):
        """Remove a player from a game's roster."""
        if not self.conn:
            self.connect()
        cursor = self.conn.cursor()
        cursor.execute(
            "DELETE FROM game_players WHERE game_id = ? AND team_id = ? AND player_id = ?",
            (game_id, team_id, player_id)
        )
        self.conn.commit()
    
    def get_player_by_number_for_game(self, game_id: int, team_id: int, player_number: str) -> Optional[sqlite3.Row]:
        """Get a player by number for a specific game and team.
        
        Args:
            game_id: The game ID
            team_id: The team ID
            player_number: Player number (can be alphanumeric)
        """
        if not self.conn:
            self.connect()
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT p.*
            FROM players p
            INNER JOIN game_players gp ON p.player_id = gp.player_id
            WHERE gp.game_id = ? AND gp.team_id = ? AND p.player_number = ?
        """, (game_id, team_id, str(player_number).strip()))
        return cursor.fetchone()
    
    def update_game_video_path(self, game_id: int, video_file_path: Optional[str]):
        """Update the video file path for a game.
        
        Args:
            game_id: The game ID
            video_file_path: Path to the video file (or None to clear it)
        """
        if not self.conn:
            self.connect()
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE games SET video_file_path = ? WHERE game_id = ?",
            (video_file_path, game_id)
        )
        self.conn.commit()
    
    def get_game_video_path(self, game_id: int) -> Optional[str]:
        """Get the video file path for a game.
        
        Args:
            game_id: The game ID
            
        Returns:
            The video file path, or None if not set
        """
        if not self.conn:
            self.connect()
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT video_file_path FROM games WHERE game_id = ?",
            (game_id,)
        )
        result = cursor.fetchone()
        return result[0] if result and result[0] else None
    
    def update_game_still_image_path(self, game_id: int, still_image_path: Optional[str]):
        """Update the still image file path for a game.
        
        Args:
            game_id: The game ID
            still_image_path: Path to the still image file (or None to clear it)
        """
        if not self.conn:
            self.connect()
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE games SET still_image_path = ? WHERE game_id = ?",
            (still_image_path, game_id)
        )
        self.conn.commit()
    
    def get_game_still_image_path(self, game_id: int) -> Optional[str]:
        """Get the still image file path for a game.
        
        Args:
            game_id: The game ID
            
        Returns:
            The still image file path, or None if not set
        """
        if not self.conn:
            self.connect()
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT still_image_path FROM games WHERE game_id = ?",
            (game_id,)
        )
        result = cursor.fetchone()
        return result[0] if result and result[0] else None
    
    def save_game_court_boundaries(self, game_id: int, court_points: dict, homography_matrix=None):
        """Save court boundary coordinates for a game.
        
        Args:
            game_id: The game ID
            court_points: Dictionary with keys like 'corner_tl', 'corner_tr', etc.
                         Each value should be a QPointF (from PySide6) or tuple (x, y)
            homography_matrix: Optional numpy array (3x3) representing the homography matrix
        """
        if not self.conn:
            self.connect()
        cursor = self.conn.cursor()
        
        # Convert QPointF or tuple to x, y values
        def get_xy(point):
            if hasattr(point, 'x') and hasattr(point, 'y'):
                # QPointF object
                return point.x(), point.y()
            # Tuple
            return point[0], point[1]
        
        tl_x, tl_y = get_xy(court_points.get('corner_tl', (0, 0)))
        tr_x, tr_y = get_xy(court_points.get('corner_tr', (0, 0)))
        bl_x, bl_y = get_xy(court_points.get('corner_bl', (0, 0)))
        br_x, br_y = get_xy(court_points.get('corner_br', (0, 0)))
        ct_x, ct_y = get_xy(court_points.get('centerline_top', (0, 0)))
        cb_x, cb_y = get_xy(court_points.get('centerline_bottom', (0, 0)))
        y200l_x, y200l_y = get_xy(court_points.get('y200_left', (0, 0)))
        y200r_x, y200r_y = get_xy(court_points.get('y200_right', (0, 0)))
        y400l_x, y400l_y = get_xy(court_points.get('y400_left', (0, 0)))
        y400r_x, y400r_y = get_xy(court_points.get('y400_right', (0, 0)))
        
        # Serialize homography matrix to JSON if provided
        homography_json = None
        if homography_matrix is not None:
            import json
            import numpy as np
            # Convert numpy array to list for JSON serialization
            homography_list = homography_matrix.tolist()
            homography_json = json.dumps(homography_list)
        
        cursor.execute("""
            UPDATE games SET
                court_corner_tl_x = ?, court_corner_tl_y = ?,
                court_corner_tr_x = ?, court_corner_tr_y = ?,
                court_corner_bl_x = ?, court_corner_bl_y = ?,
                court_corner_br_x = ?, court_corner_br_y = ?,
                court_centerline_top_x = ?, court_centerline_top_y = ?,
                court_centerline_bottom_x = ?, court_centerline_bottom_y = ?,
                court_y200_left_x = ?, court_y200_left_y = ?,
                court_y200_right_x = ?, court_y200_right_y = ?,
                court_y400_left_x = ?, court_y400_left_y = ?,
                court_y400_right_x = ?, court_y400_right_y = ?,
                homography_matrix = ?
            WHERE game_id = ?
        """, (tl_x, tl_y, tr_x, tr_y, bl_x, bl_y, br_x, br_y, ct_x, ct_y, cb_x, cb_y,
              y200l_x, y200l_y, y200r_x, y200r_y, y400l_x, y400l_y, y400r_x, y400r_y,
              homography_json, game_id))
        self.conn.commit()
    
    def get_game_court_boundaries(self, game_id: int) -> Optional[dict]:
        """Get court boundary coordinates for a game.
        
        Args:
            game_id: The game ID
            
        Returns:
            Dictionary with court points (as tuples (x, y)), or None if not set
        """
        if not self.conn:
            self.connect()
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT court_corner_tl_x, court_corner_tl_y,
                   court_corner_tr_x, court_corner_tr_y,
                   court_corner_bl_x, court_corner_bl_y,
                   court_corner_br_x, court_corner_br_y,
                   court_centerline_top_x, court_centerline_top_y,
                   court_centerline_bottom_x, court_centerline_bottom_y,
                   court_y200_left_x, court_y200_left_y,
                   court_y200_right_x, court_y200_right_y,
                   court_y400_left_x, court_y400_left_y,
                   court_y400_right_x, court_y400_right_y,
                   homography_matrix
            FROM games WHERE game_id = ?
        """, (game_id,))
        result = cursor.fetchone()
        
        if not result or result[0] is None:
            return None
        
        # Deserialize homography matrix from JSON if present
        homography_matrix = None
        if len(result) > 20 and result[20] is not None:
            try:
                import json
                import numpy as np
                homography_list = json.loads(result[20])
                homography_matrix = np.array(homography_list, dtype=np.float32)
            except Exception as e:
                print(f"Warning: Failed to deserialize homography matrix: {e}")
        
        # Return as tuples - the calling code will convert to QPointF
        return {
            'corner_tl': (result[0], result[1]),
            'corner_tr': (result[2], result[3]),
            'corner_bl': (result[4], result[5]),
            'corner_br': (result[6], result[7]),
            'centerline_top': (result[8], result[9]),
            'centerline_bottom': (result[10], result[11]),
            'y200_left': (result[12], result[13]) if result[12] is not None else None,
            'y200_right': (result[14], result[15]) if result[14] is not None else None,
            'y400_left': (result[16], result[17]) if result[16] is not None else None,
            'y400_right': (result[18], result[19]) if result[18] is not None else None,
            'homography_matrix': homography_matrix
        }


if __name__ == "__main__":
    # Initialize the database
    db = VideoStatsDB()
    db.initialize_database()
    print("VideoStats database initialized successfully!")

