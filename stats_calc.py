"""
Statistics calculation module for volleyball rally tracking app.
This module handles calculation of player statistics, including receive ratings.
"""

import json
import os
from database import VideoStatsDB
from typing import Dict, Optional
from utils import resource_path
from logging_config import get_logger

logger = get_logger('stats_calc')


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
        config_path = resource_path("data/config_receive_rating.json")
        if config_path.exists():
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
                            logger.warning(f"No array data found in JSON. Available keys: {keys}")
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing JSON: {e}")
                    logger.debug(f"Error at position: {e.pos}")
                    logger.debug(f"Context around error: {fixed_content[max(0, e.pos-50):e.pos+50]}")
                    self.receive_rating = []
        else:
            logger.warning(f"{config_path} not found")
            self.receive_rating = []
    
    def print_receive_rating_configs(self):
        """Print the receive rating configuration array for debugging."""
        logger.debug("\n" + "="*80)
        logger.debug("Receive Rating Configuration")
        logger.debug("="*80)
        if self.receive_rating:
            for i, row in enumerate(self.receive_rating):
                logger.debug(f"Row {i}: {row}")
        else:
            logger.debug("No data loaded")
        logger.debug("="*80 + "\n")
    
    def calculate_game_stats(self, db: VideoStatsDB, game_id: int):
        """Calculate and store player statistics for a specific game.
        
        Args:
            db: VideoStatsDB database connection
            game_id: The game ID to calculate stats for
        """
        if not db.conn:
            db.connect()
        
        # Compute receive ratings first (if not already computed)
        logger.info(f"Computing receive ratings for game {game_id} before calculating stats...")
        self.compute_receive_ratings_for_game(db, game_id)
        
        cursor = db.conn.cursor()
        
        # Delete existing stats for this game
        cursor.execute("DELETE FROM player_stats WHERE game_id = %s", (game_id,))
        deleted_count = cursor.rowcount
        if deleted_count > 0:
            logger.info(f"Deleted {deleted_count} existing stat records for game {game_id}")
        
        # Get all contacts for this game, joining with rallies to get game_id
        cursor.execute("""
            SELECT 
                c.player_id,
                c.contact_type,
                c.outcome,
                c.rating
            FROM contacts c
            INNER JOIN rallies r ON c.rally_id = r.rally_id
            WHERE r.game_id = %s AND c.player_id IS NOT NULL
            ORDER BY c.player_id, c.contact_type
        """, (game_id,))
        
        contacts = cursor.fetchall()
        
        if not contacts:
            logger.warning(f"No contacts found for game {game_id}")
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
                WHERE r.game_id = %s AND c.player_id = %s 
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
                WHERE r.game_id = %s AND c.player_id = %s 
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
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
        logger.info(f"Calculated and stored stats for {len(player_stats)} players for game {game_id}")
        
        # Print summary for each player
        for player_id, stats in player_stats.items():
            cursor.execute("SELECT player_number, name FROM players WHERE player_id = %s", (player_id,))
            player_info = cursor.fetchone()
            player_name = f"{player_info[0] if player_info else 'Unknown'}" + (f" ({player_info[1]})" if player_info and player_info[1] else "")
            logger.debug(f"  Player {player_name}: "
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
        
        logger.info(f"Calculating stats for {len(games)} games...")
        for game_row in games:
            game_id = game_row['game_id']
            logger.info(f"Processing game {game_id}...")
            self.calculate_game_stats(db, game_id)
        
        logger.info("All games processed!")
    
    def compute_receive_rating(self, receive_team_id: int, next_contact_type: str, 
                                next_contact_team_id: Optional[int], 
                                next_contact_x: Optional[int], 
                                next_contact_y: Optional[int],
                                team_us_id: int, team_them_id: int) -> Optional[int]:
        """Compute receive rating based on the next contact.
        
        Args:
            receive_team_id: The team ID that made the receive
            next_contact_type: The type of the next contact ('down', 'serve', 'pass', etc.)
            next_contact_team_id: The team ID that made the next contact (None if no next contact)
            next_contact_x: X coordinate of the next contact (None if not available)
            next_contact_y: Y coordinate of the next contact (None if not available)
            team_us_id: The "us" team ID for this game
            team_them_id: The "them" team ID for this game
            
        Returns:
            Rating (0, 1, 2, or 3) or None if cannot be determined
        """
        logger.debug(f"compute_receive_rating: receive_team_id={receive_team_id}, next_type={next_contact_type}, next_team_id={next_contact_team_id}, next_x={next_contact_x}, next_y={next_contact_y}")
        
        # If no next contact, cannot determine rating
        if next_contact_type is None:
            logger.debug("No next contact type - returning None")
            return None
        
        # Case 1: Next contact is DOWN
        if next_contact_type == 'down':
            logger.debug("Case 1 - Next contact is 'down'")
            # Rating = 0, EXCEPT when down location is within the other team's boundaries
            # Other team's boundaries: x between 0-300, and y > 0 and y < 600
            if next_contact_x is not None and next_contact_y is not None:
                logger.debug(f"Down contact has coordinates: x={next_contact_x}, y={next_contact_y}")
                if (0 <= next_contact_x <= 300 and 0 < next_contact_y < 600):
                    logger.debug("Down is in bounds (other team's boundaries) - using lookup table")
                    # Down is in bounds - use lookup table
                    # Map x and y from 0-600 to 0-60 (10% of original, rounded)
                    mapped_x = int(round(next_contact_x * 0.1))
                    mapped_y = int(round(next_contact_y * 0.1))
                    logger.debug(f"Mapped coordinates: mapped_x={mapped_x}, mapped_y={mapped_y}")
                    
                    # Clamp to valid array indices
                    if self.receive_rating and len(self.receive_rating) > 0:
                        max_y = len(self.receive_rating) - 1
                        max_x = len(self.receive_rating[0]) - 1 if len(self.receive_rating[0]) > 0 else 0
                        logger.debug(f"Array bounds: max_x={max_x}, max_y={max_y}")
                        mapped_y = min(max(0, mapped_y), max_y)
                        mapped_x = min(max(0, mapped_x), max_x)
                        logger.debug(f"Clamped coordinates: mapped_x={mapped_x}, mapped_y={mapped_y}")
                        
                        rating = self.receive_rating[mapped_y][mapped_x]
                        logger.debug(f"Lookup result: rating={rating} from receive_rating[{mapped_y}][{mapped_x}]")
                        return rating
                    else:
                        logger.warning("receive_rating config not available for lookup")
                else:
                    logger.debug("Down is out of bounds - returning 0")
            else:
                logger.debug("Down contact missing coordinates - returning 0")
            # Default: rating = 0 for DOWN
            return 0
        
        # Case 2: Next contact is by the other team
        if next_contact_team_id is not None:
            other_team_id = team_them_id if receive_team_id == team_us_id else team_us_id
            logger.debug(f"Case 2 - Checking if next contact is by other team: other_team_id={other_team_id}, next_team_id={next_contact_team_id}")
            if next_contact_team_id == other_team_id:
                logger.debug("Next contact is by other team - returning 0")
                return 0
        
        # Case 3: Next contact is by the same team
        if next_contact_team_id == receive_team_id:
            logger.debug("Case 3 - Next contact is by same team")
            if next_contact_x is not None and next_contact_y is not None:
                logger.debug(f"Same team contact has coordinates: x={next_contact_x}, y={next_contact_y}")
                # Map x and y from 0-600 to 0-60 (10% of original, rounded)
                mapped_x = int(round(next_contact_x * 0.1))
                mapped_y = int(round(next_contact_y * 0.1))
                logger.debug(f"Mapped coordinates: mapped_x={mapped_x}, mapped_y={mapped_y}")
                
                # Clamp to valid array indices
                if self.receive_rating and len(self.receive_rating) > 0:
                    max_y = len(self.receive_rating) - 1
                    max_x = len(self.receive_rating[0]) - 1 if len(self.receive_rating[0]) > 0 else 0
                    logger.debug(f"Array bounds: max_x={max_x}, max_y={max_y}")
                    mapped_y = min(max(0, mapped_y), max_y)
                    mapped_x = min(max(0, mapped_x), max_x)
                    logger.debug(f"Clamped coordinates: mapped_x={mapped_x}, mapped_y={mapped_y}")
                    
                    rating = self.receive_rating[mapped_y][mapped_x]
                    logger.debug(f"Lookup result: rating={rating} from receive_rating[{mapped_y}][{mapped_x}]")
                    return rating
                else:
                    logger.warning("receive_rating config not available for lookup")
            else:
                logger.debug("Same team contact missing coordinates")
        
        # Default: cannot determine rating
        logger.debug("Default case - cannot determine rating, returning None")
        return None
    
    def compute_receive_ratings_for_game(self, db: VideoStatsDB, game_id: int):
        """Compute and update receive ratings for all receive contacts in a game.
        
        Args:
            db: VideoStatsDB database connection
            game_id: The game ID to process
        """
        logger.debug(f"\n{'='*80}")
        logger.debug(f"compute_receive_ratings_for_game called for game_id={game_id}")
        logger.debug(f"{'='*80}")
        
        if not db.conn:
            db.connect()
        
        cursor = db.conn.cursor()
        
        # Get team IDs for this game
        cursor.execute("""
            SELECT team_us_id, team_them_id
            FROM games
            WHERE game_id = %s
        """, (game_id,))
        
        game_result = cursor.fetchone()
        if not game_result:
            logger.warning(f"Game {game_id} not found")
            return
        
        team_us_id = game_result['team_us_id']
        team_them_id = game_result['team_them_id']
        logger.debug(f"Team IDs - team_us_id={team_us_id}, team_them_id={team_them_id}")
        
        # Check if receive_rating config is loaded
        if self.receive_rating is None:
            logger.warning("receive_rating config is None!")
        elif len(self.receive_rating) == 0:
            logger.warning("receive_rating config is empty!")
        else:
            logger.debug(f"receive_rating config loaded - {len(self.receive_rating)} rows, {len(self.receive_rating[0]) if self.receive_rating[0] else 0} columns")
        
        # Get all receive contacts for this game, ordered by rally and sequence
        cursor.execute("""
            SELECT 
                c.contact_id,
                c.rally_id,
                c.sequence_number,
                c.team_id as receive_team_id,
                COALESCE(c.rating_manual, 0) as rating_manual
            FROM contacts c
            INNER JOIN rallies r ON c.rally_id = r.rally_id
            WHERE r.game_id = %s AND c.contact_type = 'receive'
            ORDER BY c.rally_id, c.sequence_number
        """, (game_id,))
        
        receive_contacts = cursor.fetchall()
        
        if not receive_contacts:
            logger.info(f"No receive contacts found for game {game_id}")
            return
        
        logger.info(f"Found {len(receive_contacts)} receive contacts to process")
        
        updated_count = 0
        skipped_count = 0
        
        for idx, receive in enumerate(receive_contacts):
            contact_id = receive['contact_id']
            rally_id = receive['rally_id']
            sequence_number = receive['sequence_number']
            receive_team_id = receive['receive_team_id']
            rating_manual = receive['rating_manual']
            
            logger.debug(f"\nProcessing receive contact #{idx+1}/{len(receive_contacts)}")
            logger.debug(f"  contact_id={contact_id}, rally_id={rally_id}, sequence={sequence_number}, receive_team_id={receive_team_id}, rating_manual={rating_manual}")
            
            # Skip if rating is manually set
            if rating_manual == 1:
                logger.debug(f"  [SKIP] Skipping contact {contact_id} - rating is manually set (rating_manual=1)")
                skipped_count += 1
                continue
            
            # Find the next contact in the same rally
            cursor.execute("""
                SELECT 
                    contact_type,
                    team_id,
                    x,
                    y
                FROM contacts
                WHERE rally_id = %s AND sequence_number > %s
                ORDER BY sequence_number
                LIMIT 1
            """, (rally_id, sequence_number))
            
            next_contact = cursor.fetchone()
            
            # Extract next contact information
            next_contact_type = next_contact['contact_type'] if next_contact else None
            next_contact_team_id = next_contact['team_id'] if next_contact else None
            next_contact_x = next_contact['x'] if next_contact else None
            next_contact_y = next_contact['y'] if next_contact else None
            
            logger.debug(f"  Next contact: type={next_contact_type}, team_id={next_contact_team_id}, x={next_contact_x}, y={next_contact_y}")
            
            # Compute rating
            rating = self.compute_receive_rating(
                receive_team_id=receive_team_id,
                next_contact_type=next_contact_type,
                next_contact_team_id=next_contact_team_id,
                next_contact_x=next_contact_x,
                next_contact_y=next_contact_y,
                team_us_id=team_us_id,
                team_them_id=team_them_id
            )
            
            logger.debug(f"  Computed rating: {rating}")
            
            # Update the contact with the rating
            if rating is not None:
                logger.debug(f"  Updating contact_id={contact_id} with rating={rating}")
                cursor.execute("""
                    UPDATE contacts
                    SET rating = %s
                    WHERE contact_id = %s
                """, (rating, contact_id))
                updated_count += 1
                logger.debug(f"  [OK] Successfully updated contact {contact_id} with rating {rating}")
            else:
                logger.warning(f"  [X] Could not compute rating for contact_id={contact_id}, rally_id={rally_id}, sequence={sequence_number}")
        
        db.conn.commit()
        logger.debug(f"\n{'='*80}")
        logger.info(f"Updated {updated_count} receive ratings for game {game_id}")
        if skipped_count > 0:
            logger.debug(f"Skipped {skipped_count} receive contacts with manually set ratings (rating_manual=1)")
        logger.debug(f"{'='*80}\n")
    
    def compute_receive_ratings_for_all_games(self, db: VideoStatsDB):
        """Compute receive ratings for all games in the database.
        
        Args:
            db: VideoStatsDB database connection
        """
        if not db.conn:
            db.connect()
        
        cursor = db.conn.cursor()
        cursor.execute("SELECT DISTINCT game_id FROM rallies ORDER BY game_id")
        games = cursor.fetchall()
        
        logger.info(f"Computing receive ratings for {len(games)} games...")
        for game_row in games:
            game_id = game_row['game_id']
            logger.info(f"Processing game {game_id}...")
            self.compute_receive_ratings_for_game(db, game_id)
        
        logger.info("All games processed!")


# For testing/debugging
if __name__ == "__main__":
    import sys
    calculator = StatsCalculator()
    
    if len(sys.argv) > 2:
        command = sys.argv[1]
        if command == "compute-ratings":
            # Compute receive ratings for a specific game
            from database import VideoStatsDB
            db = VideoStatsDB()
            game_id = int(sys.argv[2])
            logger.info(f"Computing receive ratings for game {game_id}...")
            calculator.compute_receive_ratings_for_game(db, game_id)
            db.close()
        elif command == "stats":
            # Calculate stats for a specific game
            from database import VideoStatsDB
            db = VideoStatsDB()
            game_id = int(sys.argv[2])
            logger.info(f"Calculating stats for game {game_id}...")
            calculator.calculate_game_stats(db, game_id)
            db.close()
    elif len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "--all-ratings":
            # Compute receive ratings for all games
            from database import VideoStatsDB
            db = VideoStatsDB()
            calculator.compute_receive_ratings_for_all_games(db)
            db.close()
        elif command == "--all":
            # Calculate stats for all games
            from database import VideoStatsDB
            db = VideoStatsDB()
            calculator.calculate_all_games_stats(db)
            db.close()
        else:
            # Try to parse as game_id for backward compatibility
            try:
                from database import VideoStatsDB
                db = VideoStatsDB()
                game_id = int(sys.argv[1])
                logger.info(f"Calculating stats for game {game_id}...")
                calculator.calculate_game_stats(db, game_id)
                db.close()
            except ValueError:
                logger.error(f"Unknown command: {sys.argv[1]}")
                logger.info("Usage:")
                logger.info("  python stats_calc.py [game_id]              - Calculate stats for a game")
                logger.info("  python stats_calc.py stats [game_id]         - Calculate stats for a game")
                logger.info("  python stats_calc.py compute-ratings [game_id] - Compute receive ratings for a game")
                logger.info("  python stats_calc.py --all                   - Calculate stats for all games")
                logger.info("  python stats_calc.py --all-ratings           - Compute receive ratings for all games")
    else:
        # Just print receive rating configs
        calculator.print_receive_rating_configs()



