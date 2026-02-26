"""
Game-related database queries.
"""
import psycopg2.extras
from typing import Optional, List
from datetime import datetime


class GameQueries:
    """Handles all game-related database operations."""
    
    def __init__(self, conn):
        """
        Initialize with database connection.
        
        Args:
            conn: psycopg2 database connection
        """
        self.conn = conn
    
    def start_game(self, team_us_id: int, team_them_id: int, 
                   notes: Optional[str] = None, 
                   game_date: Optional[datetime] = None) -> int:
        """
        Start a new game and return game_id.
        
        Args:
            team_us_id: ID of team_us
            team_them_id: ID of team_them
            notes: Optional notes for the game
            game_date: Optional game date. If None, uses CURRENT_TIMESTAMP.
        
        Returns:
            game_id of the newly created game
            
        Raises:
            ValueError: If both teams are the same
        """
        if team_us_id == team_them_id:
            raise ValueError("A game must have two different teams.")
        
        cursor = self.conn.cursor()
        if game_date:
            cursor.execute(
                "INSERT INTO games (team_us_id, team_them_id, notes, game_date) "
                "VALUES (%s, %s, %s, %s) RETURNING game_id",
                (team_us_id, team_them_id, notes, game_date)
            )
        else:
            cursor.execute(
                "INSERT INTO games (team_us_id, team_them_id, notes) "
                "VALUES (%s, %s, %s) RETURNING game_id",
                (team_us_id, team_them_id, notes)
            )
        game_id = cursor.fetchone()[0]
        self.conn.commit()
        return game_id
    
    def get_game_by_id(self, game_id: int) -> Optional[dict]:
        """
        Get game by ID.
        
        Args:
            game_id: The game ID
            
        Returns:
            Game record as dict or None if not found
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT * FROM games WHERE game_id = %s", (game_id,))
        return cursor.fetchone()
    
    def get_game_teams(self, game_id: int) -> Optional[tuple]:
        """
        Get team IDs for a game.
        
        Args:
            game_id: The game ID
            
        Returns:
            Tuple of (team_us_id, team_them_id) or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT team_us_id, team_them_id FROM games WHERE game_id = %s",
            (game_id,)
        )
        return cursor.fetchone()
    
    def get_all_games(self, team_id: Optional[int] = None) -> List[dict]:
        """
        Get all games, optionally filtered by team.
        
        Args:
            team_id: Optional team ID to filter by
            
        Returns:
            List of game records
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if team_id:
            cursor.execute(
                """SELECT game_id, game_date, team_us_id, team_them_id, notes 
                   FROM games 
                   WHERE team_us_id = %s OR team_them_id = %s 
                   ORDER BY game_date DESC""",
                (team_id, team_id)
            )
        else:
            cursor.execute(
                "SELECT * FROM games ORDER BY game_date DESC"
            )
        return cursor.fetchall()
    
    def update_game_video_path(self, game_id: int, video_file_path: Optional[str]):
        """
        Update the video file path for a game.
        
        Args:
            game_id: The game ID
            video_file_path: Path to the video file (or None to clear it)
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE games SET video_file_path = %s WHERE game_id = %s",
            (video_file_path, game_id)
        )
        self.conn.commit()
    
    def get_game_video_path(self, game_id: int) -> Optional[str]:
        """
        Get the video file path for a game.
        
        Args:
            game_id: The game ID
            
        Returns:
            The video file path, or None if not set
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT video_file_path FROM games WHERE game_id = %s",
            (game_id,)
        )
        result = cursor.fetchone()
        return result[0] if result and result[0] else None
    
    def update_game_still_image_path(self, game_id: int, still_image_path: Optional[str]):
        """
        Update the still image file path for a game.
        
        Args:
            game_id: The game ID
            still_image_path: Path to the still image file (or None to clear it)
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE games SET still_image_path = %s WHERE game_id = %s",
            (still_image_path, game_id)
        )
        self.conn.commit()
    
    def get_game_still_image_path(self, game_id: int) -> Optional[str]:
        """
        Get the still image file path for a game.
        
        Args:
            game_id: The game ID
            
        Returns:
            The still image file path, or None if not set
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT still_image_path FROM games WHERE game_id = %s",
            (game_id,)
        )
        result = cursor.fetchone()
        return result[0] if result and result[0] else None
    
    def update_game_notes(self, game_id: int, notes: str):
        """
        Update game notes.
        
        Args:
            game_id: The game ID
            notes: New notes text
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE games SET notes = %s WHERE game_id = %s",
            (notes, game_id)
        )
        self.conn.commit()
    
    def mark_game_ended(self, game_id: int):
        """
        Mark a game as ended.
        
        Args:
            game_id: The ID of the game to mark as ended
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE games SET is_ended = TRUE WHERE game_id = %s",
            (game_id,)
        )
        self.conn.commit()
    
    def is_game_ended(self, game_id: int) -> bool:
        """
        Check if a game is ended.
        
        Args:
            game_id: The ID of the game to check
            
        Returns:
            True if the game is ended, False otherwise
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT is_ended FROM games WHERE game_id = %s",
            (game_id,)
        )
        result = cursor.fetchone()
        if result:
            return bool(result[0])
        return False
    
    def save_game_court_boundaries(self, game_id: int, court_points: dict, homography_matrix=None):
        """
        Save court boundary coordinates for a game.
        
        Args:
            game_id: The game ID
            court_points: Dictionary with keys like 'corner_tl', 'corner_tr', etc.
            homography_matrix: Optional numpy array (3x3) representing the homography matrix
        """
        def _py_float(v):
            return float(v) if v is not None else None

        def _py_int(v):
            return int(v) if v is not None else None

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
                return point.x(), point.y()
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
            homography_list = homography_matrix.tolist()
            homography_json = json.dumps(homography_list)
        
        # Coerce all numerics to native Python types for psycopg2 (avoid numpy "schema np" error)
        tl_x, tl_y = _py_float(tl_x), _py_float(tl_y)
        tr_x, tr_y = _py_float(tr_x), _py_float(tr_y)
        bl_x, bl_y = _py_float(bl_x), _py_float(bl_y)
        br_x, br_y = _py_float(br_x), _py_float(br_y)
        ct_x, ct_y = _py_float(ct_x), _py_float(ct_y)
        cb_x, cb_y = _py_float(cb_x), _py_float(cb_y)
        y200l_x, y200l_y = _py_float(y200l_x), _py_float(y200l_y)
        y200r_x, y200r_y = _py_float(y200r_x), _py_float(y200r_y)
        y400l_x, y400l_y = _py_float(y400l_x), _py_float(y400l_y)
        y400r_x, y400r_y = _py_float(y400r_x), _py_float(y400r_y)
        scroll_offset_x = _py_int(scroll_offset_x)
        scroll_offset_y = _py_int(scroll_offset_y)
        video_offset_x = _py_int(video_offset_x)
        video_offset_y = _py_int(video_offset_y)
        video_width = _py_float(video_width)
        video_height = _py_float(video_height)
        scene_width = _py_float(scene_width)
        scene_height = _py_float(scene_height)
        game_id = int(game_id)
        
        try:
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
        except Exception:
            self.conn.rollback()
            raise
    
    def get_game_court_boundaries(self, game_id: int) -> Optional[dict]:
        """
        Get court boundary coordinates for a game.
        
        Args:
            game_id: The game ID
            
        Returns:
            Dictionary with court points (as tuples (x, y)), or None if not set
        """
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
            except Exception:
                pass
        
        # Get scroll offsets and dimensions (default to 0 if not present or None)
        scroll_offset_x = result[21] if len(result) > 21 and result[21] is not None else 0
        scroll_offset_y = result[22] if len(result) > 22 and result[22] is not None else 0
        video_offset_x = result[23] if len(result) > 23 and result[23] is not None else 0
        video_offset_y = result[24] if len(result) > 24 and result[24] is not None else 0
        video_width = result[25] if len(result) > 25 and result[25] is not None else 0
        video_height = result[26] if len(result) > 26 and result[26] is not None else 0
        scene_width = result[27] if len(result) > 27 and result[27] is not None else 0
        scene_height = result[28] if len(result) > 28 and result[28] is not None else 0
        
        # Return as tuples
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
    
    def get_game_with_teams(self, game_id: int) -> Optional[dict]:
        """
        Get a single game with team names included.
        
        Args:
            game_id: The game ID
            
        Returns:
            Game record with team information or None
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT g.game_id, g.game_date, 
                   t1.name as team_us_name, t2.name as team_them_name,
                   g.team_us_id, g.team_them_id, g.notes
            FROM games g
            INNER JOIN teams t1 ON g.team_us_id = t1.team_id
            INNER JOIN teams t2 ON g.team_them_id = t2.team_id
            WHERE g.game_id = %s
        """, (game_id,))
        return cursor.fetchone()
    
    def get_all_games_with_teams(self) -> List[dict]:
        """
        Get all games with team names included.
        
        Returns:
            List of game records with team information
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT g.game_id, g.game_date, 
                   t1.name as team_us_name, t2.name as team_them_name,
                   g.team_us_id, g.team_them_id,
                   g.video_file_path, g.notes, g.is_ended
            FROM games g
            INNER JOIN teams t1 ON g.team_us_id = t1.team_id
            INNER JOIN teams t2 ON g.team_them_id = t2.team_id
            ORDER BY g.game_date DESC, g.game_id DESC
        """)
        return cursor.fetchall()
    
    def delete_game(self, game_id: int) -> dict:
        """
        Delete a single game and all related data.
        
        Args:
            game_id: The ID of the game to delete
            
        Returns:
            Dictionary with counts of deleted records
            
        Raises:
            ValueError: If game_id is invalid
            Exception: If database operations fail
        """
        if not game_id or game_id <= 0:
            raise ValueError("game_id must be a positive integer")
        
        try:
            cursor = self.conn.cursor()
            
            # Verify game exists and get team IDs
            cursor.execute(
                "SELECT game_id, team_us_id, team_them_id FROM games WHERE game_id = %s",
                (game_id,)
            )
            game = cursor.fetchone()
            
            if not game:
                return {
                    'contacts': 0, 'rallies': 0, 'game_players': 0,
                    'player_stats': 0, 'substitutions': 0, 'libero_actions': 0,
                    'active_lineup': 0, 'rotation_state': 0, 'events': 0, 'game': 0
                }
            
            deleted_counts = {}
            
            # Delete in order (foreign key constraints)
            cursor.execute(
                "DELETE FROM contacts WHERE rally_id IN (SELECT rally_id FROM rallies WHERE game_id = %s)",
                (game_id,)
            )
            deleted_counts['contacts'] = cursor.rowcount
            
            cursor.execute("DELETE FROM rallies WHERE game_id = %s", (game_id,))
            deleted_counts['rallies'] = cursor.rowcount
            
            cursor.execute("DELETE FROM game_players WHERE game_id = %s", (game_id,))
            deleted_counts['game_players'] = cursor.rowcount
            
            cursor.execute("DELETE FROM player_stats WHERE game_id = %s", (game_id,))
            deleted_counts['player_stats'] = cursor.rowcount
            
            cursor.execute("DELETE FROM substitutions WHERE game_id = %s", (game_id,))
            deleted_counts['substitutions'] = cursor.rowcount
            
            cursor.execute("DELETE FROM libero_actions WHERE game_id = %s", (game_id,))
            deleted_counts['libero_actions'] = cursor.rowcount
            
            cursor.execute("DELETE FROM active_lineup WHERE game_id = %s", (game_id,))
            deleted_counts['active_lineup'] = cursor.rowcount
            
            cursor.execute("DELETE FROM rotation_state WHERE game_id = %s", (game_id,))
            deleted_counts['rotation_state'] = cursor.rowcount
            
            cursor.execute("DELETE FROM events WHERE game_id = %s", (game_id,))
            deleted_counts['events'] = cursor.rowcount
            
            cursor.execute("DELETE FROM games WHERE game_id = %s", (game_id,))
            deleted_counts['game'] = cursor.rowcount
            
            self.conn.commit()
            
            return deleted_counts
            
        except Exception as e:
            self.conn.rollback()
            raise Exception(f"Failed to delete game {game_id}: {str(e)}")
    
    def update_game_notes(self, game_id: int, notes: str):
        """
        Update the notes field for a game.
        
        Args:
            game_id: The game ID
            notes: The notes text
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE games SET notes = %s WHERE game_id = %s",
            (notes, game_id)
        )
        self.conn.commit()
    
    def get_game_full_details(self, game_id: int) -> Optional[dict]:
        """
        Get full game details including court boundaries and video paths.
        
        Args:
            game_id: The game ID
            
        Returns:
            Dictionary with all game fields or None if not found
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT game_id, team_us_id, team_them_id, notes,
                   video_file_path, still_image_path,
                   court_corner_tl_x, court_corner_tl_y,
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
            FROM games
            WHERE game_id = %s
        """, (game_id,))
        return cursor.fetchone()
    
    def update_game_court_and_video(self, game_id: int, video_path: str, still_image_path: str, court_data: tuple):
        """
        Update game with court boundaries and video paths.
        
        Args:
            game_id: The game ID
            video_path: Video file path
            still_image_path: Still image path
            court_data: Tuple of court boundary coordinates
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE games SET
                video_file_path = %s,
                still_image_path = %s,
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
                homography_matrix = %s
            WHERE game_id = %s
        """, (video_path, still_image_path) + court_data + (game_id,))
        self.conn.commit()
