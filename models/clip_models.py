"""
Data models for video clips and collections.
"""

from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime


@dataclass
class VideoClip:
    """Represents a single video clip from a contact."""
    clip_id: Optional[int]  # For saved clips
    contact_id: int
    game_id: int
    game_alias: str  # Game alias/name for display
    video_file_path: str
    timecode_ms: int
    start_ms: int  # timecode - 3000
    duration_ms: int  # 6000
    player_id: Optional[int]
    player_name: Optional[str]
    player_number: Optional[int]
    contact_type: str
    outcome: str
    rating: Optional[int]  # Contact rating (0-3)
    star_rating: Optional[int]  # User-assigned star rating (1-5)
    rally_number: int
    sequence_number: int
    order_index: int  # For collection ordering
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'clip_id': self.clip_id,
            'contact_id': self.contact_id,
            'game_id': self.game_id,
            'game_alias': self.game_alias,
            'video_file_path': self.video_file_path,
            'timecode_ms': self.timecode_ms,
            'start_ms': self.start_ms,
            'duration_ms': self.duration_ms,
            'player_id': self.player_id,
            'player_name': self.player_name,
            'player_number': self.player_number,
            'contact_type': self.contact_type,
            'outcome': self.outcome,
            'rating': self.rating,
            'star_rating': self.star_rating,
            'rally_number': self.rally_number,
            'sequence_number': self.sequence_number,
            'order_index': self.order_index
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'VideoClip':
        """Create VideoClip from dictionary."""
        return cls(
            clip_id=data.get('clip_id'),
            contact_id=data['contact_id'],
            game_id=data['game_id'],
            game_alias=data.get('game_alias', ''),
            video_file_path=data['video_file_path'],
            timecode_ms=data['timecode_ms'],
            start_ms=data.get('start_ms', max(0, data['timecode_ms'] - 3000)),
            duration_ms=data.get('duration_ms', 6000),
            player_id=data.get('player_id'),
            player_name=data.get('player_name'),
            player_number=data.get('player_number'),
            contact_type=data['contact_type'],
            outcome=data['outcome'],
            rating=data.get('rating'),
            star_rating=data.get('star_rating'),
            rally_number=data['rally_number'],
            sequence_number=data['sequence_number'],
            order_index=data.get('order_index', 0)
        )


@dataclass
class ClipCollection:
    """Represents a collection of video clips."""
    collection_id: Optional[int]
    name: str
    description: Optional[str]
    created_at: datetime
    clip_ids: List[tuple]  # List of (contact_id, game_id) tuples for ordering
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'collection_id': self.collection_id,
            'name': self.name,
            'description': self.description,
            'created_at': self.created_at.isoformat() if isinstance(self.created_at, datetime) else str(self.created_at),
            'clip_ids': self.clip_ids
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ClipCollection':
        """Create ClipCollection from dictionary."""
        created_at = data.get('created_at')
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            except:
                created_at = datetime.now()
        elif not isinstance(created_at, datetime):
            created_at = datetime.now()
        
        return cls(
            collection_id=data.get('collection_id'),
            name=data['name'],
            description=data.get('description'),
            created_at=created_at,
            clip_ids=data.get('clip_ids', [])
        )
