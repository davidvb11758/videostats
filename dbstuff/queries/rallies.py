"""
Rally-related database queries.
"""
import psycopg2.extras
from typing import Optional, List
from datetime import datetime


class RallyQueries:
    """Handles all rally-related database operations."""
    
    def __init__(self, conn):
        """
        Initialize with database connection.
        
        Args:
            conn: psycopg2 database connection
        """
        self.conn = conn
    
    def start_rally(self, game_id: int, rally_number: int, serving_team_id: int) -> int:
        """
        Start a new rally and return rally_id.
        
        Args:
            game_id: The game ID
            rally_number: The rally number within the game
            serving_team_id: The team ID that is serving
            
        Returns:
            rally_id of the newly created rally
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO rallies (game_id, rally_number, serving_team_id, rally_start_time)
               VALUES (%s, %s, %s, %s) RETURNING rally_id""",
            (game_id, rally_number, serving_team_id, datetime.now())
        )
        rally_id = cursor.fetchone()[0]
        self.conn.commit()
        return rally_id
    
    def end_rally(self, rally_id: int, point_winner_id: int, 
                  rally_end_time: Optional[datetime] = None):
        """
        End a rally and record the point winner.
        
        Args:
            rally_id: The rally ID to update
            point_winner_id: The team that won the point
            rally_end_time: Optional datetime for rally_end_time. If None, uses current time.
        """
        cursor = self.conn.cursor()
        end_time = rally_end_time if rally_end_time is not None else datetime.now()
        cursor.execute(
            """UPDATE rallies 
               SET point_winner_id = %s, rally_end_time = %s
               WHERE rally_id = %s""",
            (point_winner_id, end_time, rally_id)
        )
        self.conn.commit()
    
    def unend_rally(self, rally_id: int) -> None:
        """
        Reset a rally's point_winner_id and rally_end_time to NULL (un-end the rally).
        
        Args:
            rally_id: The rally ID to update
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """UPDATE rallies 
               SET point_winner_id = NULL, rally_end_time = NULL
               WHERE rally_id = %s""",
            (rally_id,)
        )
        self.conn.commit()
    
    def get_rally_by_id(self, rally_id: int) -> Optional[dict]:
        """
        Get rally by ID.
        
        Args:
            rally_id: The rally ID
            
        Returns:
            Rally record as dict or None if not found
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT * FROM rallies WHERE rally_id = %s", (rally_id,))
        return cursor.fetchone()
    
    def get_rally_by_game_and_number(self, game_id: int, rally_number: int) -> Optional[dict]:
        """
        Get rally by game ID and rally number.
        
        Args:
            game_id: The game ID
            rally_number: The rally number
            
        Returns:
            Rally record as dict or None if not found
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            "SELECT * FROM rallies WHERE game_id = %s AND rally_number = %s",
            (game_id, rally_number)
        )
        return cursor.fetchone()
    
    def get_max_rally_number(self, game_id: int) -> int:
        """
        Get the maximum rally number for a game.
        
        Args:
            game_id: The game ID
            
        Returns:
            Maximum rally number or 0 if no rallies exist
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT MAX(rally_number) FROM rallies WHERE game_id = %s",
            (game_id,)
        )
        result = cursor.fetchone()[0]
        return result if result is not None else 0
    
    def get_completed_rallies_count(self, game_id: int) -> int:
        """
        Get count of completed rallies for a game.
        
        Args:
            game_id: The game ID
            
        Returns:
            Count of rallies with point_winner_id set
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM rallies WHERE game_id = %s AND point_winner_id IS NOT NULL",
            (game_id,)
        )
        return cursor.fetchone()[0]
    
    def get_rallies_by_game(self, game_id: int, completed_only: bool = False) -> List[dict]:
        """
        Get all rallies for a game.
        
        Args:
            game_id: The game ID
            completed_only: If True, only return completed rallies
            
        Returns:
            List of rally records
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if completed_only:
            cursor.execute(
                """SELECT * FROM rallies 
                   WHERE game_id = %s AND point_winner_id IS NOT NULL
                   ORDER BY rally_number""",
                (game_id,)
            )
        else:
            cursor.execute(
                "SELECT * FROM rallies WHERE game_id = %s ORDER BY rally_number",
                (game_id,)
            )
        return cursor.fetchall()
    
    def get_rallies_won_by_team(self, game_id: int, team_id: int) -> List[dict]:
        """
        Get rallies won by a specific team.
        
        Args:
            game_id: The game ID
            team_id: The team ID
            
        Returns:
            List of rally records won by the team
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            """SELECT * FROM rallies 
               WHERE game_id = %s AND point_winner_id = %s
               ORDER BY rally_number""",
            (game_id, team_id)
        )
        return cursor.fetchall()
    
    def get_incomplete_rally(self, game_id: int, rally_number: int) -> Optional[dict]:
        """
        Get an incomplete rally (point_winner_id is NULL).
        
        Args:
            game_id: The game ID
            rally_number: The rally number
            
        Returns:
            Rally record or None if not found or already completed
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            """SELECT * FROM rallies 
               WHERE game_id = %s AND rally_number = %s AND point_winner_id IS NULL""",
            (game_id, rally_number)
        )
        return cursor.fetchone()
    
    def delete_rally(self, rally_id: int) -> bool:
        """
        Delete a rally by ID.
        
        Args:
            rally_id: The rally ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM rallies WHERE rally_id = %s", (rally_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def delete_game_rallies_and_contacts(self, game_id: int) -> tuple:
        """
        Delete all rallies and contacts for a given game.
        
        Args:
            game_id: The ID of the game to delete rallies and contacts for
            
        Returns:
            Tuple of (contacts_deleted, rallies_deleted) counts
        """
        cursor = self.conn.cursor()
        
        # First, delete all contacts for rallies in this game
        cursor.execute("""
            DELETE FROM contacts 
            WHERE rally_id IN (
                SELECT rally_id FROM rallies WHERE game_id = %s
            )
        """, (game_id,))
        contacts_deleted = cursor.rowcount
        
        # Then, delete all rallies for this game
        cursor.execute("DELETE FROM rallies WHERE game_id = %s", (game_id,))
        rallies_deleted = cursor.rowcount
        
        self.conn.commit()
        
        return (contacts_deleted, rallies_deleted)
    
    def get_completed_rallies(self, game_id: int) -> List[dict]:
        """
        Get all completed rallies for a game.
        
        Args:
            game_id: The game ID
            
        Returns:
            List of completed rally records
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT rally_id, point_winner_id
            FROM rallies
            WHERE game_id = %s AND point_winner_id IS NOT NULL
            ORDER BY rally_id
        """, (game_id,))
        return cursor.fetchall()
    
    def count_rallies_by_game(self, game_id: int) -> int:
        """
        Count total rallies for a game.
        
        Args:
            game_id: The game ID
            
        Returns:
            Number of rallies
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM rallies WHERE game_id = %s", (game_id,))
        return cursor.fetchone()[0] or 0
    
    def get_score_summary(self, game_id: int) -> dict:
        """
        Get score summary for a game (completed rallies grouped by winner).
        
        Args:
            game_id: The game ID
            
        Returns:
            Dictionary with point_winner_id -> count mapping
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT point_winner_id, COUNT(*) 
               FROM rallies 
               WHERE game_id = %s AND point_winner_id IS NOT NULL
               GROUP BY point_winner_id""",
            (game_id,)
        )
        results = cursor.fetchall()
        return {point_winner_id: count for point_winner_id, count in results}
    
    def get_max_rally_number(self, game_id: int) -> Optional[int]:
        """
        Get the maximum rally number for a game.
        
        Args:
            game_id: The game ID
            
        Returns:
            Maximum rally number or None if no rallies exist
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT MAX(rally_number) FROM rallies WHERE game_id = %s",
            (game_id,)
        )
        result = cursor.fetchone()
        return result[0] if result and result[0] else None
    
    def get_incomplete_rally(self, game_id: int, rally_number: int) -> Optional[dict]:
        """
        Get an incomplete rally (point_winner_id is NULL) for a specific rally number.
        
        Args:
            game_id: The game ID
            rally_number: The rally number
            
        Returns:
            Rally record as dict or None if not found
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            """SELECT rally_id, serving_team_id 
               FROM rallies 
               WHERE game_id = %s AND rally_number = %s AND point_winner_id IS NULL""",
            (game_id, rally_number)
        )
        return cursor.fetchone()
    
    def get_rally_point_winner(self, rally_id: int) -> Optional[int]:
        """
        Get the point_winner_id for a rally.
        
        Args:
            rally_id: The rally ID
            
        Returns:
            point_winner_id or None if rally not ended
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT point_winner_id FROM rallies WHERE rally_id = %s", (rally_id,))
        result = cursor.fetchone()
        return result[0] if result else None
    
    def get_rally_number_by_id(self, rally_id: int) -> Optional[int]:
        """
        Get the rally_number for a rally.
        
        Args:
            rally_id: The rally ID
            
        Returns:
            rally_number or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT rally_number FROM rallies WHERE rally_id = %s", (rally_id,))
        result = cursor.fetchone()
        return result[0] if result else None
    
    def count_rallies(self, game_id: int) -> int:
        """
        Count rallies for a game.
        
        Args:
            game_id: The game ID
            
        Returns:
            Number of rallies
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM rallies WHERE game_id = %s", (game_id,))
        return cursor.fetchone()[0] or 0
    
    def get_last_rally_by_game(self, game_id: int) -> Optional[dict]:
        """
        Get the most recent rally for a game (by rally_id).
        
        Args:
            game_id: The game ID
            
        Returns:
            Rally record or None if no rallies exist
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT rally_id 
            FROM rallies 
            WHERE game_id = %s
            ORDER BY rally_id DESC
            LIMIT 1
        """, (game_id,))
        return cursor.fetchone()
    
    def get_last_incomplete_rally_by_game(self, game_id: int) -> Optional[dict]:
        """
        Get the most recent incomplete rally (point_winner_id is NULL) for a game.
        
        Args:
            game_id: The game ID
            
        Returns:
            Rally record or None if no incomplete rallies exist
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT rally_id 
            FROM rallies 
            WHERE game_id = %s AND point_winner_id IS NULL
            ORDER BY rally_id DESC
            LIMIT 1
        """, (game_id,))
        return cursor.fetchone()
    
    def get_last_rally_with_winner(self, game_id: int, team_id: int) -> Optional[dict]:
        """
        Get the most recent rally won by a specific team.
        
        Args:
            game_id: The game ID
            team_id: The team ID that won
            
        Returns:
            Rally record or None if no rallies found
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT rally_id, serving_team_id, rally_number
            FROM rallies 
            WHERE game_id = %s AND point_winner_id = %s
            ORDER BY rally_number DESC
            LIMIT 1
        """, (game_id, team_id))
        return cursor.fetchone()
    
    def get_rally_end_time(self, rally_id: int) -> Optional[dict]:
        """
        Get rally_end_time for a rally.
        
        Args:
            rally_id: The rally ID
            
        Returns:
            Dict with rally_id and rally_end_time, or None if not found
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT rally_id, rally_end_time
            FROM rallies
            WHERE rally_id = %s
        """, (rally_id,))
        return cursor.fetchone()