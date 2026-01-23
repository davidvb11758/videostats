"""
Event logging queries.
"""
import psycopg2.extras
import json
from typing import List, Optional


class EventQueries:
    """Handles events table operations (event logging system)."""
    
    def __init__(self, conn):
        self.conn = conn
    
    def log_event(self, game_id: int, team_id: int, event_type: str, payload: dict) -> int:
        """
        Log an event.
        
        Args:
            game_id: The game ID
            team_id: The team ID
            event_type: Type of event (rotation, substitution, libero, etc.)
            payload: Event data as dictionary
            
        Returns:
            Event ID
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO events (game_id, team_id, event_type, payload)
               VALUES (%s, %s, %s, %s) RETURNING id""",
            (game_id, team_id, event_type, json.dumps(payload))
        )
        event_id = cursor.fetchone()[0]
        self.conn.commit()
        return event_id
    
    def get_events_for_game(self, game_id: int, event_type: Optional[str] = None,
                           exclude_initial_setup: bool = False) -> List[dict]:
        """
        Get events for a game.
        
        Args:
            game_id: The game ID
            event_type: Optional filter by event type
            exclude_initial_setup: If True, exclude initial_setup events
            
        Returns:
            List of event records
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        if event_type:
            cursor.execute(
                """SELECT * FROM events 
                   WHERE game_id = %s AND event_type = %s 
                   ORDER BY created_at""",
                (game_id, event_type)
            )
        elif exclude_initial_setup:
            cursor.execute(
                """SELECT * FROM events 
                   WHERE game_id = %s AND event_type != 'initial_setup'
                   ORDER BY created_at""",
                (game_id,)
            )
        else:
            cursor.execute(
                """SELECT * FROM events 
                   WHERE game_id = %s 
                   ORDER BY created_at""",
                (game_id,)
            )
        
        events = cursor.fetchall()
        # Parse JSON payloads
        for event in events:
            if 'payload' in event and isinstance(event['payload'], str):
                event['payload'] = json.loads(event['payload'])
        return events
    
    def get_initial_setup_event(self, game_id: int, team_id: int) -> Optional[dict]:
        """Get the initial_setup event for a team."""
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            """SELECT * FROM events 
               WHERE game_id = %s AND team_id = %s AND event_type = 'initial_setup'
               LIMIT 1""",
            (game_id, team_id)
        )
        event = cursor.fetchone()
        if event and 'payload' in event and isinstance(event['payload'], str):
            event['payload'] = json.loads(event['payload'])
        return event
    
    def update_event_payload(self, event_id: int, payload: dict):
        """Update an event's payload."""
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE events SET payload = %s WHERE id = %s",
            (json.dumps(payload), event_id)
        )
        self.conn.commit()
    
    def delete_event(self, event_id: int):
        """Delete an event."""
        cursor = self.conn.cursor()
        cursor.execute(
            "DELETE FROM events WHERE id = %s",
            (event_id,)
        )
        self.conn.commit()
    
    def delete_game_events(self, game_id: int, exclude_initial_setup: bool = False):
        """Delete all events for a game."""
        cursor = self.conn.cursor()
        if exclude_initial_setup:
            cursor.execute(
                "DELETE FROM events WHERE game_id = %s AND event_type != 'initial_setup'",
                (game_id,)
            )
        else:
            cursor.execute(
                "DELETE FROM events WHERE game_id = %s",
                (game_id,)
            )
        self.conn.commit()
    
    def count_events(self, game_id: int, event_type: Optional[str] = None) -> int:
        """Count events for a game, optionally filtered by type."""
        cursor = self.conn.cursor()
        if event_type:
            cursor.execute(
                "SELECT COUNT(*) FROM events WHERE game_id = %s AND event_type = %s",
                (game_id, event_type)
            )
        else:
            cursor.execute(
                "SELECT COUNT(*) FROM events WHERE game_id = %s",
                (game_id,)
            )
        return cursor.fetchone()[0]
