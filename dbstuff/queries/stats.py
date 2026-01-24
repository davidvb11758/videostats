"""
Player statistics queries.
"""
import psycopg2.extras
from typing import List, Optional


class StatsQueries:
    """Handles player_stats table operations."""
    
    def __init__(self, conn):
        self.conn = conn
    
    def get_player_stats(self, game_id: int, player_id: int) -> Optional[dict]:
        """Get stats for a specific player in a game."""
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            "SELECT * FROM player_stats WHERE game_id = %s AND player_id = %s",
            (game_id, player_id)
        )
        return cursor.fetchone()
    
    def get_all_player_stats_for_game(self, game_id: int) -> List[dict]:
        """Get stats for all players in a game."""
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            "SELECT * FROM player_stats WHERE game_id = %s ORDER BY player_id",
            (game_id,)
        )
        return cursor.fetchall()
    
    def get_team_player_stats(self, game_id: int, team_id: int) -> List[dict]:
        """Get stats for all players of a team in a game."""
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            """SELECT ps.* FROM player_stats ps
               INNER JOIN players p ON ps.player_id = p.player_id
               WHERE ps.game_id = %s AND p.team_id = %s
               ORDER BY ps.player_id""",
            (game_id, team_id)
        )
        return cursor.fetchall()
    
    def upsert_player_stats(self, game_id: int, player_id: int, stats: dict):
        """
        Insert or update player stats.
        
        Args:
            game_id: The game ID
            player_id: The player ID
            stats: Dictionary of stat values
        """
        cursor = self.conn.cursor()
        
        # Build the column names and values
        columns = ['game_id', 'player_id'] + list(stats.keys())
        placeholders = ['%s'] * len(columns)
        values = [game_id, player_id] + list(stats.values())
        
        # Build UPDATE clause for ON CONFLICT
        update_cols = [f"{col} = EXCLUDED.{col}" for col in stats.keys()]
        
        query = f"""
            INSERT INTO player_stats ({', '.join(columns)})
            VALUES ({', '.join(placeholders)})
            ON CONFLICT (game_id, player_id)
            DO UPDATE SET {', '.join(update_cols)}, updated_at = CURRENT_TIMESTAMP
        """
        
        cursor.execute(query, tuple(values))
        self.conn.commit()
    
    def delete_player_stats(self, game_id: int, player_id: int):
        """Delete stats for a specific player in a game."""
        cursor = self.conn.cursor()
        cursor.execute(
            "DELETE FROM player_stats WHERE game_id = %s AND player_id = %s",
            (game_id, player_id)
        )
        self.conn.commit()
    
    def delete_game_stats(self, game_id: int):
        """Delete all stats for a game."""
        cursor = self.conn.cursor()
        cursor.execute(
            "DELETE FROM player_stats WHERE game_id = %s",
            (game_id,)
        )
        self.conn.commit()
    
    def count_player_stats(self, game_id: int) -> int:
        """Count player stat records for a game."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM player_stats WHERE game_id = %s",
            (game_id,)
        )
        return cursor.fetchone()[0]
    
    def get_all_games_with_rallies(self) -> List[int]:
        """Get list of all game IDs that have rallies."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT game_id FROM rallies ORDER BY game_id")
        return [row[0] for row in cursor.fetchall()]
    
    def count_player_stats(self, game_id: int) -> int:
        """
        Count player stat records for a game.
        
        Args:
            game_id: The game ID
            
        Returns:
            Number of player stat records
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM player_stats WHERE game_id = %s", (game_id,))
        return cursor.fetchone()[0] or 0