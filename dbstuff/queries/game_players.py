"""
Game-player relationship queries (game roster).
"""
import psycopg2.extras
from typing import Optional, List


class GamePlayerQueries:
    """Handles game_players table operations (which players are in which games)."""
    
    def __init__(self, conn):
        """
        Initialize with database connection.
        
        Args:
            conn: psycopg2 database connection
        """
        self.conn = conn
    
    def add_player_to_game(self, game_id: int, team_id: int, player_id: int, 
                          game_role_code: str = None) -> int:
        """
        Add a player to a specific game's roster and return game_player_id.
        
        Args:
            game_id: The game ID
            team_id: The team ID
            player_id: The player ID
            game_role_code: Optional role code for this player in this game
            
        Returns:
            game_player_id
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """INSERT INTO game_players (game_id, team_id, player_id, game_role_code) 
                   VALUES (%s, %s, %s, %s) RETURNING game_player_id""",
                (game_id, team_id, player_id, game_role_code)
            )
            game_player_id = cursor.fetchone()[0]
            self.conn.commit()
            return game_player_id
        except psycopg2.IntegrityError:
            self.conn.rollback()
            # Player already in game roster - update game_role_code if provided
            if game_role_code is not None:
                cursor.execute(
                    """UPDATE game_players SET game_role_code = %s 
                       WHERE game_id = %s AND team_id = %s AND player_id = %s""",
                    (game_role_code, game_id, team_id, player_id)
                )
                self.conn.commit()
            cursor.execute(
                """SELECT game_player_id FROM game_players 
                   WHERE game_id = %s AND team_id = %s AND player_id = %s""",
                (game_id, team_id, player_id)
            )
            result = cursor.fetchone()
            return result[0] if result else None
    
    def remove_player_from_game(self, game_id: int, team_id: int, player_id: int):
        """
        Remove a player from a game's roster.
        
        Args:
            game_id: The game ID
            team_id: The team ID
            player_id: The player ID
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "DELETE FROM game_players WHERE game_id = %s AND team_id = %s AND player_id = %s",
            (game_id, team_id, player_id)
        )
        self.conn.commit()
    
    def get_game_players(self, game_id: int, team_id: int) -> List[dict]:
        """
        Get all players for a specific team in a specific game.
        
        Args:
            game_id: The game ID
            team_id: The team ID
            
        Returns:
            List of player records
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT p.player_id, p.player_number, p.name, p.team_id
            FROM players p
            INNER JOIN game_players gp ON p.player_id = gp.player_id
            WHERE gp.game_id = %s AND gp.team_id = %s
            ORDER BY 
                CASE 
                    WHEN p.player_number ~ '^[0-9]+$' 
                    THEN CAST(p.player_number AS INTEGER)
                    ELSE 999999
                END,
                p.player_number
        """, (game_id, team_id))
        return cursor.fetchall()
    
    def get_player_by_number_for_game(self, game_id: int, team_id: int, 
                                     player_number: str) -> Optional[dict]:
        """
        Get a player by number for a specific game and team.
        
        Args:
            game_id: The game ID
            team_id: The team ID
            player_number: Player number
            
        Returns:
            Player record or None if not found
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT p.*
            FROM players p
            INNER JOIN game_players gp ON p.player_id = gp.player_id
            WHERE gp.game_id = %s AND gp.team_id = %s AND p.player_number = %s
        """, (game_id, team_id, str(player_number).strip()))
        return cursor.fetchone()
    
    def count_game_players(self, game_id: int) -> int:
        """
        Count total players in a game across all teams.
        
        Args:
            game_id: The game ID
            
        Returns:
            Count of players
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM game_players WHERE game_id = %s",
            (game_id,)
        )
        return cursor.fetchone()[0]
    
    def is_player_in_game(self, game_id: int, team_id: int, player_id: int) -> bool:
        """
        Check if a player is in a game roster.
        
        Args:
            game_id: The game ID
            team_id: The team ID
            player_id: The player ID
            
        Returns:
            True if player is in game, False otherwise
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT EXISTS(SELECT 1 FROM game_players 
               WHERE game_id = %s AND team_id = %s AND player_id = %s)""",
            (game_id, team_id, player_id)
        )
        return cursor.fetchone()[0]
    
    def get_player_game_role(self, game_id: int, team_id: int, player_id: int) -> Optional[str]:
        """
        Get the game_role_code for a player in a specific game.
        
        Args:
            game_id: The game ID
            team_id: The team ID
            player_id: The player ID
            
        Returns:
            game_role_code or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT game_role_code FROM game_players 
               WHERE game_id = %s AND team_id = %s AND player_id = %s""",
            (game_id, team_id, player_id)
        )
        result = cursor.fetchone()
        return result[0] if result and result[0] else None
    
    def get_all_game_players(self, game_id: int) -> List[dict]:
        """
        Get all players in a game (all teams).
        
        Args:
            game_id: The game ID
            
        Returns:
            List of game_player records
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            """SELECT team_id, player_id, game_role_code 
               FROM game_players 
               WHERE game_id = %s 
               ORDER BY team_id, player_id""",
            (game_id,)
        )
        return cursor.fetchall()
    
    def count_game_players(self, game_id: int) -> int:
        """
        Count players in a game.
        
        Args:
            game_id: The game ID
            
        Returns:
            Number of players
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM game_players WHERE game_id = %s", (game_id,))
        return cursor.fetchone()[0] or 0