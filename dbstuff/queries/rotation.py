"""
Rotation state queries.
"""
import psycopg2.extras
import json
from typing import Optional
from datetime import datetime


class RotationQueries:
    """Handles rotation_state table operations."""
    
    def __init__(self, conn):
        self.conn = conn
    
    def get_rotation_state(self, game_id: int, team_id: int) -> Optional[dict]:
        """Get rotation state for a team."""
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            """SELECT * FROM rotation_state
               WHERE game_id = %s AND team_id = %s""",
            (game_id, team_id)
        )
        result = cursor.fetchone()
        if result and 'rotation_order' in result and isinstance(result['rotation_order'], str):
            result['rotation_order'] = json.loads(result['rotation_order'])
        return result
    
    def set_rotation_state(self, team_id: int, game_id: int, rotation_order: list,
                          rotation_index: int = 0, serving: bool = False,
                          term_of_service_start: Optional[datetime] = None):
        """Set or update rotation state for a team."""
        cursor = self.conn.cursor()
        rotation_json = json.dumps(rotation_order)
        cursor.execute(
            """INSERT INTO rotation_state 
               (team_id, game_id, rotation_order, rotation_index, serving, term_of_service_start)
               VALUES (%s, %s, %s, %s, %s, %s)
               ON CONFLICT (team_id)
               DO UPDATE SET rotation_order = EXCLUDED.rotation_order,
                            rotation_index = EXCLUDED.rotation_index,
                            serving = EXCLUDED.serving,
                            term_of_service_start = EXCLUDED.term_of_service_start,
                            game_id = EXCLUDED.game_id""",
            (team_id, game_id, rotation_json, rotation_index, serving, term_of_service_start)
        )
        self.conn.commit()
    
    def update_rotation_index(self, game_id: int, team_id: int, rotation_index: int):
        """Update just the rotation index."""
        cursor = self.conn.cursor()
        cursor.execute(
            """UPDATE rotation_state SET rotation_index = %s
               WHERE game_id = %s AND team_id = %s""",
            (rotation_index, game_id, team_id)
        )
        self.conn.commit()
    
    def set_serving_team(self, game_id: int, team_id: int, serving: bool = True,
                        term_of_service_start: Optional[datetime] = None):
        """Update serving status for a team."""
        cursor = self.conn.cursor()
        cursor.execute(
            """UPDATE rotation_state 
               SET serving = %s, term_of_service_start = %s
               WHERE game_id = %s AND team_id = %s""",
            (serving, term_of_service_start, game_id, team_id)
        )
        self.conn.commit()
    
    def delete_rotation_state(self, game_id: int):
        """Delete rotation state for a game."""
        cursor = self.conn.cursor()
        cursor.execute(
            "DELETE FROM rotation_state WHERE game_id = %s",
            (game_id,)
        )
        self.conn.commit()
