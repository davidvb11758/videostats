"""
JSON export and import routines for lineup state.
"""

import json
from datetime import datetime
from typing import Dict, List, Optional
from database import VideoStatsDB
from lineup_manager import LineupManager


def export_lineup_state(db: VideoStatsDB, team_id: int) -> Dict:
    """Export current lineup state to JSON-serializable dictionary.
    
    Args:
        db: Database connection
        team_id: Team ID
    
    Returns:
        Dictionary with lineup state
    """
    manager = LineupManager(db)
    
    # Get current lineup
    lineup = manager.get_current_lineup(team_id)
    
    # Get rotation state
    rotation_state = manager.get_rotation_state_dict(team_id)
    
    # Get recent events
    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT event_type, payload, created_at
        FROM events
        WHERE team_id = ?
        ORDER BY created_at DESC
        LIMIT 100
    """, (team_id,))
    
    events = []
    for row in cursor.fetchall():
        try:
            payload = json.loads(row[1]) if isinstance(row[1], str) else row[1]
        except:
            payload = row[1]
        
        events.append({
            'event_type': row[0],
            'payload': payload,
            'created_at': row[2]
        })
    
    # Get substitutions
    cursor.execute("""
        SELECT out_player_id, in_player_id, out_position, in_position, created_at
        FROM substitutions
        WHERE team_id = ?
        ORDER BY created_at DESC
    """, (team_id,))
    
    substitutions = []
    for row in cursor.fetchall():
        substitutions.append({
            'out_player_id': row[0],
            'in_player_id': row[1],
            'out_position': row[2],
            'in_position': row[3],
            'created_at': row[4]
        })
    
    # Get libero actions
    cursor.execute("""
        SELECT libero_id, replaced_player_id, replaced_position, action, created_at
        FROM libero_actions
        WHERE team_id = ?
        ORDER BY created_at DESC
    """, (team_id,))
    
    libero_actions = []
    for row in cursor.fetchall():
        libero_actions.append({
            'libero_id': row[0],
            'replaced_player_id': row[1],
            'replaced_position': row[2],
            'action': row[3],
            'created_at': row[4]
        })
    
    # Get team info
    cursor.execute("SELECT name FROM teams WHERE team_id = ?", (team_id,))
    team_row = cursor.fetchone()
    team_name = team_row[0] if team_row else None
    
    # Get player info
    cursor.execute("""
        SELECT player_id, name, jersey, player_number, role_code, is_active
        FROM players
        WHERE team_id = ?
        ORDER BY jersey
    """, (team_id,))
    
    players = []
    for row in cursor.fetchall():
        players.append({
            'player_id': row[0],
            'name': row[1],
            'jersey': row[2],
            'player_number': row[3],
            'role_code': row[4],
            'is_active': bool(row[5]) if row[5] is not None else False
        })
    
    return {
        'team_id': team_id,
        'team_name': team_name,
        'exported_at': datetime.utcnow().isoformat(),
        'lineup': lineup,
        'rotation_state': rotation_state,
        'players': players,
        'events': events,
        'substitutions': substitutions,
        'libero_actions': libero_actions
    }


def export_to_file(db: VideoStatsDB, team_id: int, filename: str):
    """Export lineup state to JSON file.
    
    Args:
        db: Database connection
        team_id: Team ID
        filename: Output filename
    """
    state = export_lineup_state(db, team_id)
    
    with open(filename, 'w') as f:
        json.dump(state, f, indent=2, default=str)
    
    print(f"Lineup state exported to {filename}")


def import_lineup_state(db: VideoStatsDB, state: Dict, team_id: Optional[int] = None):
    """Import lineup state from dictionary.
    
    Note: This is a read-only import for viewing/analysis.
    To actually set lineup, use LineupManager.initialize_game().
    
    Args:
        db: Database connection
        state: Dictionary with lineup state
        team_id: Optional team ID (if None, uses state['team_id'])
    """
    if team_id is None:
        team_id = state.get('team_id')
        if not team_id:
            raise ValueError("team_id not found in state")
    
    print(f"Importing lineup state for team_id={team_id}")
    print(f"  Team: {state.get('team_name')}")
    print(f"  Exported at: {state.get('exported_at')}")
    
    if 'lineup' in state:
        print("\nLineup:")
        for pos in sorted(state['lineup'].keys()):
            entry = state['lineup'][pos]
            server_marker = " [SERVER]" if entry.get('is_server') else ""
            print(f"  Position {pos}: {entry.get('name')} (#{entry.get('jersey')}, {entry.get('role_code')}){server_marker}")
    
    if 'rotation_state' in state and state['rotation_state']:
        rs = state['rotation_state']
        print(f"\nRotation State:")
        print(f"  Rotation Order: {rs.get('rotation_order')}")
        print(f"  Rotation Index: {rs.get('rotation_index')}")
        print(f"  Serving: {rs.get('serving')}")
    
    if 'events' in state:
        print(f"\nEvents: {len(state['events'])} events")
    
    if 'substitutions' in state:
        print(f"Substitutions: {len(state['substitutions'])} substitutions")
    
    if 'libero_actions' in state:
        print(f"Libero Actions: {len(state['libero_actions'])} actions")


def import_from_file(db: VideoStatsDB, filename: str, team_id: Optional[int] = None):
    """Import lineup state from JSON file.
    
    Args:
        db: Database connection
        filename: Input filename
        team_id: Optional team ID override
    """
    with open(filename, 'r') as f:
        state = json.load(f)
    
    import_lineup_state(db, state, team_id)


def main():
    """Example usage."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python lineup_export.py <command> [args]")
        print("Commands:")
        print("  export <team_id> <filename>  - Export lineup state")
        print("  import <filename> [team_id] - Import lineup state")
        return
    
    command = sys.argv[1]
    db = VideoStatsDB()
    db.connect()
    
    try:
        if command == 'export':
            if len(sys.argv) < 4:
                print("Usage: export <team_id> <filename>")
                return
            team_id = int(sys.argv[2])
            filename = sys.argv[3]
            export_to_file(db, team_id, filename)
        
        elif command == 'import':
            if len(sys.argv) < 3:
                print("Usage: import <filename> [team_id]")
                return
            filename = sys.argv[2]
            team_id = int(sys.argv[3]) if len(sys.argv) > 3 else None
            import_from_file(db, filename, team_id)
        
        else:
            print(f"Unknown command: {command}")
    
    finally:
        db.close()


if __name__ == "__main__":
    main()

