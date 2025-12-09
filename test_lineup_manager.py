"""
Unit tests for lineup manager functionality.
"""

import unittest
import os
import tempfile
from database import VideoStatsDB
from lineup_manager import LineupManager
from lineup_models import FRONT_ROW_POSITIONS, BACK_ROW_POSITIONS


class TestLineupManager(unittest.TestCase):
    """Test cases for LineupManager."""
    
    def setUp(self):
        """Set up test database and manager."""
        # Create temporary database
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name
        
        self.db = VideoStatsDB(db_path=self.db_path)
        self.db.initialize_database()
        self.db.connect()
        
        self.manager = LineupManager(self.db)
        
        # Create test team
        self.team_id = self.db.add_team("Test Team")
        
        # Create test players
        self.players = {}
        roles = ['S', 'RS', 'MH', 'OH', 'OH', 'Lib', 'DS', 'OH', 'OH', 'OH', 'OH', 'OH']
        for i, role in enumerate(roles, 1):
            player_id = self.db.add_player(self.team_id, str(i), f"Player {i}")
            # Set role_code
            cursor = self.db.conn.cursor()
            cursor.execute("UPDATE players SET role_code = ?, jersey = ? WHERE player_id = ?",
                         (role, i, player_id))
            self.players[i] = player_id
        self.db.conn.commit()
    
    def tearDown(self):
        """Clean up test database."""
        self.db.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    def test_initialize_game_valid(self):
        """Test initializing game with valid lineup."""
        lineup = [
            (1, self.players[1]),  # S
            (6, self.players[2]),  # RS
            (5, self.players[3]),   # MH
            (4, self.players[4]),  # OH
            (3, self.players[5]),  # OH
            (2, self.players[7])   # DS (not libero - position 2 is front row)
        ]
        
        self.manager.initialize_game(self.team_id, lineup, serving=True)
        
        # Verify lineup
        current = self.manager.get_current_lineup(self.team_id)
        self.assertEqual(len(current), 6)
        self.assertTrue(current[1]['is_server'])
        
        # Verify rotation state
        state = self.manager.get_rotation_state_dict(self.team_id)
        self.assertIsNotNone(state)
        self.assertTrue(state['serving'])
    
    def test_initialize_game_invalid_length(self):
        """Test initializing with wrong number of players."""
        lineup = [(1, self.players[1]), (2, self.players[2])]
        
        with self.assertRaises(ValueError):
            self.manager.initialize_game(self.team_id, lineup)
    
    def test_initialize_game_libero_front_row(self):
        """Test that libero cannot be placed in front row."""
        lineup = [
            (1, self.players[1]),
            (6, self.players[2]),
            (5, self.players[3]),
            (4, self.players[6]),  # Lib in front row - should fail
            (3, self.players[4]),
            (2, self.players[5])
        ]
        
        with self.assertRaises(ValueError):
            self.manager.initialize_game(self.team_id, lineup)
    
    def test_rotate(self):
        """Test rotation functionality."""
        # Initialize
        lineup = [
            (1, self.players[1]),
            (6, self.players[2]),
            (5, self.players[3]),
            (4, self.players[4]),
            (3, self.players[5]),
            (2, self.players[7])
        ]
        self.manager.initialize_game(self.team_id, lineup, serving=False)
        
        # Get initial lineup
        initial = self.manager.get_current_lineup(self.team_id)
        player_at_1 = initial[1]['player_id']
        
        # Rotate
        self.manager.rotate(self.team_id)
        
        # Verify rotation
        after = self.manager.get_current_lineup(self.team_id)
        # Player who was at position 1 should now be at position 6
        self.assertEqual(after[6]['player_id'], player_at_1)
        # Player who was at position 6 should now be at position 5
        self.assertEqual(after[5]['player_id'], initial[6]['player_id'])
        # Position 1 should now have the server
        self.assertTrue(after[1]['is_server'])
    
    def test_set_server(self):
        """Test setting server."""
        lineup = [
            (1, self.players[1]),
            (6, self.players[2]),
            (5, self.players[3]),
            (4, self.players[4]),
            (3, self.players[5]),
            (2, self.players[7])
        ]
        self.manager.initialize_game(self.team_id, lineup, serving=False)
        
        # Set server
        self.manager.set_server(self.team_id, 1)
        
        # Verify
        current = self.manager.get_current_lineup(self.team_id)
        self.assertTrue(current[1]['is_server'])
        self.assertFalse(current[2]['is_server'])
        
        # Verify rotation state updated
        state = self.manager.get_rotation_state_dict(self.team_id)
        self.assertTrue(state['serving'])
    
    def test_substitution(self):
        """Test substitution."""
        lineup = [
            (1, self.players[1]),
            (6, self.players[2]),
            (5, self.players[3]),
            (4, self.players[4]),
            (3, self.players[5]),
            (2, self.players[7])
        ]
        self.manager.initialize_game(self.team_id, lineup, serving=False)
        
        # Substitute player at position 4
        self.manager.substitution(self.team_id, self.players[4], self.players[8], out_position=4)
        
        # Verify
        current = self.manager.get_current_lineup(self.team_id)
        self.assertEqual(current[4]['player_id'], self.players[8])
        
        # Verify player status
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT is_active FROM players WHERE player_id = ?", (self.players[4],))
        self.assertFalse(bool(cursor.fetchone()[0]))
        cursor.execute("SELECT is_active FROM players WHERE player_id = ?", (self.players[8],))
        self.assertTrue(bool(cursor.fetchone()[0]))
    
    def test_substitution_libero_front_row_reject(self):
        """Test that libero cannot be substituted into front row."""
        lineup = [
            (1, self.players[1]),
            (6, self.players[2]),
            (5, self.players[3]),
            (4, self.players[4]),
            (3, self.players[5]),
            (2, self.players[7])
        ]
        self.manager.initialize_game(self.team_id, lineup, serving=False)
        
        # Try to substitute libero into front row position 4
        with self.assertRaises(ValueError):
            self.manager.substitution(self.team_id, self.players[4], self.players[6], out_position=4)
    
    def test_libero_replace_enter(self):
        """Test libero entering to replace back row player."""
        lineup = [
            (1, self.players[1]),
            (6, self.players[2]),
            (5, self.players[3]),
            (4, self.players[4]),
            (3, self.players[5]),
            (2, self.players[7])
        ]
        self.manager.initialize_game(self.team_id, lineup, serving=False)
        
        # Libero enters at position 5 (back row)
        self.manager.libero_replace(self.team_id, self.players[6], self.players[3], 5, 'enter')
        
        # Verify
        current = self.manager.get_current_lineup(self.team_id)
        self.assertEqual(current[5]['player_id'], self.players[6])
        self.assertEqual(current[5]['role_code'], 'Lib')
    
    def test_libero_replace_front_row_reject(self):
        """Test that libero cannot replace front row player."""
        lineup = [
            (1, self.players[1]),
            (6, self.players[2]),
            (5, self.players[3]),
            (4, self.players[4]),
            (3, self.players[5]),
            (2, self.players[7])
        ]
        self.manager.initialize_game(self.team_id, lineup, serving=False)
        
        # Try to enter at front row position 4
        with self.assertRaises(ValueError):
            self.manager.libero_replace(self.team_id, self.players[6], self.players[4], 4, 'enter')
    
    def test_role_adjustment_two_setters(self):
        """Test role adjustment when two setters are on court."""
        # Create two setters
        cursor = self.db.conn.cursor()
        cursor.execute("UPDATE players SET role_code = 'S' WHERE player_id = ?", (self.players[8],))
        self.db.conn.commit()
        
        lineup = [
            (1, self.players[1]),  # S in back row
            (6, self.players[2]),
            (5, self.players[3]),
            (4, self.players[4]),
            (3, self.players[8]),  # S in front row
            (2, self.players[7])
        ]
        self.manager.initialize_game(self.team_id, lineup, serving=False)
        
        # Verify role adjustment: back row S stays S, front row S becomes RS
        current = self.manager.get_current_lineup(self.team_id)
        self.assertEqual(current[1]['role_code'], 'S')  # Back row setter stays S
        self.assertEqual(current[3]['role_code'], 'RS')  # Front row setter becomes RS


if __name__ == '__main__':
    unittest.main()

