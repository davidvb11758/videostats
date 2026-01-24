"""
Service for fetching and managing video clips.
"""

from typing import List, Optional, Dict
from models.clip_models import VideoClip
from dbstuff.database import VideoStatsDB


class ClipService:
    """Service for handling video clip operations."""
    
    def __init__(self, db: VideoStatsDB):
        self.db = db
    
    def get_filtered_clips(self, game_ids: List[int], filters: Dict) -> List[VideoClip]:
        """
        Get filtered clips from one or more games.
        
        Args:
            game_ids: List of game IDs to query
            filters: Filter dictionary from FilterService
            
        Returns:
            List of VideoClip objects
        """
        if not game_ids:
            return []
        
        if not self.db.conn:
            self.db.connect()
        
        cursor = self.db.conn.cursor()
        
        # Build query with game alias
        query = """
            SELECT 
                c.contact_id,
                c.timecode,
                p.player_number,
                p.name as player_name,
                c.contact_type,
                c.outcome,
                r.rally_number,
                c.sequence_number,
                c.rating,
                c.player_id,
                r.game_id,
                g.video_file_path,
                g.notes,
                t2.name as team_them_name
            FROM contacts c
            INNER JOIN rallies r ON c.rally_id = r.rally_id
            LEFT JOIN players p ON c.player_id = p.player_id
            INNER JOIN teams t ON c.team_id = t.team_id
            INNER JOIN games g ON r.game_id = g.game_id
            INNER JOIN teams t2 ON g.team_them_id = t2.team_id
            WHERE r.game_id IN ({})
              AND c.contact_type IN ({})
              AND c.outcome IN ({})
        """.format(
            ','.join(['%s'] * len(game_ids)),
            ','.join(['%s'] * len(filters['contact_types'])),
            ','.join(['%s'] * len(filters['outcomes']))
        )
        
        params = list(game_ids) + filters['contact_types'] + filters['outcomes']
        
        # Add team filter
        if len(filters['team_ids']) < 2 and len(filters['team_ids']) > 0:
            query += " AND c.team_id IN ({})".format(','.join(['%s'] * len(filters['team_ids'])))
            params.extend(filters['team_ids'])
        
        # Add rating filter if Receive is selected and ratings are selected
        if filters['use_rating_filter']:
            query += " AND (c.contact_type != 'receive' OR c.rating IN ({}))".format(
                ','.join(['%s'] * len(filters['ratings']))
            )
            params.extend(filters['ratings'])
        
        # Add player filter
        if not filters['all_players_selected'] and len(filters['player_ids']) > 0:
            query += " AND c.player_id IN ({})".format(','.join(['%s'] * len(filters['player_ids'])))
            params.extend(filters['player_ids'])
        
        query += " ORDER BY r.game_id, r.rally_number, c.sequence_number"
        
        cursor.execute(query, params)
        contacts = cursor.fetchall()
        
        # Get star ratings for all contacts
        star_ratings = self._get_star_ratings_batch(
            [(c['contact_id'], c['game_id']) for c in contacts]
        )
        
        # Convert to VideoClip objects
        clips = []
        for contact in contacts:
            # Extract game alias
            game_alias = self._extract_game_alias(contact['notes'], contact['team_them_name'])
            
            # Get star rating
            star_rating = star_ratings.get((contact['contact_id'], contact['game_id']))
            
            timecode_ms = contact['timecode'] if contact['timecode'] is not None else 0
            start_ms = max(0, timecode_ms - 3000)
            duration_ms = 6000
            
            clip = VideoClip(
                clip_id=None,
                contact_id=contact['contact_id'],
                game_id=contact['game_id'],
                game_alias=game_alias,
                video_file_path=contact['video_file_path'] or '',
                timecode_ms=timecode_ms,
                start_ms=start_ms,
                duration_ms=duration_ms,
                player_id=contact['player_id'],
                player_name=contact['player_name'],
                player_number=contact['player_number'],
                contact_type=contact['contact_type'],
                outcome=contact['outcome'],
                rating=contact['rating'],
                star_rating=star_rating,
                rally_number=contact['rally_number'],
                sequence_number=contact['sequence_number'],
                order_index=0
            )
            clips.append(clip)
        
        return clips
    
    def _extract_game_alias(self, notes: Optional[str], team_them_name: str) -> str:
        """Extract game alias from notes or use team name."""
        if notes:
            if notes.startswith("Opponent: "):
                return notes.replace("Opponent: ", "").strip()
            elif notes.strip():
                return notes.strip()
        return team_them_name
    
    def _get_star_ratings_batch(self, contact_game_pairs: List[tuple]) -> Dict[tuple, int]:
        """Get star ratings for multiple contacts in batch."""
        if not contact_game_pairs:
            return {}
        
        if not self.db.conn:
            self.db.connect()
        
        cursor = self.db.conn.cursor()
        
        # Build query with placeholders
        placeholders = ','.join(['(%s, %s)'] * len(contact_game_pairs))
        query = f"""
            SELECT contact_id, game_id, star_rating
            FROM clip_star_ratings
            WHERE (contact_id, game_id) IN ({placeholders})
        """
        
        params = []
        for contact_id, game_id in contact_game_pairs:
            params.extend([contact_id, game_id])
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        
        return {(r['contact_id'], r['game_id']): r['star_rating'] for r in results}
    
    def update_clip_star_rating(self, contact_id: int, game_id: int, star_rating: int) -> bool:
        """
        Update star rating for a clip.
        
        Args:
            contact_id: Contact ID
            game_id: Game ID
            star_rating: Star rating (1-5)
            
        Returns:
            True if successful, False otherwise
        """
        if not (1 <= star_rating <= 5):
            return False
        
        if not self.db.conn:
            self.db.connect()
        
        cursor = self.db.conn.cursor()
        
        try:
            # PostgreSQL syntax for INSERT ... ON CONFLICT
            cursor.execute("""
                INSERT INTO clip_star_ratings (contact_id, game_id, star_rating, updated_at)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (contact_id, game_id) 
                DO UPDATE SET star_rating = EXCLUDED.star_rating, updated_at = CURRENT_TIMESTAMP
            """, (contact_id, game_id, star_rating))
            self.db.conn.commit()
            return True
        except Exception as e:
            print(f"Error updating star rating: {e}")
            self.db.conn.rollback()
            return False
    
    def get_clip_star_rating(self, contact_id: int, game_id: int) -> Optional[int]:
        """
        Get star rating for a clip.
        
        Args:
            contact_id: Contact ID
            game_id: Game ID
            
        Returns:
            Star rating (1-5) or None if not set
        """
        if not self.db.conn:
            self.db.connect()
        
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT star_rating
            FROM clip_star_ratings
            WHERE contact_id = %s AND game_id = %s
        """, (contact_id, game_id))
        
        result = cursor.fetchone()
        return result['star_rating'] if result else None
    
    def get_games_list(self) -> List[Dict]:
        """Get list of all games with their aliases."""
        if not self.db.conn:
            self.db.connect()
        
        games = self.db.games.get_all_games_with_teams()
        
        result = []
        for game in games:
            # Extract game alias
            game_alias = game['team_them_name']
            if game['notes']:
                if game['notes'].startswith("Opponent: "):
                    game_alias = game['notes'].replace("Opponent: ", "").strip()
                elif game['notes'].strip():
                    game_alias = game['notes'].strip()
            
            result.append({
                'game_id': game['game_id'],
                'game_date': game['game_date'],
                'team_us_id': game['team_us_id'],
                'team_them_id': game['team_them_id'],
                'team_us_name': game['team_us_name'],
                'team_them_name': game['team_them_name'],
                'game_alias': game_alias,
                'notes': game['notes']
            })
        
        return result


