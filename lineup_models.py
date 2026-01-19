"""
Data models for volleyball lineup management.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict
from datetime import datetime, timezone


@dataclass
class Position:
    """Immutable position definition."""
    number: int
    name: str
    abbrev: str
    row: str  # 'Front'|'Back'
    side: str  # 'Left'|'Middle'|'Right'
    x: int
    y: int


@dataclass
class Player:
    """Player model."""
    id: int
    name: str
    jersey: Optional[int]
    role_code: str  # S, RS/RH, MH, OH, Lib, DS
    is_active: bool = False
    team_id: Optional[int] = None
    player_number: Optional[str] = None  # Keep for backward compatibility


@dataclass
class LineupEntry:
    """Active lineup entry - player in a position."""
    position: int
    player_id: int
    role_code: str
    is_server: bool = False
    placed_at: datetime = None
    
    def __post_init__(self):
        if self.placed_at is None:
            self.placed_at = datetime.now(timezone.utc)


@dataclass
class RotationState:
    """Current rotation state for a team."""
    team_id: int
    rotation_order: List[int]  # e.g. [1,6,5,4,3,2]
    rotation_index: int = 0  # index into rotation_order (0..5)
    serving: bool = False
    term_of_service_start: Optional[datetime] = None


@dataclass
class Substitution:
    """Substitution record."""
    id: Optional[int] = None
    team_id: Optional[int] = None
    out_player_id: int = 0
    in_player_id: int = 0
    out_position: Optional[int] = None
    in_position: Optional[int] = None
    created_at: Optional[datetime] = None


@dataclass
class LiberoAction:
    """Libero action record."""
    id: Optional[int] = None
    team_id: Optional[int] = None
    libero_id: int = 0
    replaced_player_id: int = 0
    replaced_position: int = 0
    action: str = ''  # 'enter'|'exit'
    created_at: Optional[datetime] = None


# Constants
FRONT_ROW_POSITIONS = {2, 3, 4}
BACK_ROW_POSITIONS = {5, 6, 1}
ALL_POSITIONS = {1, 2, 3, 4, 5, 6}

# Rotation mapping: position -> next position in rotation
ROTATION_MAP = {1: 6, 6: 5, 5: 4, 4: 3, 3: 2, 2: 1}

# Default rotation order
DEFAULT_ROTATION_ORDER = [1, 6, 5, 4, 3, 2]

# Valid role codes
VALID_ROLE_CODES = {'S', 'RS', 'RH', 'MH', 'OH', 'Lib', 'DS'}

# Role aliases (RS and RH are synonyms)
ROLE_ALIASES = {
    'RS': 'RS',
    'RH': 'RS'  # RH maps to RS
}


