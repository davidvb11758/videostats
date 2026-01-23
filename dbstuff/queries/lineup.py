"""
Active lineup queries.
"""
import psycopg2.extras
from typing import List, Dict, Optional


class LineupQueries:
    """Handles active_lineup table operations."""
    
    def __init__(self, conn):
        self.conn = conn
    
    def get_active_lineup(self, game_id: int, team_id: int) -> List[dict]:
        """Get current active lineup for a team in a game."""
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            """SELECT * FROM active_lineup
               WHERE game_id = %s AND team_id = %s
               ORDER BY position_number""",
            (game_id, team_id)
        )
        return cursor.fetchall()
    
    def set_lineup_position(self, game_id: int, team_id: int, position_number: int,
                           player_id: int, role_code: str, is_server: bool = False):
        """Set or update a position in the active lineup."""
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO active_lineup 
               (game_id, team_id, position_number, player_id, role_code, is_server)
               VALUES (%s, %s, %s, %s, %s, %s)
               ON CONFLICT (game_id, team_id, position_number)
               DO UPDATE SET player_id = EXCLUDED.player_id, 
                            role_code = EXCLUDED.role_code,
                            is_server = EXCLUDED.is_server""",
            (game_id, team_id, position_number, player_id, role_code, is_server)
        )
        self.conn.commit()
    
    def clear_lineup(self, game_id: int, team_id: int):
        """Clear all lineup positions for a team."""
        cursor = self.conn.cursor()
        cursor.execute(
            "DELETE FROM active_lineup WHERE game_id = %s AND team_id = %s",
            (game_id, team_id)
        )
        self.conn.commit()
    
    def update_lineup_position(self, game_id: int, team_id: int, position_number: int,
                              player_id: Optional[int] = None, role_code: Optional[str] = None):
        """Update specific fields for a lineup position."""
        updates = []
        params = []
        if player_id is not None:
            updates.append("player_id = %s")
            params.append(player_id)
        if role_code is not None:
            updates.append("role_code = %s")
            params.append(role_code)
        
        if updates:
            params.extend([game_id, team_id, position_number])
            cursor = self.conn.cursor()
            cursor.execute(
                f"""UPDATE active_lineup SET {', '.join(updates)}
                    WHERE game_id = %s AND team_id = %s AND position_number = %s""",
                tuple(params)
            )
            self.conn.commit()
    
    def set_server(self, game_id: int, team_id: int, position_number: int):
        """Mark a position as the server and clear others."""
        cursor = self.conn.cursor()
        # Clear all servers first
        cursor.execute(
            """UPDATE active_lineup SET is_server = FALSE
               WHERE game_id = %s AND team_id = %s AND position_number != %s""",
            (game_id, team_id, position_number)
        )
        # Set the specified position as server
        cursor.execute(
            """UPDATE active_lineup SET is_server = TRUE
               WHERE game_id = %s AND team_id = %s AND position_number = %s""",
            (game_id, team_id, position_number)
        )
        self.conn.commit()
    
    def get_server_position(self, game_id: int, team_id: int) -> Optional[int]:
        """Get the position number of the current server."""
        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT position_number FROM active_lineup
               WHERE game_id = %s AND team_id = %s AND is_server = TRUE
               LIMIT 1""",
            (game_id, team_id)
        )
        result = cursor.fetchone()
        return result[0] if result else None
    
    def get_player_at_position(self, game_id: int, team_id: int, 
                              position_number: int) -> Optional[dict]:
        """Get the player at a specific position."""
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            """SELECT al.*, p.name, p.player_number, p.jersey
               FROM active_lineup al
               LEFT JOIN players p ON al.player_id = p.player_id
               WHERE al.game_id = %s AND al.team_id = %s AND al.position_number = %s""",
            (game_id, team_id, position_number)
        )
        return cursor.fetchone()
