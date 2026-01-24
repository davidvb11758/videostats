"""
Setup script to initialize a new game using game_1d=37 as a template.
This script copies players, starting positions, libero status, serving team, etc.
"""

import sys
import json
from dbstuff.database import VideoStatsDB
from lineup_manager import LineupManager
from lineup_models import DEFAULT_ROTATION_ORDER


def setup_new_game_from_template(template_game_id: int = 37):
    """
    Initialize a new game using an existing game as a template.
    
    Args:
        template_game_id: The game ID to use as a template (default: 37)
    
    Returns:
        The new game_id
    """
    db = VideoStatsDB()
    db.connect()
    cursor = db.conn.cursor()
    
    try:
        # 1. Get template game information
        print(f"Reading template game {template_game_id}...")
        game_row = db.games.get_game_full_details(template_game_id)
        if not game_row:
            raise ValueError(f"Template game {template_game_id} not found")
        
        template_team_us_id = game_row['team_us_id']
        template_team_them_id = game_row['team_them_id']
        template_notes = game_row['notes']
        template_video_path = game_row['video_file_path']
        template_still_image_path = game_row['still_image_path']
        # Extract court boundary data as tuple
        template_court_data = (
            game_row['court_corner_tl_x'], game_row['court_corner_tl_y'],
            game_row['court_corner_tr_x'], game_row['court_corner_tr_y'],
            game_row['court_corner_bl_x'], game_row['court_corner_bl_y'],
            game_row['court_corner_br_x'], game_row['court_corner_br_y'],
            game_row['court_centerline_top_x'], game_row['court_centerline_top_y'],
            game_row['court_centerline_bottom_x'], game_row['court_centerline_bottom_y'],
            game_row['court_y200_left_x'], game_row['court_y200_left_y'],
            game_row['court_y200_right_x'], game_row['court_y200_right_y'],
            game_row['court_y400_left_x'], game_row['court_y400_left_y'],
            game_row['court_y400_right_x'], game_row['court_y400_right_y'],
            game_row['homography_matrix']
        )
        
        print(f"  Template teams: us={template_team_us_id}, them={template_team_them_id}")
        
        # 2. Get active lineup from template game
        lineup_rows = db.lineup.get_lineup_with_roles(template_game_id, template_team_us_id)
        if len(lineup_rows) != 6:
            raise ValueError(f"Template game must have exactly 6 players in lineup, found {len(lineup_rows)}")
        
        # Build lineup list: [(position, player_id), ...]
        template_lineup = [(row['position_number'], row['player_id']) for row in lineup_rows]
        template_roles = {row['position_number']: row['role_code'] for row in lineup_rows}
        template_is_server = {row['position_number']: bool(row['is_server']) for row in lineup_rows}
        
        print(f"  Template lineup: {template_lineup}")
        
        # 3. Get rotation state from template game
        rotation_row = db.rotation.get_rotation_state(template_game_id, template_team_us_id)
        if not rotation_row:
            # Rotation state doesn't exist - create defaults from active lineup
            print(f"  WARNING: Template game has no rotation_state, creating defaults from lineup...")
            # Determine serving status from is_server flag in active_lineup (position 1)
            template_serving = template_is_server.get(1, False)
            # Use default rotation order
            template_rotation_order = json.dumps(DEFAULT_ROTATION_ORDER)
            template_rotation_index = 0  # Default to rotation index 0
            template_term_of_service_start = None  # No term of service start
            print(f"  Created default rotation state: index={template_rotation_index}, serving={template_serving}")
        else:
            template_rotation_order = rotation_row['rotation_order']
            template_rotation_index = rotation_row['rotation_index']
            template_serving = bool(rotation_row['serving'])
            template_term_of_service_start = rotation_row['term_of_service_start']
            print(f"  Template rotation: index={template_rotation_index}, serving={template_serving}")
        
        # 4. Get game_players from template (all players in the game)
        template_game_players = db.game_players.get_all_game_players(template_game_id)
        print(f"  Template game_players: {len(template_game_players)} players")
        
        # 4a. Get libero_actions from template game
        template_libero_actions = db.substitutions.get_libero_actions(template_game_id)
        print(f"  Template libero_actions: {len(template_libero_actions)} actions")
        
        # 5. Create new game
        print(f"\nCreating new game...")
        new_game_id = db.games.start_game(template_team_us_id, template_team_them_id, template_notes)
        print(f"  New game_id: {new_game_id}")
        
        # 6. Copy court boundaries and video paths if they exist
        if any(template_court_data):
            print(f"  Copying court boundaries and video paths...")
            db.games.update_game_court_and_video(new_game_id, template_video_path, 
                                                  template_still_image_path, template_court_data)
        
        # 7. Copy game_players
        print(f"  Copying game_players...")
        for player in template_game_players:
            db.game_players.add_player_to_game(new_game_id, player['team_id'], player['player_id'])
        print(f"    Added {len(template_game_players)} players to game")
        
        # 8. Initialize lineup using LineupManager
        print(f"  Initializing lineup...")
        lineup_manager = LineupManager(db)
        lineup_manager.initialize_game(new_game_id, template_team_us_id, template_lineup, serving=template_serving)
        
        # 9. Update role_codes in active_lineup to match template
        print(f"  Updating role_codes...")
        for position, role_code in template_roles.items():
            if role_code:
                db.lineup.update_lineup_position(new_game_id, template_team_us_id, position, 
                                                  role_code=role_code)
        
        # 10. Update is_server flags to match template
        print(f"  Updating server flags...")
        for position, is_server in template_is_server.items():
            db.lineup.update_lineup_server_flag(new_game_id, template_team_us_id, position, is_server)
        
        # 11. Update rotation_state to match template exactly
        print(f"  Updating rotation_state...")
        db.rotation.update_rotation_state_full(new_game_id, template_team_us_id, 
                                                template_rotation_order, template_rotation_index, 
                                                template_term_of_service_start)
        
        # 12. Copy libero_actions from template game
        if template_libero_actions:
            print(f"  Copying libero_actions...")
            for action in template_libero_actions:
                db.substitutions.add_libero_action(
                    new_game_id, action['team_id'], action['libero_id'],
                    action['replaced_player_id'], action['replaced_position'],
                    action['action'], action['created_at']
                )
            print(f"    Copied {len(template_libero_actions)} libero actions")
        else:
            print(f"  No libero_actions to copy from template")
        
        print(f"\n✓ New game {new_game_id} initialized successfully!")
        print(f"  Template: game {template_game_id}")
        print(f"  Teams: us={template_team_us_id}, them={template_team_them_id}")
        print(f"  Serving: {template_serving}")
        print(f"  Rotation index: {template_rotation_index}")
        
        return new_game_id
        
    except Exception as e:
        db.conn.rollback()
        print(f"\n✗ Error setting up new game: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    template_id = 37
    if len(sys.argv) > 1:
        try:
            template_id = int(sys.argv[1])
        except ValueError:
            print(f"Invalid template game ID: {sys.argv[1]}")
            print(f"Usage: python setup_new_game.py [template_game_id]")
            print(f"Default: template_game_id = 37")
            sys.exit(1)
    
    try:
        new_game_id = setup_new_game_from_template(template_id)
        print(f"\nSetup complete! New game_id: {new_game_id}")
        sys.exit(0)
    except Exception as e:
        print(f"\nSetup failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)



