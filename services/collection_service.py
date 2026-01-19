"""
Service for managing clip collections.
"""

from typing import List, Optional, Tuple
from datetime import datetime
from models.clip_models import ClipCollection, VideoClip
from database import VideoStatsDB


class CollectionService:
    """Service for managing clip collections."""
    
    def __init__(self, db: VideoStatsDB):
        self.db = db
    
    def create_collection(self, name: str, description: Optional[str] = None) -> ClipCollection:
        """
        Create a new collection.
        
        Args:
            name: Collection name
            description: Optional description
            
        Returns:
            ClipCollection object
        """
        return ClipCollection(
            collection_id=None,
            name=name,
            description=description,
            created_at=datetime.now(),
            clip_ids=[]
        )
    
    def save_collection(self, collection: ClipCollection, clips: List[VideoClip]) -> int:
        """
        Save a collection with its clips to the database.
        
        Args:
            collection: ClipCollection object
            clips: List of VideoClip objects in order
            
        Returns:
            Collection ID
        """
        if not self.db.conn:
            self.db.connect()
        
        cursor = self.db.conn.cursor()
        
        try:
            # Insert or update collection
            if collection.collection_id:
                cursor.execute("""
                    UPDATE clip_collections
                    SET name = %s, description = %s
                    WHERE collection_id = %s
                """, (collection.name, collection.description, collection.collection_id))
                collection_id = collection.collection_id
                
                # Delete existing clips
                cursor.execute("""
                    DELETE FROM collection_clips
                    WHERE collection_id = %s
                """, (collection_id,))
            else:
                cursor.execute("""
                    INSERT INTO clip_collections (name, description, created_at)
                    VALUES (%s, %s, %s)
                """, (collection.name, collection.description, collection.created_at))
                collection_id = cursor.lastrowid
            
            # Check if is_selected column exists
            cursor.execute("PRAGMA table_info(collection_clips)")
            columns = [row[1] for row in cursor.fetchall()]
            has_is_selected = 'is_selected' in columns
            
            # Insert clips with order and selection state
            for order_index, clip in enumerate(clips):
                # Get is_selected from clip dict if available (not part of VideoClip model)
                is_selected = getattr(clip, 'is_selected', True) if hasattr(clip, 'is_selected') else True
                # If clip is a dict (from API), check for is_selected
                if isinstance(clip, dict):
                    is_selected = clip.get('is_selected', True)  # Default to True (selected)
                
                if has_is_selected:
                    cursor.execute("""
                        INSERT INTO collection_clips (collection_id, contact_id, game_id, order_index, is_selected)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (collection_id, clip.contact_id, clip.game_id, order_index, 1 if is_selected else 0))
                else:
                    # Fallback if column doesn't exist yet
                    cursor.execute("""
                        INSERT INTO collection_clips (collection_id, contact_id, game_id, order_index)
                        VALUES (%s, %s, %s, %s)
                    """, (collection_id, clip.contact_id, clip.game_id, order_index))
            
            self.db.conn.commit()
            return collection_id
        except Exception as e:
            print(f"Error saving collection: {e}")
            self.db.conn.rollback()
            raise
    
    def load_collection(self, collection_id: int) -> Tuple[ClipCollection, List[VideoClip]]:
        """
        Load a collection and its clips from the database.
        
        Args:
            collection_id: Collection ID
            
        Returns:
            Tuple of (ClipCollection, List[VideoClip])
        """
        if not self.db.conn:
            self.db.connect()
        
        cursor = self.db.conn.cursor()
        
        # Get collection
        cursor.execute("""
            SELECT collection_id, name, description, created_at
            FROM clip_collections
            WHERE collection_id = %s
        """, (collection_id,))
        result = cursor.fetchone()
        
        if not result:
            raise ValueError(f"Collection {collection_id} not found")
        
        collection = ClipCollection(
            collection_id=result['collection_id'],
            name=result['name'],
            description=result['description'],
            created_at=datetime.fromisoformat(result['created_at'].replace('Z', '+00:00')) if isinstance(result['created_at'], str) else result['created_at'],
            clip_ids=[]
        )
        
        # Check if is_selected column exists
        has_is_selected = False
        try:
            cursor.execute("PRAGMA table_info(collection_clips)")
            columns = [row[1] for row in cursor.fetchall()]
            has_is_selected = 'is_selected' in columns
        except Exception as e:
            print(f"Error checking for is_selected column: {e}")
            has_is_selected = False
        
        # Get clips in order with selection state
        try:
            if has_is_selected:
                cursor.execute("""
                    SELECT cc.contact_id, cc.game_id, cc.order_index, COALESCE(cc.is_selected, 1) as is_selected,
                           c.timecode, c.contact_type, c.outcome, c.rating,
                           p.player_id, p.player_number, p.name as player_name,
                           r.rally_number, c.sequence_number,
                           g.video_file_path, g.notes, t2.name as team_them_name
                    FROM collection_clips cc
                    INNER JOIN contacts c ON cc.contact_id = c.contact_id
                    INNER JOIN rallies r ON c.rally_id = r.rally_id
                    LEFT JOIN players p ON c.player_id = p.player_id
                    INNER JOIN games g ON r.game_id = g.game_id
                    INNER JOIN teams t2 ON g.team_them_id = t2.team_id
                    WHERE cc.collection_id = %s
                    ORDER BY cc.order_index
                """, (collection_id,))
            else:
                # Fallback if is_selected column doesn't exist yet
                cursor.execute("""
                    SELECT cc.contact_id, cc.game_id, cc.order_index,
                           c.timecode, c.contact_type, c.outcome, c.rating,
                           p.player_id, p.player_number, p.name as player_name,
                           r.rally_number, c.sequence_number,
                           g.video_file_path, g.notes, t2.name as team_them_name
                    FROM collection_clips cc
                    INNER JOIN contacts c ON cc.contact_id = c.contact_id
                    INNER JOIN rallies r ON c.rally_id = r.rally_id
                    LEFT JOIN players p ON c.player_id = p.player_id
                    INNER JOIN games g ON r.game_id = g.game_id
                    INNER JOIN teams t2 ON g.team_them_id = t2.team_id
                    WHERE cc.collection_id = %s
                    ORDER BY cc.order_index
                """, (collection_id,))
            
            clip_rows = cursor.fetchall()
        except Exception as e:
            print(f"Error executing query to load collection clips: {e}")
            import traceback
            traceback.print_exc()
            raise
        
        # Get star ratings
        from services.clip_service import ClipService
        clip_service = ClipService(self.db)
        star_ratings = clip_service._get_star_ratings_batch(
            [(row['contact_id'], row['game_id']) for row in clip_rows]
        )
        
        # Build VideoClip objects
        clips = []
        for row in clip_rows:
            game_alias = clip_service._extract_game_alias(row['notes'], row['team_them_name'])
            star_rating = star_ratings.get((row['contact_id'], row['game_id']))
            
            timecode_ms = row['timecode'] if row['timecode'] is not None else 0
            start_ms = max(0, timecode_ms - 3000)
            duration_ms = 6000
            
            clip = VideoClip(
                clip_id=None,
                contact_id=row['contact_id'],
                game_id=row['game_id'],
                game_alias=game_alias,
                video_file_path=row['video_file_path'] or '',
                timecode_ms=timecode_ms,
                start_ms=start_ms,
                duration_ms=duration_ms,
                player_id=row['player_id'],
                player_name=row['player_name'],
                player_number=row['player_number'],
                contact_type=row['contact_type'],
                outcome=row['outcome'],
                rating=row['rating'],
                star_rating=star_rating,
                rally_number=row['rally_number'],
                sequence_number=row['sequence_number'],
                order_index=row['order_index']
            )
            # Store is_selected as an attribute (not part of VideoClip model, but preserved in dict)
            # Default to True if column doesn't exist (all loaded clips should be selected)
            try:
                if has_is_selected and 'is_selected' in row.keys():
                    clip.is_selected = bool(row.get('is_selected', 1))  # Default to 1 (selected) for loaded clips
                else:
                    clip.is_selected = True  # All loaded clips are selected if column doesn't exist
            except (KeyError, AttributeError):
                clip.is_selected = True  # Default to selected if there's any error
            clips.append(clip)
        
        # Update collection clip_ids
        collection.clip_ids = [(c.contact_id, c.game_id) for c in clips]
        
        return collection, clips
    
    def list_collections(self) -> List[ClipCollection]:
        """
        List all collections.
        
        Returns:
            List of ClipCollection objects
        """
        if not self.db.conn:
            self.db.connect()
        
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT collection_id, name, description, created_at
            FROM clip_collections
            ORDER BY created_at DESC
        """)
        
        results = cursor.fetchall()
        collections = []
        for row in results:
            created_at = row['created_at']
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                except:
                    created_at = datetime.now()
            elif not isinstance(created_at, datetime):
                created_at = datetime.now()
            
            collection = ClipCollection(
                collection_id=row['collection_id'],
                name=row['name'],
                description=row['description'],
                created_at=created_at,
                clip_ids=[]
            )
            collections.append(collection)
        
        return collections
    
    def delete_collection(self, collection_id: int) -> bool:
        """
        Delete a collection.
        
        Args:
            collection_id: Collection ID
            
        Returns:
            True if successful, False otherwise
        """
        if not self.db.conn:
            self.db.connect()
        
        cursor = self.db.conn.cursor()
        
        try:
            # Clips will be deleted automatically due to CASCADE
            cursor.execute("""
                DELETE FROM clip_collections
                WHERE collection_id = %s
            """, (collection_id,))
            self.db.conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error deleting collection: {e}")
            self.db.conn.rollback()
            return False


