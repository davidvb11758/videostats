"""
CLI script for managing volleyball lineup state.
Commands: init, rotate, sub, libero-enter, libero-exit, export-state, show-state
"""

import sys
import argparse
from database import VideoStatsDB
from lineup_manager import LineupManager
from lineup_export import export_to_file, import_from_file


def cmd_init(args, db, manager):
    """Initialize game with starting lineup."""
    if not args.team_id:
        print("Error: --team-id required")
        return 1
    
    # Parse lineup: format "pos:player_id,pos:player_id,..."
    lineup = []
    for pair in args.lineup.split(','):
        pos_str, player_str = pair.split(':')
        lineup.append((int(pos_str), int(player_str)))
    
    serving = args.serving if args.serving is not None else False
    
    try:
        manager.initialize_game(args.team_id, lineup, serving=serving)
        print(f"Game initialized for team {args.team_id}")
        print(f"  Serving: {serving}")
        
        # Show lineup
        current = manager.get_current_lineup(args.team_id)
        print("\nLineup:")
        for pos in sorted(current.keys()):
            entry = current[pos]
            server_marker = " [SERVER]" if entry['is_server'] else ""
            print(f"  Position {pos}: {entry['name']} (#{entry['jersey']}, {entry['role_code']}){server_marker}")
        
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


def cmd_rotate(args, db, manager):
    """Perform rotation."""
    if not args.team_id:
        print("Error: --team-id required")
        return 1
    
    try:
        manager.rotate(args.team_id)
        print(f"Rotation performed for team {args.team_id}")
        
        # Show updated lineup
        current = manager.get_current_lineup(args.team_id)
        print("\nLineup after rotation:")
        for pos in sorted(current.keys()):
            entry = current[pos]
            server_marker = " [SERVER]" if entry['is_server'] else ""
            print(f"  Position {pos}: {entry['name']} (#{entry['jersey']}, {entry['role_code']}){server_marker}")
        
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


def cmd_set_server(args, db, manager):
    """Set server."""
    if not args.team_id:
        print("Error: --team-id required")
        return 1
    
    position = args.position if args.position else 1
    
    try:
        manager.set_server(args.team_id, position)
        print(f"Server set for team {args.team_id} at position {position}")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


def cmd_sub(args, db, manager):
    """Perform substitution."""
    if not args.team_id:
        print("Error: --team-id required")
        return 1
    
    if not args.out_player or not args.in_player:
        print("Error: --out-player and --in-player required")
        return 1
    
    try:
        manager.substitution(
            args.team_id,
            int(args.out_player),
            int(args.in_player),
            out_position=int(args.position) if args.position else None,
            in_position=int(args.position) if args.position else None
        )
        print(f"Substitution: Player {args.out_player} out, Player {args.in_player} in")
        
        # Show updated lineup
        current = manager.get_current_lineup(args.team_id)
        print("\nLineup after substitution:")
        for pos in sorted(current.keys()):
            entry = current[pos]
            server_marker = " [SERVER]" if entry['is_server'] else ""
            print(f"  Position {pos}: {entry['name']} (#{entry['jersey']}, {entry['role_code']}){server_marker}")
        
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


def cmd_libero_enter(args, db, manager):
    """Libero enters to replace player."""
    if not args.team_id:
        print("Error: --team-id required")
        return 1
    
    if not args.libero or not args.replaced_player or not args.position:
        print("Error: --libero, --replaced-player, and --position required")
        return 1
    
    try:
        manager.libero_replace(
            args.team_id,
            int(args.libero),
            int(args.replaced_player),
            int(args.position),
            'enter'
        )
        print(f"Libero {args.libero} entered at position {args.position}")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


def cmd_libero_exit(args, db, manager):
    """Libero exits, replaced by original player."""
    if not args.team_id:
        print("Error: --team-id required")
        return 1
    
    if not args.libero or not args.replaced_player or not args.position:
        print("Error: --libero, --replaced-player, and --position required")
        return 1
    
    try:
        manager.libero_replace(
            args.team_id,
            int(args.libero),
            int(args.replaced_player),
            int(args.position),
            'exit'
        )
        print(f"Libero {args.libero} exited at position {args.position}")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


def cmd_export_state(args, db, manager):
    """Export lineup state to JSON."""
    if not args.team_id:
        print("Error: --team-id required")
        return 1
    
    filename = args.filename if args.filename else f"lineup_state_team_{args.team_id}.json"
    
    try:
        export_to_file(db, args.team_id, filename)
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


