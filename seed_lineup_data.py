"""
Example seed data script for lineup management.
Creates a team with 12 players and sets up an initial lineup.
"""

from database import VideoStatsDB
from lineup_manager import LineupManager


def seed_team_data(db: VideoStatsDB, team_name: str = "Team_us"):
    """Create a team with 12 players and example roles.
    
    Args:
        db: Database connection
        team_name: Name of the team
    
    Returns:
        Tuple of (team_id, player_ids_dict)
    """
    # Create or get team
    cursor = db.conn.cursor()
    cursor.execute("SELECT team_id FROM teams WHERE name = ?", (team_name,))
    result = cursor.fetchone()
    
    if result:
        team_id = result[0]
        print(f"Using existing team: {team_name} (ID: {team_id})")
    else:
        team_id = db.add_team(team_name)
        print(f"Created team: {team_name} (ID: {team_id})")
    
    # Player roster with roles
    players_data = [
        (1, "Alice", "S"),      # Setter
        (2, "Bob", "RS"),       # Right Side
        (3, "Charlie", "MH"),   # Middle Hitter
        (4, "Diana", "OH"),     # Outside Hitter
        (5, "Eve", "OH"),       # Outside Hitter
        (6, "Frank", "Lib"),    # Libero
        (7, "Grace", "DS"),     # Defensive Specialist
        (8, "Henry", "S"),      # Setter (backup)
        (9, "Iris", "RS"),      # Right Side (backup)
        (10, "Jack", "MH"),     # Middle Hitter (backup)
        (11, "Kate", "OH"),     # Outside Hitter (backup)
        (12, "Liam", "OH"),     # Outside Hitter (backup)
    ]
    
    player_ids = {}
    
    for jersey, name, role in players_data:
        # Check if player exists
        cursor.execute("""
            SELECT player_id FROM players 
            WHERE team_id = ? AND jersey = ?
        """, (team_id, jersey))
        result = cursor.fetchone()
        
        if result:
            player_id = result[0]
            # Update role if needed
            cursor.execute("UPDATE players SET role_code = ?, name = ? WHERE player_id = ?",
                         (role, name, player_id))
        else:
            # Create new player
            player_id = db.add_player(team_id, str(jersey), name)
            cursor.execute("UPDATE players SET role_code = ?, jersey = ? WHERE player_id = ?",
                         (role, jersey, player_id))
        
        player_ids[jersey] = player_id
        print(f"  Player {jersey}: {name} ({role}) - ID: {player_id}")
    
    db.conn.commit()
    return team_id, player_ids


def create_initial_lineup(manager: LineupManager, team_id: int, player_ids: dict, serving: bool = True):
    """Create an initial lineup.
    
    Args:
        manager: LineupManager instance
        team_id: Team ID
        player_ids: Dictionary mapping jersey number to player_id
        serving: Whether team is serving
    """
    # Example starting lineup:
    # Position 1 (Right Back): Setter (Alice)
    # Position 6 (Middle Back): Right Side (Bob)
    # Position 5 (Left Back): Middle Hitter (Charlie)
    # Position 4 (Left Front): Outside Hitter (Diana)
    # Position 3 (Middle Front): Outside Hitter (Eve)
    # Position 2 (Right Front): Outside Hitter (Grace) - not libero in front row
    
    lineup = [
        (1, player_ids[1]),   # Alice (S) at position 1
        (6, player_ids[2]),   # Bob (RS) at position 6
        (5, player_ids[3]),   # Charlie (MH) at position 5
        (4, player_ids[4]),   # Diana (OH) at position 4
        (3, player_ids[5]),   # Eve (OH) at position 3
        (2, player_ids[7]),   # Grace (DS) at position 2
    ]
    
    try:
        manager.initialize_game(team_id, lineup, serving=serving)
        print(f"\nInitial lineup set successfully!")
        print(f"  Serving: {serving}")
        
        # Display lineup
        current = manager.get_current_lineup(team_id)
        print("\nCurrent Lineup:")
        for pos in sorted(current.keys()):
            entry = current[pos]
            server_marker = " [SERVER]" if entry['is_server'] else ""
            print(f"  Position {pos}: {entry['name']} (#{entry['jersey']}, {entry['role_code']}){server_marker}")
        
        # Display rotation state
        state = manager.get_rotation_state_dict(team_id)
        if state:
            print(f"\nRotation State:")
            print(f"  Rotation Order: {state['rotation_order']}")
            print(f"  Rotation Index: {state['rotation_index']}")
            print(f"  Serving: {state['serving']}")
        
    except Exception as e:
        print(f"Error initializing lineup: {e}")
        raise


def main():
    """Main function to seed data."""
    db = VideoStatsDB()
    db.initialize_database()
    db.connect()
    
    try:
        # Create team and players
        team_id, player_ids = seed_team_data(db, "Team_us")
        
        # Create lineup manager
        manager = LineupManager(db)
        
        # Create initial lineup
        print("\n" + "="*50)
        create_initial_lineup(manager, team_id, player_ids, serving=True)
        
        print("\n" + "="*50)
        print("Seed data created successfully!")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()

