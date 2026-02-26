"""
Team-related database queries.
"""
import psycopg2.extras
from typing import Optional, List


class TeamQueries:
    """Handles all team-related database operations."""
    
    def __init__(self, conn):
        """
        Initialize with database connection.
        
        Args:
            conn: psycopg2 database connection
        """
        self.conn = conn
    
    def add_team(self, name: str) -> int:
        """
        Add a team and return team_id.
        
        Args:
            name: Team name
            
        Returns:
            team_id of the newly created team
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO teams (name) VALUES (%s) RETURNING team_id",
            (name,)
        )
        team_id = cursor.fetchone()[0]
        self.conn.commit()
        return team_id
    
    def get_all_teams(self) -> List[dict]:
        """
        Get all teams from the database.
        
        Returns:
            List of team records as dictionaries ordered by name
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT team_id, name FROM teams ORDER BY name")
        return cursor.fetchall()
    
    def get_team_by_id(self, team_id: int) -> Optional[dict]:
        """
        Get a team by ID.
        
        Args:
            team_id: The team ID
            
        Returns:
            Team record as dict or None if not found
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT * FROM teams WHERE team_id = %s", (team_id,))
        return cursor.fetchone()
    
    def get_team_name(self, team_id: int) -> Optional[str]:
        """
        Get team name by ID.
        
        Args:
            team_id: The team ID
            
        Returns:
            Team name or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM teams WHERE team_id = %s", (team_id,))
        result = cursor.fetchone()
        return result[0] if result else None
    
    def get_team_by_name(self, name: str) -> Optional[dict]:
        """
        Get team by name.
        
        Args:
            name: The team name
            
        Returns:
            Team record or None if not found
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT * FROM teams WHERE name = %s", (name,))
        return cursor.fetchone()
    
    def get_team_id_by_name(self, name: str) -> Optional[int]:
        """
        Get team_id by name.
        
        Args:
            name: The team name
            
        Returns:
            team_id or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT team_id FROM teams WHERE name = %s", (name,))
        result = cursor.fetchone()
        return result[0] if result else None