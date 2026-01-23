"""
Player-related database queries.
"""
import psycopg2.extras
from typing import Optional, List


class PlayerQueries:
    """Handles all player-related database operations."""
    
    def __init__(self, conn):
        """
        Initialize with database connection.
        
        Args:
            conn: psycopg2 database connection
        """
        self.conn = conn
    
    def add_player(self, team_id: int, player_number: str, name: Optional[str] = None,
                   role_code: Optional[str] = None, jersey: Optional[str] = None) -> int:
        """
        Add a player and return player_id.
        
        Args:
            team_id: The team ID
            player_number: Player number (can be alphanumeric)
            name: Optional player name
            role_code: Optional role code
            jersey: Optional jersey number/identifier
            
        Returns:
            player_id of the newly created player
        """
        cursor = self.conn.cursor()
        player_number_str = str(player_number).strip()
        cursor.execute(
            "INSERT INTO players (team_id, player_number, name, role_code, jersey) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING player_id",
            (team_id, player_number_str, name, role_code, jersey)
        )
        player_id = cursor.fetchone()[0]
        self.conn.commit()
        return player_id
    
    def get_player_by_id(self, player_id: int) -> Optional[dict]:
        """
        Get player by ID.
        
        Args:
            player_id: The player ID
            
        Returns:
            Player record as dict or None if not found
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT * FROM players WHERE player_id = %s", (player_id,))
        return cursor.fetchone()
    
    def get_player_by_number(self, team_id: int, player_number: str) -> Optional[dict]:
        """
        Get a player by team and number.
        
        Args:
            team_id: The team ID
            player_number: Player number (can be alphanumeric)
            
        Returns:
            Player record as dict or None if not found
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            "SELECT * FROM players WHERE team_id = %s AND player_number = %s",
            (team_id, str(player_number).strip())
        )
        return cursor.fetchone()
    
    def get_players_by_team(self, team_id: int) -> List[dict]:
        """
        Get all players for a team.
        
        Args:
            team_id: The team ID
            
        Returns:
            List of player records
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            """SELECT * FROM players 
               WHERE team_id = %s 
               ORDER BY 
                   CASE 
                       WHEN player_number ~ '^[0-9]+$' 
                       THEN CAST(player_number AS INTEGER)
                       ELSE 999999
                   END,
                   player_number""",
            (team_id,)
        )
        return cursor.fetchall()
    
    def update_player_role(self, player_id: int, role_code: str):
        """
        Update player's role code.
        
        Args:
            player_id: The player ID
            role_code: New role code
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE players SET role_code = %s WHERE player_id = %s",
            (role_code, player_id)
        )
        self.conn.commit()
    
    def update_player_active_status(self, player_id: int, is_active: bool):
        """
        Update player's active status.
        
        Args:
            player_id: The player ID
            is_active: Active status
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE players SET is_active = %s WHERE player_id = %s",
            (is_active, player_id)
        )
        self.conn.commit()
    
    def get_player_info(self, player_id: int) -> Optional[tuple]:
        """
        Get player name, jersey, and number.
        
        Args:
            player_id: The player ID
            
        Returns:
            Tuple of (name, jersey, player_number) or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT name, jersey, player_number FROM players WHERE player_id = %s",
            (player_id,)
        )
        return cursor.fetchone()
    
    def get_liberos_by_team(self, team_id: int) -> List[dict]:
        """
        Get all libero players for a team.
        
        Args:
            team_id: The team ID
            
        Returns:
            List of libero player records
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            "SELECT * FROM players WHERE team_id = %s AND role_code = 'Lib'",
            (team_id,)
        )
        return cursor.fetchall()
