"""
Clip collection queries.
"""
import psycopg2.extras
from typing import List, Optional


class CollectionQueries:
    """Handles clip_collections and collection_clips tables."""
    
    def __init__(self, conn):
        self.conn = conn
    
    # Collections
    def create_collection(self, name: str, description: Optional[str] = None) -> int:
        """Create a new collection."""
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO clip_collections (name, description)
               VALUES (%s, %s) RETURNING collection_id""",
            (name, description)
        )
        collection_id = cursor.fetchone()[0]
        self.conn.commit()
        return collection_id
    
    def get_collection(self, collection_id: int) -> Optional[dict]:
        """Get a collection by ID."""
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            "SELECT * FROM clip_collections WHERE collection_id = %s",
            (collection_id,)
        )
        return cursor.fetchone()
    
    def get_all_collections(self) -> List[dict]:
        """Get all collections."""
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            "SELECT * FROM clip_collections ORDER BY created_at DESC"
        )
        return cursor.fetchall()
    
    def update_collection(self, collection_id: int, name: Optional[str] = None,
                         description: Optional[str] = None):
        """Update collection details."""
        updates = []
        params = []
        if name is not None:
            updates.append("name = %s")
            params.append(name)
        if description is not None:
            updates.append("description = %s")
            params.append(description)
        
        if updates:
            params.append(collection_id)
            cursor = self.conn.cursor()
            cursor.execute(
                f"UPDATE clip_collections SET {', '.join(updates)} WHERE collection_id = %s",
                tuple(params)
            )
            self.conn.commit()
    
    def delete_collection(self, collection_id: int):
        """Delete a collection (cascades to collection_clips)."""
        cursor = self.conn.cursor()
        cursor.execute(
            "DELETE FROM clip_collections WHERE collection_id = %s",
            (collection_id,)
        )
        self.conn.commit()
    
    # Collection Clips
    def add_clip_to_collection(self, collection_id: int, contact_id: int, game_id: int,
                              order_index: int, is_selected: int = 0):
        """Add a clip to a collection."""
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO collection_clips 
               (collection_id, contact_id, game_id, order_index, is_selected)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (collection_id, contact_id, game_id)
               DO UPDATE SET order_index = EXCLUDED.order_index,
                            is_selected = EXCLUDED.is_selected""",
            (collection_id, contact_id, game_id, order_index, is_selected)
        )
        self.conn.commit()
    
    def remove_clip_from_collection(self, collection_id: int, contact_id: int, game_id: int):
        """Remove a clip from a collection."""
        cursor = self.conn.cursor()
        cursor.execute(
            """DELETE FROM collection_clips 
               WHERE collection_id = %s AND contact_id = %s AND game_id = %s""",
            (collection_id, contact_id, game_id)
        )
        self.conn.commit()
    
    def get_collection_clips(self, collection_id: int) -> List[dict]:
        """Get all clips in a collection."""
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            """SELECT * FROM collection_clips 
               WHERE collection_id = %s 
               ORDER BY order_index""",
            (collection_id,)
        )
        return cursor.fetchall()
    
    def update_clip_order(self, collection_id: int, contact_id: int, game_id: int,
                         order_index: int):
        """Update the order of a clip in a collection."""
        cursor = self.conn.cursor()
        cursor.execute(
            """UPDATE collection_clips SET order_index = %s
               WHERE collection_id = %s AND contact_id = %s AND game_id = %s""",
            (order_index, collection_id, contact_id, game_id)
        )
        self.conn.commit()
    
    def update_clip_selection(self, collection_id: int, contact_id: int, game_id: int,
                             is_selected: int):
        """Update the selection status of a clip."""
        cursor = self.conn.cursor()
        cursor.execute(
            """UPDATE collection_clips SET is_selected = %s
               WHERE collection_id = %s AND contact_id = %s AND game_id = %s""",
            (is_selected, collection_id, contact_id, game_id)
        )
        self.conn.commit()
    
    # Star Ratings
    def set_clip_star_rating(self, contact_id: int, game_id: int, star_rating: int):
        """Set or update star rating for a clip."""
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO clip_star_ratings (contact_id, game_id, star_rating)
               VALUES (%s, %s, %s)
               ON CONFLICT (contact_id, game_id)
               DO UPDATE SET star_rating = EXCLUDED.star_rating,
                            updated_at = CURRENT_TIMESTAMP""",
            (contact_id, game_id, star_rating)
        )
        self.conn.commit()
    
    def get_clip_star_rating(self, contact_id: int, game_id: int) -> Optional[int]:
        """Get star rating for a clip."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT star_rating FROM clip_star_ratings WHERE contact_id = %s AND game_id = %s",
            (contact_id, game_id)
        )
        result = cursor.fetchone()
        return result[0] if result else None
    
    def delete_clip_star_rating(self, contact_id: int, game_id: int):
        """Delete star rating for a clip."""
        cursor = self.conn.cursor()
        cursor.execute(
            "DELETE FROM clip_star_ratings WHERE contact_id = %s AND game_id = %s",
            (contact_id, game_id)
        )
        self.conn.commit()
