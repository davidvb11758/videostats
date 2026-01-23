"""
Database queries organized by domain.
All database queries should be defined here to centralize database access.
"""

from .teams import TeamQueries
from .players import PlayerQueries
from .games import GameQueries
from .rallies import RallyQueries
from .contacts import ContactQueries
from .lineup import LineupQueries
from .rotation import RotationQueries
from .substitutions import SubstitutionQueries
from .events import EventQueries
from .stats import StatsQueries
from .collections import CollectionQueries
from .game_players import GamePlayerQueries

__all__ = [
    'TeamQueries',
    'PlayerQueries',
    'GameQueries',
    'RallyQueries',
    'ContactQueries',
    'LineupQueries',
    'RotationQueries',
    'SubstitutionQueries',
    'EventQueries',
    'StatsQueries',
    'CollectionQueries',
    'GamePlayerQueries',
]
