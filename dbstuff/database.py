"""
PostgreSQL database structure for VideoStats volleyball tracking application.
Tracks player ball contacts from serve through rally end.
"""

import psycopg2
import psycopg2.extras
import re
from pathlib import Path
from datetime import datetime
from typing import Optional
from logging_config import get_logger
import os

# Import query classes
from dbstuff.queries import (
    TeamQueries, PlayerQueries, GameQueries, RallyQueries,
    ContactQueries, LineupQueries, RotationQueries, 
    SubstitutionQueries, EventQueries, StatsQueries,
    CollectionQueries, GamePlayerQueries
)

logger = get_logger('database')


class VideoStatsDB:
    """Database manager for VideoStats volleyball tracking."""
    
    def __init__(self, connection_string: str = None):
        """Initialize the database connection.
        """
        # Check for connection string (priority order: parameter > env var)
        if connection_string is None:
            connection_string = os.getenv('SUPABASE_URL')
        
        if connection_string:
            # Use connection string (for Supabase or other hosted PostgreSQL)
            self.db_config = connection_string
        else:
            raise ValueError("No connection string provided")
        
        self.conn = None
        
        # Query class instances (initialized lazily)
        # self._teams = None
        # self._players = None
        # self._games = None
        # self._rallies = None
        # self._contacts = None
        # self._lineup = None
        # self._rotation = None
        # self._substitutions = None
        # self._events = None
        # self._stats = None
        # self._collections = None
        # self._game_players = None
        
    def connect(self):
        """Connect to the database."""
        # Handle both connection string and config dict
        if isinstance(self.db_config, str):
            # Connection string (DSN) format
            self.conn = psycopg2.connect(self.db_config)
        else:
            # Dictionary config format
            self.conn = psycopg2.connect(**self.db_config)
        
        self.conn.set_session(autocommit=False)
        # Reset query instances when connection changes
        self._reset_query_instances()
        return self.conn
    
    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            self._reset_query_instances()
    
    def _reset_query_instances(self):
        """Reset all query class instances."""
        self._teams = None
        self._players = None
        self._games = None
        self._rallies = None
        self._contacts = None
        self._lineup = None
        self._rotation = None
        self._substitutions = None
        self._events = None
        self._stats = None
        self._collections = None
        self._game_players = None
    
    # Properties for query classes (lazy initialization)
    @property
    def teams(self) -> TeamQueries:
        """Get TeamQueries instance."""
        if self._teams is None:
            self._teams = TeamQueries(self.conn)
        return self._teams
    
    @property
    def players(self) -> PlayerQueries:
        """Get PlayerQueries instance."""
        if self._players is None:
            self._players = PlayerQueries(self.conn)
        return self._players
    
    @property
    def games(self) -> GameQueries:
        """Get GameQueries instance."""
        if self._games is None:
            self._games = GameQueries(self.conn)
        return self._games
    
    @property
    def rallies(self) -> RallyQueries:
        """Get RallyQueries instance."""
        if self._rallies is None:
            self._rallies = RallyQueries(self.conn)
        return self._rallies
    
    @property
    def contacts(self) -> ContactQueries:
        """Get ContactQueries instance."""
        if self._contacts is None:
            self._contacts = ContactQueries(self.conn)
        return self._contacts
    
    @property
    def lineup(self) -> LineupQueries:
        """Get LineupQueries instance."""
        if self._lineup is None:
            self._lineup = LineupQueries(self.conn)
        return self._lineup
    
    @property
    def rotation(self) -> RotationQueries:
        """Get RotationQueries instance."""
        if self._rotation is None:
            self._rotation = RotationQueries(self.conn)
        return self._rotation
    
    @property
    def substitutions(self) -> SubstitutionQueries:
        """Get SubstitutionQueries instance."""
        if self._substitutions is None:
            self._substitutions = SubstitutionQueries(self.conn)
        return self._substitutions
    
    @property
    def events(self) -> EventQueries:
        """Get EventQueries instance."""
        if self._events is None:
            self._events = EventQueries(self.conn)
        return self._events
    
    @property
    def stats(self) -> StatsQueries:
        """Get StatsQueries instance."""
        if self._stats is None:
            self._stats = StatsQueries(self.conn)
        return self._stats
    
    @property
    def collections(self) -> CollectionQueries:
        """Get CollectionQueries instance."""
        if self._collections is None:
            self._collections = CollectionQueries(self.conn)
        return self._collections
    
    @property
    def game_players(self) -> GamePlayerQueries:
        """Get GamePlayerQueries instance."""
        if self._game_players is None:
            self._game_players = GamePlayerQueries(self.conn)
        return self._game_players
    
    
    def initialize_database(self):
        """Initialize the database with tables.
        Note: For PostgreSQL, schema should be created using migration files.
        This method is kept for compatibility but doesn't create tables.
        """
        logger.info("Database initialization called. Use migration files to create PostgreSQL schema.")
    
    
    # ============================================================================
    # BACKWARD COMPATIBILITY METHODS
    # These methods delegate to the query classes for backward compatibility.
    # New code should use db.teams.method(), db.players.method(), etc.
    # ============================================================================
    
    def add_team(self, name: str) -> int:
        """Add a team and return team_id."""
        if not self.conn:
            self.connect()
        return self.teams.add_team(name)
    
    def get_all_teams(self) -> list:
        """Get all teams from the database."""
        if not self.conn:
            self.connect()
        return self.teams.get_all_teams()
    
    def get_team_by_id(self, team_id: int) -> Optional[dict]:
        """Get a team by ID."""
        if not self.conn:
            self.connect()
        return self.teams.get_team_by_id(team_id)
    
    def add_player(self, team_id: int, player_number: str, name: Optional[str] = None) -> int:
        """Add a player and return player_id."""
        if not self.conn:
            self.connect()
        return self.players.add_player(team_id, player_number, name)
    
    def start_game(self, team_us_id: int, team_them_id: int, notes: Optional[str] = None, game_date: Optional[datetime] = None) -> int:
        """Start a new game and return game_id."""
        if not self.conn:
            self.connect()
        return self.games.start_game(team_us_id, team_them_id, notes, game_date)
    
    def start_rally(self, game_id: int, rally_number: int, serving_team_id: int) -> int:
        """Start a new rally and return rally_id."""
        if not self.conn:
            self.connect()
        return self.rallies.start_rally(game_id, rally_number, serving_team_id)
    
    def add_contact(self, rally_id: int, sequence_number: int, contact_type: str, 
                   team_id: int, player_id: Optional[int] = None, 
                   x: Optional[int] = None, y: Optional[int] = None,
                   timecode: Optional[int] = None,
                   outcome: str = 'continue', rating: Optional[int] = None) -> int:
        """Add a ball contact and return contact_id."""
        if not self.conn:
            self.connect()
        return self.contacts.add_contact(rally_id, sequence_number, contact_type, team_id, 
                                        player_id, x, y, timecode, outcome, rating)
    
    def end_rally(self, rally_id: int, point_winner_id: int, rally_end_time: Optional[datetime] = None):
        """End a rally and record the point winner."""
        if not self.conn:
            self.connect()
        return self.rallies.end_rally(rally_id, point_winner_id, rally_end_time)
    
    def unend_rally(self, rally_id: int) -> None:
        """Reset a rally's point_winner_id and rally_end_time to NULL."""
        if not self.conn:
            self.connect()
        return self.rallies.unend_rally(rally_id)
    
    def update_contact_outcome(self, contact_id: int, outcome: str):
        """Update the outcome of a contact."""
        if not self.conn:
            self.connect()
        return self.contacts.update_contact_outcome(contact_id, outcome)
    
    def delete_contact(self, contact_id: int) -> bool:
        """Delete a contact by ID."""
        if not self.conn:
            self.connect()
        return self.contacts.delete_contact(contact_id)
    
    def get_rally_contacts(self, rally_id: int) -> list:
        """Get all contacts for a rally, ordered by sequence number."""
        if not self.conn:
            self.connect()
        return self.contacts.get_rally_contacts(rally_id)
    
    def get_last_contact(self, rally_id: int) -> Optional[dict]:
        """Get the most recent contact in a rally."""
        if not self.conn:
            self.connect()
        return self.contacts.get_last_contact(rally_id)
    
    def delete_game_rallies_and_contacts(self, game_id: int) -> tuple[int, int]:
        """Delete all rallies and contacts for a given game."""
        if not self.conn:
            self.connect()
        return self.rallies.delete_game_rallies_and_contacts(game_id)
    
    def get_player_by_number(self, team_id: int, player_number: str) -> Optional[dict]:
        """Get a player by team and number."""
        if not self.conn:
            self.connect()
        return self.players.get_player_by_number(team_id, player_number)
    
    def get_current_rally_sequence(self, rally_id: int) -> int:
        """Get the next sequence number for a rally."""
        if not self.conn:
            self.connect()
        return self.contacts.get_current_rally_sequence(rally_id)
    
    def add_player_to_game(self, game_id: int, team_id: int, player_id: int, game_role_code: str = None) -> int:
        """Add a player to a specific game's roster."""
        if not self.conn:
            self.connect()
        return self.game_players.add_player_to_game(game_id, team_id, player_id, game_role_code)
    
    def get_game_players(self, game_id: int, team_id: int) -> list:
        """Get all players for a specific team in a specific game."""
        if not self.conn:
            self.connect()
        return self.game_players.get_game_players(game_id, team_id)
    
    def remove_player_from_game(self, game_id: int, team_id: int, player_id: int):
        """Remove a player from a game's roster."""
        if not self.conn:
            self.connect()
        return self.game_players.remove_player_from_game(game_id, team_id, player_id)
    
    def get_player_by_number_for_game(self, game_id: int, team_id: int, player_number: str) -> Optional[dict]:
        """Get a player by number for a specific game and team."""
        if not self.conn:
            self.connect()
        return self.game_players.get_player_by_number_for_game(game_id, team_id, player_number)
    
    def update_game_video_path(self, game_id: int, video_file_path: Optional[str]):
        """Update the video file path for a game."""
        if not self.conn:
            self.connect()
        return self.games.update_game_video_path(game_id, video_file_path)
    
    def get_game_video_path(self, game_id: int) -> Optional[str]:
        """Get the video file path for a game."""
        if not self.conn:
            self.connect()
        return self.games.get_game_video_path(game_id)
    
    def update_game_still_image_path(self, game_id: int, still_image_path: Optional[str]):
        """Update the still image file path for a game."""
        if not self.conn:
            self.connect()
        return self.games.update_game_still_image_path(game_id, still_image_path)
    
    def get_game_still_image_path(self, game_id: int) -> Optional[str]:
        """Get the still image file path for a game."""
        if not self.conn:
            self.connect()
        return self.games.get_game_still_image_path(game_id)
    
    def save_game_court_boundaries(self, game_id: int, court_points: dict, homography_matrix=None):
        """Save court boundary coordinates for a game."""
        if not self.conn:
            self.connect()
        return self.games.save_game_court_boundaries(game_id, court_points, homography_matrix)
    
    def get_game_court_boundaries(self, game_id: int) -> Optional[dict]:
        """Get court boundary coordinates for a game."""
        if not self.conn:
            self.connect()
        return self.games.get_game_court_boundaries(game_id)
    
    def delete_game(self, game_id: int) -> dict:
        """Delete a single game and all related data."""
        if not self.conn:
            self.connect()
        return self.games.delete_game(game_id)
    
    def mark_game_ended(self, game_id: int):
        """Mark a game as ended."""
        if not self.conn:
            self.connect()
        return self.games.mark_game_ended(game_id)
    
    def is_game_ended(self, game_id: int) -> bool:
        """Check if a game is ended."""
        if not self.conn:
            self.connect()
        return self.games.is_game_ended(game_id)
    
    # DEPRECATED - use property accessors instead
    def _save_game_court_boundaries_old(self, game_id: int, court_points: dict, homography_matrix=None):
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
        
        # Get scroll offsets (default to 0 if not provided)
        scroll_offset_x = court_points.get('scroll_offset_x', 0)
        scroll_offset_y = court_points.get('scroll_offset_y', 0)
        video_offset_x = court_points.get('video_offset_x', 0)
        video_offset_y = court_points.get('video_offset_y', 0)
        video_width = court_points.get('video_width', 0)
        video_height = court_points.get('video_height', 0)
        scene_width = court_points.get('scene_width', 0)
        scene_height = court_points.get('scene_height', 0)
        
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
                court_corner_tl_x = %s, court_corner_tl_y = %s,
                court_corner_tr_x = %s, court_corner_tr_y = %s,
                court_corner_bl_x = %s, court_corner_bl_y = %s,
                court_corner_br_x = %s, court_corner_br_y = %s,
                court_centerline_top_x = %s, court_centerline_top_y = %s,
                court_centerline_bottom_x = %s, court_centerline_bottom_y = %s,
                court_y200_left_x = %s, court_y200_left_y = %s,
                court_y200_right_x = %s, court_y200_right_y = %s,
                court_y400_left_x = %s, court_y400_left_y = %s,
                court_y400_right_x = %s, court_y400_right_y = %s,
                homography_matrix = %s,
                scroll_offset_x = %s,
                scroll_offset_y = %s,
                video_offset_x = %s,
                video_offset_y = %s,
                video_width = %s,
                video_height = %s,
                scene_width = %s,
                scene_height = %s
            WHERE game_id = %s
        """, (tl_x, tl_y, tr_x, tr_y, bl_x, bl_y, br_x, br_y, ct_x, ct_y, cb_x, cb_y,
              y200l_x, y200l_y, y200r_x, y200r_y, y400l_x, y400l_y, y400r_x, y400r_y,
              homography_json, scroll_offset_x, scroll_offset_y, video_offset_x, video_offset_y,
              video_width, video_height, scene_width, scene_height, game_id))
        self.conn.commit()
        logger.debug(f"Court boundaries saved for game {game_id} with scroll offsets X:{scroll_offset_x}, Y:{scroll_offset_y}")
    
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
                   homography_matrix,
                   scroll_offset_x, scroll_offset_y,
                   video_offset_x, video_offset_y,
                   video_width, video_height,
                   scene_width, scene_height
            FROM games WHERE game_id = %s
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
                logger.warning(f"Failed to deserialize homography matrix: {e}")
        
        # Get scroll offsets and dimensions (default to 0 if not present or None)
        scroll_offset_x = result[21] if len(result) > 21 and result[21] is not None else 0
        scroll_offset_y = result[22] if len(result) > 22 and result[22] is not None else 0
        video_offset_x = result[23] if len(result) > 23 and result[23] is not None else 0
        video_offset_y = result[24] if len(result) > 24 and result[24] is not None else 0
        video_width = result[25] if len(result) > 25 and result[25] is not None else 0
        video_height = result[26] if len(result) > 26 and result[26] is not None else 0
        scene_width = result[27] if len(result) > 27 and result[27] is not None else 0
        scene_height = result[28] if len(result) > 28 and result[28] is not None else 0
        
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
            'homography_matrix': homography_matrix,
            'scroll_offset_x': scroll_offset_x,
            'scroll_offset_y': scroll_offset_y,
            'video_offset_x': video_offset_x,
            'video_offset_y': video_offset_y,
            'video_width': video_width,
            'video_height': video_height,
            'scene_width': scene_width,
            'scene_height': scene_height
        }
    
    def delete_game(self, game_id: int) -> dict:
        """Delete a single game and all related data.
        
        This method deletes:
        - contacts (via rallies)
        - rallies
        - game_players
        - player_stats
        - substitutions
        - libero_actions
        - rotation_state (for teams in the game)
        - the game itself
        
        Args:
            game_id: The ID of the game to delete
            
        Returns:
            Dictionary with counts of deleted records:
            {
                'contacts': int,
                'rallies': int,
                'game_players': int,
                'player_stats': int,
                'substitutions': int,
                'libero_actions': int,
                'rotation_state': int,
                'game': int (should be 1 if successful, 0 if game not found)
            }
            
        Raises:
            ValueError: If game_id is invalid
            Exception: If database operations fail
        """
        if not game_id or game_id <= 0:
            raise ValueError("game_id must be a positive integer")
        
        if not self.conn:
            self.connect()
        
        try:
            cursor = self.conn.cursor()
            
            # Verify game exists and get team IDs
            cursor.execute("""
                SELECT game_id, team_us_id, team_them_id 
                FROM games 
                WHERE game_id = %s
            """, (game_id,))
            game = cursor.fetchone()
            
            if not game:
                return {
                    'contacts': 0,
                    'rallies': 0,
                    'game_players': 0,
                    'player_stats': 0,
                    'substitutions': 0,
                    'libero_actions': 0,
                    'active_lineup': 0,
                    'rotation_state': 0,
                    'game': 0
                }
            
            team_us_id, team_them_id = game[1], game[2]
            deleted_counts = {}
            
            # 1. Delete contacts (via rallies)
            cursor.execute("""
                DELETE FROM contacts 
                WHERE rally_id IN (
                    SELECT rally_id FROM rallies WHERE game_id = %s
                )
            """, (game_id,))
            deleted_counts['contacts'] = cursor.rowcount
            
            # 2. Delete rallies
            cursor.execute("DELETE FROM rallies WHERE game_id = %s", (game_id,))
            deleted_counts['rallies'] = cursor.rowcount
            
            # 3. Delete game_players
            cursor.execute("DELETE FROM game_players WHERE game_id = %s", (game_id,))
            deleted_counts['game_players'] = cursor.rowcount
            
            # 4. Delete player_stats
            cursor.execute("DELETE FROM player_stats WHERE game_id = %s", (game_id,))
            deleted_counts['player_stats'] = cursor.rowcount
            
            # 5. Delete substitutions
            cursor.execute("DELETE FROM substitutions WHERE game_id = %s", (game_id,))
            deleted_counts['substitutions'] = cursor.rowcount
            
            # 6. Delete libero_actions
            cursor.execute("DELETE FROM libero_actions WHERE game_id = %s", (game_id,))
            deleted_counts['libero_actions'] = cursor.rowcount
            
            # 7. Delete active_lineup for the game
            cursor.execute("DELETE FROM active_lineup WHERE game_id = %s", (game_id,))
            deleted_counts['active_lineup'] = cursor.rowcount
            
            # 8. Delete rotation_state for the game
            cursor.execute("DELETE FROM rotation_state WHERE game_id = %s", (game_id,))
            deleted_counts['rotation_state'] = cursor.rowcount
            
            # 9. Finally, delete the game itself
            cursor.execute("DELETE FROM games WHERE game_id = %s", (game_id,))
            deleted_counts['game'] = cursor.rowcount
            
            self.conn.commit()
            
            return deleted_counts
            
        except Exception as e:
            self.conn.rollback()
            raise Exception(f"Failed to delete game {game_id}: {str(e)}")
    
    def mark_game_ended(self, game_id: int):
        """Mark a game as ended.
        
        Args:
            game_id: The ID of the game to mark as ended
        """
        if not self.conn:
            self.connect()
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE games SET is_ended = TRUE WHERE game_id = %s",
            (game_id,)
        )
        self.conn.commit()
    
    def is_game_ended(self, game_id: int) -> bool:
        """Check if a game is ended.
        
        Args:
            game_id: The ID of the game to check
            
        Returns:
            True if the game is ended, False otherwise
        """
        if not self.conn:
            self.connect()
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT is_ended FROM games WHERE game_id = %s",
            (game_id,)
        )
        result = cursor.fetchone()
        if result:
            return bool(result[0])
        return False


if __name__ == "__main__":
    # Initialize the database connection
    # Make sure PostgreSQL is running and configuration is correct
    db = VideoStatsDB()
    try:
        db.connect()
        logger.info("VideoStats PostgreSQL database connection successful!")
        logger.info("Use migration files to create/update schema.")
        db.close()
    except Exception as e:
        logger.error(f"Failed to connect to PostgreSQL database: {e}")
        logger.info("Please check your database configuration and ensure PostgreSQL is running.")


