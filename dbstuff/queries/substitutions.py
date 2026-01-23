"""
Substitution and libero action queries.
"""
import psycopg2.extras
from typing import List, Optional


class SubstitutionQueries:
    """Handles substitutions and libero_actions tables."""
    
    def __init__(self, conn):
        self.conn = conn
    
    # Substitutions
    def add_substitution(self, team_id: int, out_player_id: int, in_player_id: int,
                        game_id: int, out_position: Optional[int] = None,
                        in_position: Optional[int] = None) -> int:
        """Record a substitution."""
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO substitutions 
               (team_id, out_player_id, in_player_id, game_id, out_position, in_position)
               VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
            (team_id, out_player_id, in_player_id, game_id, out_position, in_position)
        )
        sub_id = cursor.fetchone()[0]
        self.conn.commit()
        return sub_id
    
    def delete_substitution(self, substitution_id: int):
        """Delete a substitution record."""
        cursor = self.conn.cursor()
        cursor.execute(
            "DELETE FROM substitutions WHERE id = %s",
            (substitution_id,)
        )
        self.conn.commit()
    
    def get_substitutions_for_game(self, game_id: int) -> List[dict]:
        """Get all substitutions for a game."""
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            """SELECT * FROM substitutions 
               WHERE game_id = %s 
               ORDER BY created_at""",
            (game_id,)
        )
        return cursor.fetchall()
    
    def delete_game_substitutions(self, game_id: int):
        """Delete all substitutions for a game."""
        cursor = self.conn.cursor()
        cursor.execute(
            "DELETE FROM substitutions WHERE game_id = %s",
            (game_id,)
        )
        self.conn.commit()
    
    # Libero Actions
    def add_libero_action(self, team_id: int, libero_id: int, replaced_player_id: int,
                         replaced_position: int, action: str, game_id: int) -> int:
        """Record a libero action (enter/exit)."""
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO libero_actions 
               (team_id, libero_id, replaced_player_id, replaced_position, action, game_id)
               VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
            (team_id, libero_id, replaced_player_id, replaced_position, action, game_id)
        )
        action_id = cursor.fetchone()[0]
        self.conn.commit()
        return action_id
    
    def delete_libero_action(self, action_id: int):
        """Delete a libero action record."""
        cursor = self.conn.cursor()
        cursor.execute(
            "DELETE FROM libero_actions WHERE id = %s",
            (action_id,)
        )
        self.conn.commit()
    
    def get_libero_actions_for_game(self, game_id: int, team_id: Optional[int] = None) -> List[dict]:
        """Get libero actions for a game, optionally filtered by team."""
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if team_id is not None:
            cursor.execute(
                """SELECT * FROM libero_actions 
                   WHERE game_id = %s AND team_id = %s 
                   ORDER BY created_at""",
                (game_id, team_id)
            )
        else:
            cursor.execute(
                """SELECT * FROM libero_actions 
                   WHERE game_id = %s 
                   ORDER BY created_at""",
                (game_id,)
            )
        return cursor.fetchall()
    
    def get_active_libero_entry(self, game_id: int, team_id: int, 
                               replaced_position: int) -> Optional[dict]:
        """Get active libero entry for a position (no exit yet)."""
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            """SELECT * FROM libero_actions
               WHERE game_id = %s AND team_id = %s 
                     AND replaced_position = %s AND action = 'enter'
               ORDER BY created_at DESC
               LIMIT 1""",
            (game_id, team_id, replaced_position)
        )
        return cursor.fetchone()
    
    def delete_game_libero_actions(self, game_id: int):
        """Delete all libero actions for a game."""
        cursor = self.conn.cursor()
        cursor.execute(
            "DELETE FROM libero_actions WHERE game_id = %s",
            (game_id,)
        )
        self.conn.commit()
