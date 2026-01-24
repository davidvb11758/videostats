"""
PostgreSQL database structure for VideoStats volleyball tracking application.
Tracks player ball contacts from serve through rally end.

Connection Configuration:
    For Supabase pooled connections, use the connection pooler port (6543):
    postgresql://postgres.[project-ref]:[password]@aws-0-us-west-1.pooler.supabase.com:6543/postgres
    
    Set via environment variable:
        SUPABASE_URL=postgresql://...
    
    Or pass directly:
        db = VideoStatsDB(connection_string="postgresql://...")
    
    The pooler provides connection pooling automatically, no additional configuration needed.
    See dbstuff/SUPABASE_SETUP.md for complete setup instructions.

Usage:
    Access all queries through domain-specific query classes:
        db.teams.add_team(name)
        db.players.add_player(team_id, number, name)
        db.games.start_game(team_us_id, team_them_id)
        db.rallies.start_rally(game_id, rally_number, serving_team_id)
        db.contacts.add_contact(rally_id, sequence_number, contact_type, team_id, player_id)
        db.lineup.set_lineup_position(game_id, team_id, position_number, player_id, role_code)
        db.rotation.set_rotation_state(team_id, game_id, rotation_order, rotation_index, serving)
        db.substitutions.add_substitution(team_id, out_player_id, in_player_id, game_id)
        db.events.log_event(game_id, team_id, event_type, payload)
        db.stats.upsert_player_stats(game_id, player_id, stats_dict)
        db.collections.create_collection(name, description)
        db.game_players.add_player_to_game(game_id, team_id, player_id, game_role_code)
    
    See dbstuff/QUERY_REFACTORING.md for complete API documentation.
"""

import psycopg2
import psycopg2.extras
import re
from pathlib import Path
from datetime import datetime
from typing import Optional
from logging_config import get_logger
import os

# Import query classes
from dbstuff.queries import (
    TeamQueries, PlayerQueries, GameQueries, RallyQueries,
    ContactQueries, LineupQueries, RotationQueries, 
    SubstitutionQueries, EventQueries, StatsQueries,
    CollectionQueries, GamePlayerQueries
)

logger = get_logger('database')


class VideoStatsDB:
    """Database manager for VideoStats volleyball tracking."""
    
    def __init__(self, connection_string: str = None):
        """Initialize the database connection.
        """
        # Check for connection string (priority order: parameter > env var)
        if connection_string is None:
            connection_string = os.getenv('SUPABASE_URL')
        
        if connection_string:
            # Use connection string (for Supabase or other hosted PostgreSQL)
            self.db_config = connection_string
        else:
            raise ValueError("No connection string provided")
        
        self.conn = None
        
        # Query class instances (initialized lazily)
        self._teams = None
        self._players = None
        self._games = None
        self._rallies = None
        self._contacts = None
        self._lineup = None
        self._rotation = None
        self._substitutions = None
        self._events = None
        self._stats = None
        self._collections = None
        self._game_players = None
        
    def connect(self):
        """Connect to the database."""
        # Handle both connection string and config dict
        if isinstance(self.db_config, str):
            # Connection string (DSN) format
            self.conn = psycopg2.connect(self.db_config)
        else:
            # Dictionary config format
            self.conn = psycopg2.connect(**self.db_config)
        
        self.conn.set_session(autocommit=False)
        # Reset query instances when connection changes
        self._reset_query_instances()
        return self.conn
    
    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            self._reset_query_instances()
    
    def _reset_query_instances(self):
        """Reset all query class instances."""
        self._teams = None
        self._players = None
        self._games = None
        self._rallies = None
        self._contacts = None
        self._lineup = None
        self._rotation = None
        self._substitutions = None
        self._events = None
        self._stats = None
        self._collections = None
        self._game_players = None
    
    # Properties for query classes (lazy initialization)
    @property
    def teams(self) -> TeamQueries:
        """Get TeamQueries instance."""
        if self._teams is None:
            self._teams = TeamQueries(self.conn)
        return self._teams
    
    @property
    def players(self) -> PlayerQueries:
        """Get PlayerQueries instance."""
        if self._players is None:
            self._players = PlayerQueries(self.conn)
        return self._players
    
    @property
    def games(self) -> GameQueries:
        """Get GameQueries instance."""
        if self._games is None:
            self._games = GameQueries(self.conn)
        return self._games
    
    @property
    def rallies(self) -> RallyQueries:
        """Get RallyQueries instance."""
        if self._rallies is None:
            self._rallies = RallyQueries(self.conn)
        return self._rallies
    
    @property
    def contacts(self) -> ContactQueries:
        """Get ContactQueries instance."""
        if self._contacts is None:
            self._contacts = ContactQueries(self.conn)
        return self._contacts
    
    @property
    def lineup(self) -> LineupQueries:
        """Get LineupQueries instance."""
        if self._lineup is None:
            self._lineup = LineupQueries(self.conn)
        return self._lineup
    
    @property
    def rotation(self) -> RotationQueries:
        """Get RotationQueries instance."""
        if self._rotation is None:
            self._rotation = RotationQueries(self.conn)
        return self._rotation
    
    @property
    def substitutions(self) -> SubstitutionQueries:
        """Get SubstitutionQueries instance."""
        if self._substitutions is None:
            self._substitutions = SubstitutionQueries(self.conn)
        return self._substitutions
    
    @property
    def events(self) -> EventQueries:
        """Get EventQueries instance."""
        if self._events is None:
            self._events = EventQueries(self.conn)
        return self._events
    
    @property
    def stats(self) -> StatsQueries:
        """Get StatsQueries instance."""
        if self._stats is None:
            self._stats = StatsQueries(self.conn)
        return self._stats
    
    @property
    def collections(self) -> CollectionQueries:
        """Get CollectionQueries instance."""
        if self._collections is None:
            self._collections = CollectionQueries(self.conn)
        return self._collections
    
    @property
    def game_players(self) -> GamePlayerQueries:
        """Get GamePlayerQueries instance."""
        if self._game_players is None:
            self._game_players = GamePlayerQueries(self.conn)
        return self._game_players
    
    
    def initialize_database(self):
        """Initialize the database with tables.
        
        Note: For PostgreSQL, schema should be created using migration files.
        This method is kept for compatibility but doesn't create tables.
        
        For Supabase setup, see: dbstuff/SUPABASE_SETUP.md
        """
        logger.info("Database initialization called. Use migration files to create PostgreSQL schema.")

