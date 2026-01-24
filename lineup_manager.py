"""
Core lineup management functions for volleyball tracking.
Handles lineup initialization, rotations, substitutions, libero actions, and role adjustments.
"""

import json
import psycopg2.extras
from datetime import datetime, timezone
from typing import List, Tuple, Optional, Dict
from dbstuff.database import VideoStatsDB
from lineup_models import (
    Position, Player, LineupEntry, RotationState, Substitution, LiberoAction,
    FRONT_ROW_POSITIONS, BACK_ROW_POSITIONS, ALL_POSITIONS,
    ROTATION_MAP, DEFAULT_ROTATION_ORDER, VALID_ROLE_CODES, ROLE_ALIASES
)


class LineupManager:
    """Manages lineup, rotations, substitutions, and libero actions."""
    
    def __init__(self, db: VideoStatsDB):
        self.db = db
        if not db.conn:
            db.connect()
    
    def _log_event(self, team_id: int, event_type: str, payload: dict, game_id: Optional[int] = None):
        """Log an event to the events table.
        
        Args:
            team_id: Team ID
            event_type: Type of event
            payload: Event payload dictionary
            game_id: Game ID (required)
        """
        if game_id is None:
            raise ValueError("game_id is required for logging events")
        self.db.events.log_event(game_id, team_id, event_type, payload)
    
    def _get_active_lineup(self, game_id: int, team_id: int) -> Dict[int, LineupEntry]:
        """Get current active lineup as dict position -> LineupEntry."""
        rows = self.db.lineup.get_active_lineup(game_id, team_id)
        
        lineup = {}
        for row in rows:
            pos = row['position_number']
            lineup[pos] = LineupEntry(
                position=pos,
                player_id=row['player_id'],
                role_code=row['role_code'],
                is_server=bool(row['is_server']),
                placed_at=datetime.fromisoformat(row['placed_at']) if isinstance(row['placed_at'], str) else row['placed_at']
            )
        return lineup
    
    def _get_active_lineup_snapshot(self, game_id: int, team_id: int) -> dict:
        """Get current active lineup as a serializable snapshot dictionary.
        
        Returns a dict with position -> {player_id, role_code, is_server} for JSON serialization.
        """
        lineup = self._get_active_lineup(game_id, team_id)
        snapshot = {}
        for pos, entry in lineup.items():
            snapshot[str(pos)] = {
                'player_id': entry.player_id,
                'role_code': entry.role_code,
                'is_server': entry.is_server
            }
        return snapshot
    
    def _get_rotation_state(self, game_id: int, team_id: int) -> Optional[RotationState]:
        """Get current rotation state for team."""
        row = self.db.rotation.get_rotation_state(game_id, team_id)
        if not row:
            return None
        
        rotation_order = row['rotation_order']
        term_start = None
        if row['term_of_service_start']:
            term_start = datetime.fromisoformat(row['term_of_service_start']) if isinstance(row['term_of_service_start'], str) else row['term_of_service_start']
        
        return RotationState(
            team_id=team_id,
            rotation_order=rotation_order,
            rotation_index=row['rotation_index'],
            serving=bool(row['serving']),
            term_of_service_start=term_start
        )
    
    def _get_rotation_state_snapshot(self, game_id: int, team_id: int) -> Optional[dict]:
        """Get current rotation state as a serializable snapshot dictionary.
        
        Returns a dict with rotation_order, rotation_index, serving, term_of_service_start for JSON serialization.
        """
        state = self._get_rotation_state(game_id, team_id)
        if not state:
            return None
        return {
            'rotation_order': state.rotation_order,
            'rotation_index': state.rotation_index,
            'serving': state.serving,
            'term_of_service_start': state.term_of_service_start.isoformat() if state.term_of_service_start else None
        }
    
    def _get_player_role(self, player_id: int, game_id: Optional[int] = None, team_id: Optional[int] = None) -> Optional[str]:
        """Get player's role code.
        
        For team_us with game_id, uses game_role_code from game_players table.
        Otherwise, falls back to role_code from players table.
        
        Args:
            player_id: Player ID
            game_id: Optional game ID (required for team_us to use game_role_code)
            team_id: Optional team ID (required with game_id to check if team_us)
        
        Returns:
            Role code string or None
        """
        # If game_id and team_id are provided, check if it's team_us and use game_role_code
        if game_id is not None and team_id is not None:
            # Check if this team_id is team_us for this game
            game_teams = self.db.games.get_game_teams(game_id)
            if game_teams and game_teams[0] == team_id:
                # This is team_us - use game_role_code from game_players
                role = self.db.game_players.get_player_game_role(game_id, team_id, player_id)
                if role:
                    return role
        
        # Fallback to role_code from players table (for team_them or when game_id not provided)
        return self.db.players.get_player_role(player_id)
    
    def _update_player_active(self, player_id: int, is_active: bool):
        """Update player's is_active status."""
        self.db.players.update_player_active_status(player_id, is_active)
    
    def _normalize_role_code(self, role_code: str) -> str:
        """Normalize role code (RH -> RS)."""
        return ROLE_ALIASES.get(role_code, role_code)
    
    def role_adjustment_check(self, game_id: int, team_id: int):
        """Check and adjust roles if two setters are on court.
        
        Rule: If two players with role S are on court, the one in a back row
        is the active setter; the other becomes RS.
        """
        lineup = self._get_active_lineup(game_id, team_id)
        if len(lineup) != 6:
            return
        
        # Find all entries with role_code == 'S'
        setter_entries = [
            (pos, entry) for pos, entry in lineup.items()
            if entry.role_code == 'S'
        ]
        
        if len(setter_entries) <= 1:
            return  # No adjustment needed
        
        # Prefer setter who is in back row
        back_row_setters = [
            (pos, entry) for pos, entry in setter_entries
            if pos in BACK_ROW_POSITIONS
        ]
        
        if back_row_setters:
            # Keep the first back-row setter as S
            active_setter_pos, _ = back_row_setters[0]
        else:
            # No back-row setter, keep first one as S
            active_setter_pos, _ = setter_entries[0]
        
        # Convert other setters to RS
        cursor = self.db.conn.cursor()
        for pos, entry in setter_entries:
            if pos != active_setter_pos:
                cursor.execute("""
                    UPDATE active_lineup
                    SET role_code = 'RS'
                    WHERE game_id = %s AND team_id = %s AND position_number = %s
                """, (game_id, team_id, pos))
        
        self.db.conn.commit()
    
    def initialize_game(self, game_id: int, team_id: int, lineup: List[Tuple[int, int]], serving: bool = False):
        """Initialize game with starting lineup.
        
        Args:
            game_id: Game ID
            team_id: Team ID
            lineup: List of (position, player_id) tuples. Must have exactly 6 entries.
            serving: Whether team is currently serving
        
        Raises:
            ValueError: If lineup is invalid
        """
        if len(lineup) != 6:
            raise ValueError(f"Lineup must have exactly 6 players, got {len(lineup)}")
        
        positions = {pos for pos, _ in lineup}
        if positions != ALL_POSITIONS:
            raise ValueError(f"Lineup must include all positions 1-6, got {positions}")
        
        # Validate front/back row distribution
        front_row_count = sum(1 for pos, _ in lineup if pos in FRONT_ROW_POSITIONS)
        back_row_count = sum(1 for pos, _ in lineup if pos in BACK_ROW_POSITIONS)
        
        if front_row_count != 3 or back_row_count != 3:
            raise ValueError(f"Lineup must have 3 front row and 3 back row players")
        
        # Start transaction
        cursor = self.db.conn.cursor()
        try:
            # Clear existing lineup for this game
            cursor.execute("DELETE FROM active_lineup WHERE game_id = %s AND team_id = %s", (game_id, team_id))
            
            # Insert new lineup
            now = datetime.now(timezone.utc)
            for pos, player_id in lineup:
                # Use game_role_code for team_us, fallback to role_code from players
                role = self._get_player_role(player_id, game_id, team_id)
                if not role:
                    # Default role if not set
                    role = 'OH'
                
                role = self._normalize_role_code(role)
                is_server = (pos == 1 and serving)
                
                cursor.execute("""
                    INSERT INTO active_lineup (game_id, team_id, position_number, player_id, role_code, is_server, placed_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (game_id, team_id, pos, player_id, role, 1 if is_server else 0, now))
                
                # Mark player as active
                self._update_player_active(player_id, True)
            
            # Set rotation state
            # Find which player is in position 1 to determine rotation_index
            pos1_player_id = next(player_id for pos, player_id in lineup if pos == 1)
            # For now, assume rotation_index 0 (can be adjusted based on rotation_order)
            rotation_order_json = json.dumps(DEFAULT_ROTATION_ORDER)
            term_start = now if serving else None
            
            cursor.execute("""
                INSERT OR REPLACE INTO rotation_state 
                (game_id, team_id, rotation_order, rotation_index, serving, term_of_service_start)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (game_id, team_id, rotation_order_json, 0, 1 if serving else 0, term_start))
            
            # Run role adjustment check
            self.role_adjustment_check(game_id, team_id)
            
            # Log initial setup event (use game_role_code for team_us)
            lineup_snapshot = {
                pos: {
                    'player_id': player_id,
                    'role_code': self._get_player_role(player_id, game_id, team_id) or 'OH',
                    'is_server': (pos == 1 and serving)
                }
                for pos, player_id in lineup
            }
            
            self._log_event(team_id, 'initial_setup', {
                'lineup': lineup_snapshot,
                'serving': serving,
                'rotation_order': DEFAULT_ROTATION_ORDER
            }, game_id)
            
            self.db.conn.commit()
            
        except Exception as e:
            self.db.conn.rollback()
            raise
    
    def rotate(self, game_id: int, team_id: int):
        """Perform a rotation.
        
        Precondition: Rotation occurs when team gains serve.
        Each player moves to the next position in rotation_order.
        Player at position 1 becomes the server.
        """
        lineup = self._get_active_lineup(game_id, team_id)
        if len(lineup) != 6:
            raise ValueError("Cannot rotate: incomplete lineup")
        
        rotation_state = self._get_rotation_state(game_id, team_id)
        if not rotation_state:
            raise ValueError("Cannot rotate: no rotation state found")
        
        try:
            # Get snapshots before rotation
            active_lineup_snapshot_before = self._get_active_lineup_snapshot(game_id, team_id)
            rotation_state_snapshot_before = self._get_rotation_state_snapshot(game_id, team_id)
            
            # Compute new lineup: each player moves to next position
            new_lineup = {}
            for old_pos, entry in lineup.items():
                new_pos = ROTATION_MAP[old_pos]
                new_lineup[new_pos] = entry
            
            # Update active_lineup
            cursor = self.db.conn.cursor()
            cursor.execute("DELETE FROM active_lineup WHERE game_id = %s AND team_id = %s", (game_id, team_id))
            
            now = datetime.now(timezone.utc)
            for new_pos, entry in new_lineup.items():
                is_server = (new_pos == 1)
                cursor.execute("""
                    INSERT INTO active_lineup 
                    (game_id, team_id, position_number, player_id, role_code, is_server, placed_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (game_id, team_id, new_pos, entry.player_id, entry.role_code, 1 if is_server else 0, now))
            
            # Update rotation_index
            new_rotation_index = (rotation_state.rotation_index + 1) % 6
            cursor.execute("""
                UPDATE rotation_state
                SET rotation_index = %s
                WHERE game_id = %s AND team_id = %s
            """, (new_rotation_index, game_id, team_id))
            
            # Run role adjustment check
            self.role_adjustment_check(game_id, team_id)
            
            # Get snapshots after rotation (and role adjustment)
            active_lineup_snapshot_after = self._get_active_lineup_snapshot(game_id, team_id)
            rotation_state_snapshot_after = self._get_rotation_state_snapshot(game_id, team_id)
            
            # Log rotation event with snapshots
            self._log_event(team_id, 'rotation', {
                'active_lineup_snapshot_before': active_lineup_snapshot_before,
                'active_lineup_snapshot_after': active_lineup_snapshot_after,
                'rotation_state_snapshot_before': rotation_state_snapshot_before,
                'rotation_state_snapshot_after': rotation_state_snapshot_after,
                'rotation_index': new_rotation_index
            }, game_id)
            
            self.db.conn.commit()
            
        except Exception as e:
            self.db.conn.rollback()
            raise
    
    def set_server(self, game_id: int, team_id: int, position_number: int):
        """Set the server for a team.
        
        Only position 1 can be the server. If position_number != 1, 
        this will set the player at position 1 as server.
        
        Args:
            game_id: Game ID
            team_id: Team ID
            position_number: Position number (should be 1, but will auto-correct)
        """
        if position_number != 1:
            # Auto-correct: server must be at position 1
            position_number = 1
        
        cursor = self.db.conn.cursor()
        
        # Check if already serving
        rotation_state = self._get_rotation_state(game_id, team_id)
        was_serving = rotation_state.serving if rotation_state else False
        
        # Set is_server for position 1
        cursor.execute("""
            UPDATE active_lineup
            SET is_server = 1
            WHERE game_id = %s AND team_id = %s AND position_number = 1
        """, (game_id, team_id))
        
        # Clear is_server for other positions
        cursor.execute("""
            UPDATE active_lineup
            SET is_server = 0
            WHERE game_id = %s AND team_id = %s AND position_number != 1
        """, (game_id, team_id))
        
        # Update rotation_state if serving state changed
        if not was_serving:
            now = datetime.now(timezone.utc)
            cursor.execute("""
                UPDATE rotation_state
                SET serving = 1, term_of_service_start = %s
                WHERE game_id = %s AND team_id = %s
            """, (now, game_id, team_id))
        
        # Log server change event
        lineup = self._get_active_lineup(game_id, team_id)
        server_entry = lineup.get(1)
        if server_entry:
            self._log_event(team_id, 'server_change', {
                'position': 1,
                'player_id': server_entry.player_id,
                'serving': True
            }, game_id)
        
        self.db.conn.commit()
    
    def substitution(self, team_id: int, out_player_id: int, in_player_id: int,
                     game_id: Optional[int] = None,
                     out_position: Optional[int] = None, in_position: Optional[int] = None):
        """Perform a substitution.
        
        Args:
            team_id: Team ID
            out_player_id: Player leaving the court
            in_player_id: Player entering the court
            game_id: Game ID (required for tracking)
            out_position: Optional position of outgoing player (validated if provided)
            in_position: Optional position for incoming player (must match out_position if both provided)
        
        Raises:
            ValueError: If substitution is invalid
        """
        if game_id is None:
            raise ValueError("game_id is required for substitution")
        cursor = self.db.conn.cursor()
        
        # Validate in_player exists
        cursor.execute("SELECT player_id FROM players WHERE player_id = %s", (in_player_id,))
        if not cursor.fetchone():
            raise ValueError(f"Player {in_player_id} not found")
        
        # Validate in_player is on bench (not in active_lineup)
        cursor.execute("""
            SELECT player_id FROM active_lineup
            WHERE game_id = %s AND team_id = %s AND player_id = %s
        """, (game_id, team_id, in_player_id))
        if cursor.fetchone():
            raise ValueError(f"Player {in_player_id} is already on court")
        
        # Validate out_player exists
        cursor.execute("SELECT player_id FROM players WHERE player_id = %s", (out_player_id,))
        if not cursor.fetchone():
            raise ValueError(f"Player {out_player_id} not found")
        
        # Validate out_player is on court (in active_lineup)
        cursor.execute("""
            SELECT player_id FROM active_lineup
            WHERE game_id = %s AND team_id = %s AND player_id = %s
        """, (game_id, team_id, out_player_id))
        if not cursor.fetchone():
            raise ValueError(f"Player {out_player_id} is not on court")
        
        # Find out_player's current position
        cursor.execute("""
            SELECT position_number FROM active_lineup
            WHERE game_id = %s AND team_id = %s AND player_id = %s
        """, (game_id, team_id, out_player_id))
        position_row = cursor.fetchone()
        if not position_row:
            raise ValueError(f"Player {out_player_id} not found in active lineup")
        
        actual_out_position = position_row[0]
        
        # Validate positions if provided
        if out_position and out_position != actual_out_position:
            raise ValueError(f"Out player position mismatch: expected {actual_out_position}, got {out_position}")
        
        if in_position and in_position != actual_out_position:
            raise ValueError(f"In position must match out position for substitution")
        
        target_position = actual_out_position
        
        # Get in_player's role (use game_role_code for team_us)
        in_role = self._get_player_role(in_player_id, game_id, team_id)
        
        try:
            # Get snapshot of active_lineup before substitution
            active_lineup_snapshot_before = self._get_active_lineup_snapshot(game_id, team_id)
            
            # Update active_lineup
            in_role_normalized = self._normalize_role_code(in_role) if in_role else 'OH'
            cursor.execute("""
                UPDATE active_lineup
                SET player_id = %s, role_code = %s
                WHERE game_id = %s AND team_id = %s AND position_number = %s
            """, (in_player_id, in_role_normalized, game_id, team_id, target_position))
            
            # Update player active status
            self._update_player_active(out_player_id, False)
            self._update_player_active(in_player_id, True)
            
            # Record substitution
            cursor.execute("""
                INSERT INTO substitutions 
                (game_id, team_id, out_player_id, in_player_id, out_position, in_position, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (game_id, team_id, out_player_id, in_player_id, target_position, target_position, datetime.now(timezone.utc)))
            substitution_id = cursor.lastrowid
            
            # Run role adjustment check
            self.role_adjustment_check(game_id, team_id)
            
            # Get snapshot of active_lineup after substitution (and role adjustment)
            active_lineup_snapshot_after = self._get_active_lineup_snapshot(game_id, team_id)
            
            # Log substitution event with snapshots (use game_role_code for team_us)
            self._log_event(team_id, 'substitution', {
                'substitution_id': substitution_id,
                'out_player_id': out_player_id,
                'in_player_id': in_player_id,
                'position': target_position,
                'out_role': self._get_player_role(out_player_id, game_id, team_id),
                'in_role': in_role_normalized,
                'active_lineup_snapshot_before': active_lineup_snapshot_before,
                'active_lineup_snapshot_after': active_lineup_snapshot_after
            }, game_id)
            
            self.db.conn.commit()
            
        except Exception as e:
            self.db.conn.rollback()
            raise
    
    def libero_replace(self, team_id: int, libero_id: int, replaced_player_id: int,
                      replaced_position: int, action: str, game_id: Optional[int] = None):
        """Perform a libero replacement (enter or exit).
        
        Args:
            team_id: Team ID
            libero_id: Player ID of the libero
            replaced_player_id: Player ID being replaced
            replaced_position: Position number (must be back row)
            action: 'enter' or 'exit'
            game_id: Game ID (required for tracking)
        
        Raises:
            ValueError: If replacement is invalid
        """
        if game_id is None:
            raise ValueError("game_id is required for libero replacement")
        if action not in ('enter', 'exit'):
            raise ValueError(f"Action must be 'enter' or 'exit', got '{action}'")
        
        cursor = self.db.conn.cursor()
        
        # Validate libero role (use game_role_code for team_us)
        libero_role = self._get_player_role(libero_id, game_id, team_id)
        if libero_role != 'Lib':
            raise ValueError(f"Player {libero_id} is not a libero (role: {libero_role})")
        
        try:
            # Get snapshot of active_lineup before libero action
            active_lineup_snapshot_before = self._get_active_lineup_snapshot(game_id, team_id)
            
            if action == 'enter':
                # Validate replaced player is on court at this position
                cursor.execute("""
                    SELECT player_id FROM active_lineup
                    WHERE game_id = %s AND team_id = %s AND position_number = %s
                """, (game_id, team_id, replaced_position))
                pos_row = cursor.fetchone()
                if not pos_row or pos_row[0] != replaced_player_id:
                    raise ValueError(f"Player {replaced_player_id} not at position {replaced_position}")
                
                # Replace in active_lineup
                cursor.execute("""
                    UPDATE active_lineup
                    SET player_id = %s, role_code = 'Lib'
                    WHERE game_id = %s AND team_id = %s AND position_number = %s
                """, (libero_id, game_id, team_id, replaced_position))
                
                # Mark players
                self._update_player_active(replaced_player_id, False)
                self._update_player_active(libero_id, True)
                
            else:  # exit
                # Validate libero is at this position
                cursor.execute("""
                    SELECT player_id FROM active_lineup
                    WHERE game_id = %s AND team_id = %s AND position_number = %s
                """, (game_id, team_id, replaced_position))
                pos_row = cursor.fetchone()
                if not pos_row or pos_row[0] != libero_id:
                    raise ValueError(f"Libero {libero_id} not at position {replaced_position}")
                
                # Replace libero with original player (or validate replacement rule)
                # For now, assume replaced_player_id is the original player
                # Use game_role_code for team_us
                original_role = self._get_player_role(replaced_player_id, game_id, team_id)
                original_role_normalized = self._normalize_role_code(original_role) if original_role else 'OH'
                
                cursor.execute("""
                    UPDATE active_lineup
                    SET player_id = %s, role_code = %s
                    WHERE game_id = %s AND team_id = %s AND position_number = %s
                """, (replaced_player_id, original_role_normalized, game_id, team_id, replaced_position))
                
                # Mark players
                self._update_player_active(libero_id, False)
                self._update_player_active(replaced_player_id, True)
            
            # Record libero action
            cursor.execute("""
                INSERT INTO libero_actions
                (game_id, team_id, libero_id, replaced_player_id, replaced_position, action, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (game_id, team_id, libero_id, replaced_player_id, replaced_position, action, datetime.now(timezone.utc)))
            libero_action_id = cursor.lastrowid
            
            # Run role adjustment check
            self.role_adjustment_check(game_id, team_id)
            
            # Get snapshot of active_lineup after libero action (and role adjustment)
            active_lineup_snapshot_after = self._get_active_lineup_snapshot(game_id, team_id)
            
            # Log libero event with snapshots
            self._log_event(team_id, 'libero', {
                'libero_action_id': libero_action_id,
                'action': action,
                'libero_id': libero_id,
                'replaced_player_id': replaced_player_id,
                'position': replaced_position,
                'active_lineup_snapshot_before': active_lineup_snapshot_before,
                'active_lineup_snapshot_after': active_lineup_snapshot_after
            }, game_id)
            
            self.db.conn.commit()
            
        except Exception as e:
            self.db.conn.rollback()
            raise
    
    def get_current_lineup(self, game_id: int, team_id: int) -> Dict[int, Dict]:
        """Get current lineup as a dictionary with player info."""
        lineup = self._get_active_lineup(game_id, team_id)
        cursor = self.db.conn.cursor()
        
        result = {}
        for pos, entry in lineup.items():
            cursor.execute("""
                SELECT name, jersey, player_number FROM players WHERE player_id = %s
            """, (entry.player_id,))
            player_row = cursor.fetchone()
            
            result[pos] = {
                'player_id': entry.player_id,
                'name': player_row[0] if player_row else None,
                'jersey': player_row[1] if player_row else None,
                'player_number': player_row[2] if player_row else None,
                'role_code': entry.role_code,
                'is_server': entry.is_server
            }
        
        return result
    
    def get_rotation_state_dict(self, game_id: int, team_id: int) -> Optional[Dict]:
        """Get rotation state as dictionary."""
        state = self._get_rotation_state(game_id, team_id)
        if not state:
            return None
        
        return {
            'team_id': state.team_id,
            'rotation_order': state.rotation_order,
            'rotation_index': state.rotation_index,
            'serving': state.serving,
            'term_of_service_start': state.term_of_service_start.isoformat() if state.term_of_service_start else None
        }
    
    def restore_initial_lineup(self, team_id: int, game_id: Optional[int] = None) -> Tuple[bool, bool]:
        """Restore the initial lineup from the initial_setup event.
        
        Args:
            team_id: Team ID to restore lineup for
            game_id: Game ID (required to delete substitutions and libero actions)
            
        Returns:
            Tuple of (success: bool, serving: bool) - success indicates if initial setup was found and restored
            
        Raises:
            ValueError: If initial setup cannot be restored
        """
        cursor = self.db.conn.cursor()
        
        # Find the initial_setup event for this game (should be the first one)
        cursor.execute("""
            SELECT payload, created_at
            FROM events
            WHERE game_id = %s AND team_id = %s AND event_type = 'initial_setup'
            ORDER BY created_at ASC
            LIMIT 1
        """, (game_id, team_id))
        
        result = cursor.fetchone()
        if not result:
            return False, False
        
        payload_json = result[0]
        try:
            payload = json.loads(payload_json) if isinstance(payload_json, str) else payload_json
        except json.JSONDecodeError:
            raise ValueError("Failed to parse initial_setup payload")
        
        lineup_snapshot = payload.get('lineup', {})
        serving = payload.get('serving', False)
        rotation_order = payload.get('rotation_order', DEFAULT_ROTATION_ORDER)
        
        if not lineup_snapshot or len(lineup_snapshot) != 6:
            raise ValueError("Invalid initial lineup in event")
        
        try:
            if not game_id:
                raise ValueError("game_id is required to restore initial lineup")
            
            # Get current active lineup players for this game before clearing
            cursor.execute("""
                SELECT player_id FROM active_lineup 
                WHERE game_id = %s AND team_id = %s
            """, (game_id, team_id))
            current_active_players = [row[0] for row in cursor.fetchall()]
            
            # Clear current active lineup for this game only
            cursor.execute("DELETE FROM active_lineup WHERE game_id = %s AND team_id = %s", (game_id, team_id))
            
            # Mark only players who were active in THIS game as inactive
            if current_active_players:
                placeholders = ','.join('%s' * len(current_active_players))
                cursor.execute(f"""
                    UPDATE players 
                    SET is_active = 0 
                    WHERE player_id IN ({placeholders})
                """, current_active_players)
            
            # Restore initial lineup
            now = datetime.now(timezone.utc)
            restored_lineup = []
            for pos in sorted(lineup_snapshot.keys(), key=int):
                player_data = lineup_snapshot[pos]
                player_id = player_data['player_id']
                role_code = player_data.get('role_code', 'OH')
                is_server = player_data.get('is_server', False)
                
                role_code = self._normalize_role_code(role_code)
                
                cursor.execute("""
                    INSERT INTO active_lineup (game_id, team_id, position_number, player_id, role_code, is_server, placed_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (game_id, team_id, int(pos), player_id, role_code, 1 if is_server else 0, now))
                
                # Mark player as active
                self._update_player_active(player_id, True)
                
                restored_lineup.append((int(pos), player_id))
            
            # Restore rotation state
            rotation_order_json = json.dumps(rotation_order)
            term_start = now if serving else None
            
            cursor.execute("""
                INSERT OR REPLACE INTO rotation_state 
                (game_id, team_id, rotation_order, rotation_index, serving, term_of_service_start)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (game_id, team_id, rotation_order_json, 0, 1 if serving else 0, term_start))
            
            # Delete all substitutions for this game
            cursor.execute("DELETE FROM substitutions WHERE game_id = %s", (game_id,))
            
            # Delete all libero actions for this game
            cursor.execute("DELETE FROM libero_actions WHERE game_id = %s", (game_id,))
            
            # Run role adjustment check
            self.role_adjustment_check(game_id, team_id)
            
            self.db.conn.commit()
            return True, serving
            
        except Exception as e:
            self.db.conn.rollback()
            raise
    
    def _restore_active_lineup_from_snapshot(self, game_id: int, team_id: int, snapshot: dict):
        """Restore active_lineup from a snapshot dictionary.
        
        Args:
            game_id: Game ID
            team_id: Team ID
            snapshot: Dictionary with position -> {player_id, role_code, is_server}
        """
        cursor = self.db.conn.cursor()
        
        # Clear current active lineup for this game/team
        cursor.execute("DELETE FROM active_lineup WHERE game_id = %s AND team_id = %s", (game_id, team_id))
        
        # Mark all players from this team as inactive first
        cursor.execute("""
            UPDATE players 
            SET is_active = 0 
            WHERE team_id = %s
        """, (team_id,))
        
        # Restore lineup from snapshot
        now = datetime.now(timezone.utc)
        for pos_str, player_data in snapshot.items():
            pos = int(pos_str)
            player_id = player_data['player_id']
            role_code = player_data.get('role_code', 'OH')
            is_server = player_data.get('is_server', False)
            
            cursor.execute("""
                INSERT INTO active_lineup (game_id, team_id, position_number, player_id, role_code, is_server, placed_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (game_id, team_id, pos, player_id, role_code, 1 if is_server else 0, now))
            
            # Mark player as active
            self._update_player_active(player_id, True)
    
    def _restore_rotation_state_from_snapshot(self, game_id: int, team_id: int, snapshot: dict):
        """Restore rotation_state from a snapshot dictionary.
        
        Args:
            game_id: Game ID
            team_id: Team ID
            snapshot: Dictionary with rotation_order, rotation_index, serving, term_of_service_start
        """
        cursor = self.db.conn.cursor()
        
        rotation_order = snapshot.get('rotation_order', DEFAULT_ROTATION_ORDER)
        rotation_index = snapshot.get('rotation_index', 0)
        serving = snapshot.get('serving', False)
        term_start_str = snapshot.get('term_of_service_start')
        
        term_start = None
        if term_start_str:
            try:
                term_start = datetime.fromisoformat(term_start_str) if isinstance(term_start_str, str) else term_start_str
            except (ValueError, TypeError):
                term_start = None
        
        rotation_order_json = json.dumps(rotation_order)
        
        cursor.execute("""
            INSERT OR REPLACE INTO rotation_state 
            (game_id, team_id, rotation_order, rotation_index, serving, term_of_service_start)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (game_id, team_id, rotation_order_json, rotation_index, 1 if serving else 0, term_start))
    
    def _delete_substitution(self, substitution_id: int):
        """Delete a substitution record.
        
        Args:
            substitution_id: Substitution ID to delete
        """
        cursor = self.db.conn.cursor()
        cursor.execute("DELETE FROM substitutions WHERE id = %s", (substitution_id,))
        self.db.conn.commit()
    
    def _delete_libero_action(self, libero_action_id: int):
        """Delete a libero action record.
        
        Args:
            libero_action_id: Libero action ID to delete
        """
        cursor = self.db.conn.cursor()
        cursor.execute("DELETE FROM libero_actions WHERE id = %s", (libero_action_id,))
        self.db.conn.commit()



