"""
Statistics calculation module for volleyball rally tracking app.
This module handles calculation of player statistics, including receive ratings.
"""

import json
import os
from database import VideoStatsDB
from typing import Dict, Optional


class StatsCalculator:
    """Calculates statistics for volleyball player actions."""
    
    def __init__(self):
        """Initialize the statistics calculator with receive rating configs."""
        # 2D array for receive rating configuration
        self.receive_rating = None
        
        # Load configuration file
        self._load_receive_rating_configs()
    
    def _load_receive_rating_configs(self):
        """Load receive rating configuration file into a 2D array."""
        config_path = "config_receive_rating.json"
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                content = f.read()
                # Fix malformed JSON by adding commas between array elements
                lines = content.strip().split('\n')
                fixed_lines = []
                for i, line in enumerate(lines):
                    line = line.strip()
                    if not line:  # Skip empty lines
                        continue
                    if i == 0:
                        fixed_lines.append(line)
                    elif line.startswith('['):
                        # Add comma before array if not the first array element
                        if fixed_lines and not fixed_lines[-1].endswith('['):
                            fixed_lines.append(',' + line)
                        else:
                            fixed_lines.append(line)
                    elif line == '] }' or line == ']}':
                        fixed_lines.append(line)
                    else:
                        fixed_lines.append(line)
                
                fixed_content = '\n'.join(fixed_lines)
                try:
                    data = json.loads(fixed_content)
                    # Extract the 2D array from the JSON - try 'receive_rating' first, then fallback to other keys
                    if "receive_rating" in data:
                        self.receive_rating = data["receive_rating"]
                    elif "scores_us" in data:
                        self.receive_rating = data["scores_us"]
                    elif "scores_them" in data:
                        self.receive_rating = data["scores_them"]
                    else:
                        # Use the first available array value
                        keys = list(data.keys())
                        if keys:
                            self.receive_rating = data[keys[0]]
                        else:
                            self.receive_rating = []
                            print(f"Warning: No array data found in JSON. Available keys: {keys}")
                except json.JSONDecodeError as e:
                    print(f"Error parsing JSON: {e}")
                    print(f"Error at position: {e.pos}")
                    print(f"Context around error: {fixed_content[max(0, e.pos-50):e.pos+50]}")
                    self.receive_rating = []
        else:
            print(f"Warning: {config_path} not found")
            self.receive_rating = []
    
    def print_receive_rating_configs(self):
        """Print the receive rating configuration array for debugging."""
        print("\n" + "="*80)
        print("Receive Rating Configuration")
        print("="*80)
        if self.receive_rating:
            for i, row in enumerate(self.receive_rating):
                print(f"Row {i}: {row}")
        else:
            print("No data loaded")
        print("="*80 + "\n")
    
    def calculate_game_stats(self, db: VideoStatsDB, game_id: int):
        """Calculate and store player statistics for a specific game.
        
        Args:
            db: VideoStatsDB database connection
            game_id: The game ID to calculate stats for
        """
        if not db.conn:
            db.connect()
        
        cursor = db.conn.cursor()
        
        # Delete existing stats for this game
        cursor.execute("DELETE FROM player_stats WHERE game_id = ?", (game_id,))
        deleted_count = cursor.rowcount
        if deleted_count > 0:
            print(f"Deleted {deleted_count} existing stat records for game {game_id}")
        
        # Get all contacts for this game, joining with rallies to get game_id
        cursor.execute("""
            SELECT 
                c.player_id,
                c.contact_type,
                c.outcome,
                c.rating
            FROM contacts c
            INNER JOIN rallies r ON c.rally_id = r.rally_id
            WHERE r.game_id = ? AND c.player_id IS NOT NULL
            ORDER BY c.player_id, c.contact_type
        """, (game_id,))
        
        contacts = cursor.fetchall()
        
        if not contacts:
            print(f"No contacts found for game {game_id}")
            db.conn.commit()
            return
        
        # Group contacts by player_id
        player_stats: Dict[int, Dict] = {}
        
        for contact in contacts:
            player_id = contact['player_id']
            contact_type = contact['contact_type']
            outcome = contact['outcome']
            rating = contact['rating']
            
            # Initialize player stats if not exists
            if player_id not in player_stats:
                player_stats[player_id] = {
                    'serve_attempts': 0,
                    'serve_errors': 0,
                    'receive_attempts': 0,
                    'receive_errors': 0,
                    'receive_0': 0,
                    'receive_1': 0,
                    'receive_2': 0,
                    'receive_3': 0,
                    'receive_ratings_sum': 0,
                    'receive_ratings_count': 0,
                    'pass_attempts': 0,
                    'pass_continue': 0,  # Tracked but not stored in DB (no column)
                    'set_attempts': 0,
                    'set_errors': 0,
                    'attack_attempts': 0,
                    'attack_kills': 0,
                    'attack_errors': 0,
                    'freeball_attempts': 0,
                    'block_attempts': 0,
                }
            
            stats = player_stats[player_id]
            
            # Count by contact type
            if contact_type == 'serve':
                stats['serve_attempts'] += 1
                if outcome == 'error':
                    stats['serve_errors'] += 1
            elif contact_type == 'receive':
                stats['receive_attempts'] += 1
                if outcome == 'error':
                    stats['receive_errors'] += 1
                # Count by rating
                if rating is not None:
                    if rating == 0:
                        stats['receive_0'] += 1
                    elif rating == 1:
                        stats['receive_1'] += 1
                    elif rating == 2:
                        stats['receive_2'] += 1
                    elif rating == 3:
                        stats['receive_3'] += 1
                    stats['receive_ratings_sum'] += rating
                    stats['receive_ratings_count'] += 1
            elif contact_type == 'pass':
                stats['pass_attempts'] += 1
                if outcome == 'continue':
                    stats['pass_continue'] += 1
            elif contact_type == 'set':
                stats['set_attempts'] += 1
                if outcome == 'error':
                    stats['set_errors'] += 1
            elif contact_type == 'attack':
                stats['attack_attempts'] += 1
                if outcome == 'kill':
                    stats['attack_kills'] += 1
                elif outcome == 'error':
                    stats['attack_errors'] += 1
            elif contact_type == 'freeball':
                stats['freeball_attempts'] += 1
            elif contact_type == 'block':
                stats['block_attempts'] += 1
        
        # Calculate derived statistics and insert into database
        for player_id, stats in player_stats.items():
            # Calculate average receive rating (rounded to 2 decimal places)
            receive_avg_rating = 0.0
            if stats['receive_ratings_count'] > 0:
                receive_avg_rating = round(stats['receive_ratings_sum'] / stats['receive_ratings_count'], 2)
            
            # Calculate attack kill percentage as decimal (0.123 = 12.3%) (rounded to 3 decimal places)
            attack_kill_pct = 0.0
            if stats['attack_attempts'] > 0:
                attack_kill_pct = round(stats['attack_kills'] / stats['attack_attempts'], 3)
            
            # Calculate hitting percentage as decimal (0.123 = 12.3%): (Kills - Errors) / Total Attacks (rounded to 3 decimal places)
            attack_hitting_pct = 0.0
            if stats['attack_attempts'] > 0:
                attack_hitting_pct = round((stats['attack_kills'] - stats['attack_errors']) / stats['attack_attempts'], 3)
            
            # Count aces (outcome = 'ace') during the main loop
            # We'll count them separately here
            cursor.execute("""
                SELECT COUNT(*) as ace_count
                FROM contacts c
                INNER JOIN rallies r ON c.rally_id = r.rally_id
                WHERE r.game_id = ? AND c.player_id = ? 
                AND c.contact_type = 'serve' AND c.outcome = 'ace'
            """, (game_id, player_id))
            ace_result = cursor.fetchone()
            serve_aces = ace_result[0] if ace_result else 0
            
            # Calculate serve ace percentage as decimal (0.123 = 12.3%) (rounded to 3 decimal places)
            serve_ace_pct = 0.0
            if stats['serve_attempts'] > 0:
                serve_ace_pct = round(serve_aces / stats['serve_attempts'], 3)
                
                # Calculate serves in percentage as decimal (0.123 = 12.3%) (not errors) (rounded to 3 decimal places)
                serves_in = stats['serve_attempts'] - stats['serve_errors']
                serve_in_pct = round(serves_in / stats['serve_attempts'], 3)
            else:
                serve_in_pct = 0.0
            
            # Count set assists (outcome = 'assist')
            cursor.execute("""
                SELECT COUNT(*) as assist_count
                FROM contacts c
                INNER JOIN rallies r ON c.rally_id = r.rally_id
                WHERE r.game_id = ? AND c.player_id = ? 
                AND c.contact_type = 'set' AND c.outcome = 'assist'
            """, (game_id, player_id))
            assist_result = cursor.fetchone()
            set_assists = assist_result[0] if assist_result else 0
            
            # Insert or update player stats
            cursor.execute("""
                INSERT INTO player_stats (
                    game_id, player_id,
                    receive_attempts, receive_0, receive_1, receive_2, receive_3, receive_avg_rating,
                    attack_attempts, attack_kills, attack_errors, attack_kill_pct, attack_hitting_pct,
                    set_attempts, set_assists,
                    serve_attempts, serve_aces, serve_errors, serve_ace_pct, serve_in_pct,
                    dig_attempts, dig_successful,
                    block_solo
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                game_id, player_id,
                stats['receive_attempts'], stats['receive_0'], stats['receive_1'], stats['receive_2'], stats['receive_3'], receive_avg_rating,
                stats['attack_attempts'], stats['attack_kills'], stats['attack_errors'], attack_kill_pct, attack_hitting_pct,
                stats['set_attempts'], set_assists,
                stats['serve_attempts'], serve_aces, stats['serve_errors'], serve_ace_pct, serve_in_pct,
                0, 0,  # dig_attempts, dig_successful (not calculated yet)
                stats['block_attempts']  # block_solo (using block_attempts as solo blocks for now)
            ))
        
        db.conn.commit()
        print(f"Calculated and stored stats for {len(player_stats)} players for game {game_id}")
        
        # Print summary for each player
        for player_id, stats in player_stats.items():
            cursor.execute("SELECT player_number, name FROM players WHERE player_id = ?", (player_id,))
            player_info = cursor.fetchone()
            player_name = f"{player_info[0] if player_info else 'Unknown'}" + (f" ({player_info[1]})" if player_info and player_info[1] else "")
            print(f"  Player {player_name}: "
                  f"Serves={stats['serve_attempts']}, "
                  f"Receives={stats['receive_attempts']}, "
                  f"Passes={stats['pass_attempts']} (continue={stats['pass_continue']}), "
                  f"Sets={stats['set_attempts']}, "
                  f"Attacks={stats['attack_attempts']}, "
                  f"Freeballs={stats['freeball_attempts']}, "
                  f"Blocks={stats['block_attempts']}")
    
    def calculate_all_games_stats(self, db: VideoStatsDB):
        """Calculate statistics for all games in the database.
        
        Args:
            db: VideoStatsDB database connection
        """
        if not db.conn:
            db.connect()
        
        cursor = db.conn.cursor()
        cursor.execute("SELECT DISTINCT game_id FROM rallies ORDER BY game_id")
        games = cursor.fetchall()
        
        print(f"Calculating stats for {len(games)} games...")
        for game_row in games:
            game_id = game_row['game_id']
            print(f"\nProcessing game {game_id}...")
            self.calculate_game_stats(db, game_id)
        
        print("\nAll games processed!")


# For testing/debugging
if __name__ == "__main__":
    import sys
    calculator = StatsCalculator()
    
    if len(sys.argv) > 1:
        # Calculate stats for a specific game
        from database import VideoStatsDB
        db = VideoStatsDB()
        game_id = int(sys.argv[1])
        print(f"Calculating stats for game {game_id}...")
        calculator.calculate_game_stats(db, game_id)
        db.close()
    elif len(sys.argv) > 1 and sys.argv[1] == "--all":
        # Calculate stats for all games
        from database import VideoStatsDB
        db = VideoStatsDB()
        calculator.calculate_all_games_stats(db)
        db.close()
    else:
        # Just print receive rating configs
        calculator.print_receive_rating_configs()