def cmd_show_state(args, db, manager):
    """Show current lineup state."""
    if not args.team_id:
        print("Error: --team-id required")
        return 1
    
    try:
        current = manager.get_current_lineup(args.team_id)
        rotation_state = manager.get_rotation_state_dict(args.team_id)
        
        print(f"\nLineup for Team {args.team_id}:")
        print("=" * 50)
        
        if not current:
            print("No active lineup")
            return 0
        
        print("\nCurrent Lineup:")
        for pos in sorted(current.keys()):
            entry = current[pos]
            server_marker = " [SERVER]" if entry['is_server'] else ""
            print(f"  Position {pos}: {entry['name']} (#{entry['jersey']}, {entry['role_code']}){server_marker}")
        
        if rotation_state:
            print(f"\nRotation State:")
            print(f"  Rotation Order: {rotation_state['rotation_order']}")
            print(f"  Rotation Index: {rotation_state['rotation_index']}")
            print(f"  Serving: {rotation_state['serving']}")
            if rotation_state['term_of_service_start']:
                print(f"  Term Started: {rotation_state['term_of_service_start']}")
        
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description='VideoStats Lineup Management CLI')
    parser.add_argument('--db', default='videostats.db', help='Database file path')
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Init command
    init_parser = subparsers.add_parser('init', help='Initialize game with starting lineup')
    init_parser.add_argument('--team-id', type=int, required=True)
    init_parser.add_argument('--lineup', required=True, help='Lineup as "pos:player_id,pos:player_id,..."')
    init_parser.add_argument('--serving', action='store_true', help='Team is serving')
    
    # Rotate command
    rotate_parser = subparsers.add_parser('rotate', help='Perform rotation')
    rotate_parser.add_argument('--team-id', type=int, required=True)
    
    # Set server command
    server_parser = subparsers.add_parser('set-server', help='Set server')
    server_parser.add_argument('--team-id', type=int, required=True)
    server_parser.add_argument('--position', type=int, default=1, help='Position (default: 1)')
    
    # Substitution command
    sub_parser = subparsers.add_parser('sub', help='Perform substitution')
    sub_parser.add_argument('--team-id', type=int, required=True)
    sub_parser.add_argument('--out-player', type=int, help='Outgoing player ID')
    sub_parser.add_argument('--in-player', type=int, help='Incoming player ID')
    sub_parser.add_argument('--position', type=int, help='Position number')
    
    # Libero enter command
    libero_enter_parser = subparsers.add_parser('libero-enter', help='Libero enters')
    libero_enter_parser.add_argument('--team-id', type=int, required=True)
    libero_enter_parser.add_argument('--libero', type=int, help='Libero player ID')
    libero_enter_parser.add_argument('--replaced-player', type=int, help='Replaced player ID')
    libero_enter_parser.add_argument('--position', type=int, help='Position number')
    
    # Libero exit command
    libero_exit_parser = subparsers.add_parser('libero-exit', help='Libero exits')
    libero_exit_parser.add_argument('--team-id', type=int, required=True)
    libero_exit_parser.add_argument('--libero', type=int, help='Libero player ID')
    libero_exit_parser.add_argument('--replaced-player', type=int, help='Replaced player ID')
    libero_exit_parser.add_argument('--position', type=int, help='Position number')
    
    # Export state command
    export_parser = subparsers.add_parser('export-state', help='Export lineup state to JSON')
    export_parser.add_argument('--team-id', type=int, required=True)
    export_parser.add_argument('--filename', help='Output filename')
    
    # Show state command
    show_parser = subparsers.add_parser('show-state', help='Show current lineup state')
    show_parser.add_argument('--team-id', type=int, required=True)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Initialize database
    db = VideoStatsDB(db_path=args.db)
    db.initialize_database()
    db.connect()
    
    manager = LineupManager(db)
    
    try:
        # Route to command handler
        handlers = {
            'init': cmd_init,
            'rotate': cmd_rotate,
            'set-server': cmd_set_server,
            'sub': cmd_sub,
            'libero-enter': cmd_libero_enter,
            'libero-exit': cmd_libero_exit,
            'export-state': cmd_export_state,
            'show-state': cmd_show_state,
        }
        
        handler = handlers.get(args.command)
        if not handler:
            print(f"Unknown command: {args.command}")
            return 1
        
        return handler(args, db, manager)
    
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())

