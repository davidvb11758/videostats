"""
Script to create a new game with the exact same setup/initialization values as game_id=87.
Use this to prepare a fresh/clean game for testing.
"""

import sys
import json
from database import VideoStatsDB
from lineup_manager import LineupManager
from lineup_models import DEFAULT_ROTATION_ORDER


def create_game_from_87():
    """
    Create a new game using game_id=87 as a template.
    Copies all setup/initialization values including:
    - Teams
    - Notes
    - Video paths and court boundaries
    - Scroll offsets and video offsets
    - Video and scene dimensions
    - Starting lineup
    - Rotation state
    - Game players
    - Libero actions
    
    Returns:
        The new game_id
    """
    template_game_id = 87
    db = VideoStatsDB()
    db.connect()
    cursor = db.conn.cursor()
    
    try:
        # 1. Get template game information
        print(f"Reading template game {template_game_id}...")
        cursor.execute("""
            SELECT game_id, team_us_id, team_them_id, notes,
                   video_file_path, still_image_path,
                   court_corner_tl_x, court_corner_tl_y,
                   court_corner_tr_x, court_corner_tr_y,
                   court_corner_bl_x, court_corner_bl_y,
                   court_corner_br_x, court_corner_br_y,
                   court_centerline_top_x, court_centerline_top_y,
                   court_centerline_bottom_x, court_centerline_bottom_y,
                   court_y200_left_x, court_y200_left_y,
                   court_y200_right_x, court_y200_right_y,
                   court_y400_left_x, court_y400_left_y,
                   court_y400_right_x, court_y400_right_y,
                   homography_matrix,
                   scroll_offset_x, scroll_offset_y,
                   video_offset_x, video_offset_y,
                   video_width, video_height,
                   scene_width, scene_height
            FROM games
            WHERE game_id = ?
        """, (template_game_id,))
        
        game_row = cursor.fetchone()
        if not game_row:
            raise ValueError(f"Template game {template_game_id} not found")
        
        template_team_us_id = game_row[1]
        template_team_them_id = game_row[2]
        template_notes = game_row[3]
        template_video_path = game_row[4]
        template_still_image_path = game_row[5]
        template_court_data = game_row[6:27]  # Court boundary data (indices 6-26, includes homography_matrix)
        template_scroll_offset_x = game_row[27] if len(game_row) > 27 else None
        template_scroll_offset_y = game_row[28] if len(game_row) > 28 else None
        template_video_offset_x = game_row[29] if len(game_row) > 29 else None
        template_video_offset_y = game_row[30] if len(game_row) > 30 else None
        template_video_width = game_row[31] if len(game_row) > 31 else None
        template_video_height = game_row[32] if len(game_row) > 32 else None
        template_scene_width = game_row[33] if len(game_row) > 33 else None
        template_scene_height = game_row[34] if len(game_row) > 34 else None
        
        print(f"  Template teams: us={template_team_us_id}, them={template_team_them_id}")
        
        # 2. Get active lineup from template game
        cursor.execute("""
            SELECT position_number, player_id, role_code, is_server
            FROM active_lineup
            WHERE game_id = ? AND team_id = ?
            ORDER BY position_number
        """, (template_game_id, template_team_us_id))
        
        lineup_rows = cursor.fetchall()
        if len(lineup_rows) != 6:
            raise ValueError(f"Template game must have exactly 6 players in lineup, found {len(lineup_rows)}")
        
        # Build lineup list: [(position, player_id), ...]
        template_lineup = [(row[0], row[1]) for row in lineup_rows]
        template_roles = {row[0]: row[2] for row in lineup_rows}
        template_is_server = {row[0]: bool(row[3]) for row in lineup_rows}
        
        print(f"  Template lineup: {template_lineup}")
        
        # 3. Get rotation state from template game
        cursor.execute("""
            SELECT rotation_order, rotation_index, serving, term_of_service_start
            FROM rotation_state
            WHERE game_id = ? AND team_id = ?
        """, (template_game_id, template_team_us_id))
        
        rotation_row = cursor.fetchone()
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
            template_rotation_order = rotation_row[0]
            template_rotation_index = rotation_row[1]
            template_serving = bool(rotation_row[2])
            template_term_of_service_start = rotation_row[3]
            print(f"  Template rotation: index={template_rotation_index}, serving={template_serving}")
        
        # 4. Get game_players from template (all players in the game)
        cursor.execute("""
            SELECT team_id, player_id, game_role_code
            FROM game_players
            WHERE game_id = ?
            ORDER BY team_id, player_id
        """, (template_game_id,))
        
        template_game_players = cursor.fetchall()
        print(f"  Template game_players: {len(template_game_players)} players")
        
        # 4a. Get libero_actions from template game
        cursor.execute("""
            SELECT team_id, libero_id, replaced_player_id, replaced_position, action, created_at
            FROM libero_actions
            WHERE game_id = ?
            ORDER BY created_at
        """, (template_game_id,))
        
        template_libero_actions = cursor.fetchall()
        print(f"  Template libero_actions: {len(template_libero_actions)} actions")
        
        # 5. Create new game
        print(f"\nCreating new game...")
        new_game_id = db.start_game(template_team_us_id, template_team_them_id, template_notes)
        print(f"  New game_id: {new_game_id}")
        
        # 6. Copy court boundaries, video paths, offsets, and dimensions
        print(f"  Copying court boundaries, video paths, offsets, and dimensions...")
        cursor.execute("""
            UPDATE games SET
                video_file_path = ?,
                still_image_path = ?,
                court_corner_tl_x = ?, court_corner_tl_y = ?,
                court_corner_tr_x = ?, court_corner_tr_y = ?,
                court_corner_bl_x = ?, court_corner_bl_y = ?,
                court_corner_br_x = ?, court_corner_br_y = ?,
                court_centerline_top_x = ?, court_centerline_top_y = ?,
                court_centerline_bottom_x = ?, court_centerline_bottom_y = ?,
                court_y200_left_x = ?, court_y200_left_y = ?,
                court_y200_right_x = ?, court_y200_right_y = ?,
                court_y400_left_x = ?, court_y400_left_y = ?,
                court_y400_right_x = ?, court_y400_right_y = ?,
                homography_matrix = ?,
                scroll_offset_x = ?,
                scroll_offset_y = ?,
                video_offset_x = ?,
                video_offset_y = ?,
                video_width = ?,
                video_height = ?,
                scene_width = ?,
                scene_height = ?
            WHERE game_id = ?
        """, (template_video_path, template_still_image_path) + tuple(template_court_data) + (
            template_scroll_offset_x, template_scroll_offset_y,
            template_video_offset_x, template_video_offset_y,
            template_video_width, template_video_height,
            template_scene_width, template_scene_height,
            new_game_id
        ))
        db.conn.commit()
        
        # 7. Copy game_players (including game_role_code)
        print(f"  Copying game_players...")
        for team_id, player_id, game_role_code in template_game_players:
            db.add_player_to_game(new_game_id, team_id, player_id, game_role_code)
        print(f"    Added {len(template_game_players)} players to game")
        
        # 8. Initialize lineup using LineupManager
        print(f"  Initializing lineup...")
        lineup_manager = LineupManager(db)
        lineup_manager.initialize_game(new_game_id, template_team_us_id, template_lineup, serving=template_serving)
        
        # 9. Update role_codes in active_lineup to match template
        print(f"  Updating role_codes...")
        for position, role_code in template_roles.items():
            if role_code:
                cursor.execute("""
                    UPDATE active_lineup
                    SET role_code = ?
                    WHERE game_id = ? AND team_id = ? AND position_number = ?
                """, (role_code, new_game_id, template_team_us_id, position))
        
        # 10. Update is_server flags to match template
        print(f"  Updating server flags...")
        for position, is_server in template_is_server.items():
            cursor.execute("""
                UPDATE active_lineup
                SET is_server = ?
                WHERE game_id = ? AND team_id = ? AND position_number = ?
            """, (1 if is_server else 0, new_game_id, template_team_us_id, position))
        
        # 11. Update rotation_state to match template exactly
        print(f"  Updating rotation_state...")
        cursor.execute("""
            UPDATE rotation_state
            SET rotation_order = ?, rotation_index = ?, term_of_service_start = ?
            WHERE game_id = ? AND team_id = ?
        """, (template_rotation_order, template_rotation_index, template_term_of_service_start, 
              new_game_id, template_team_us_id))
        
        db.conn.commit()
        
        # 12. Copy libero_actions from template game
        if template_libero_actions:
            print(f"  Copying libero_actions...")
            for team_id, libero_id, replaced_player_id, replaced_position, action, created_at in template_libero_actions:
                cursor.execute("""
                    INSERT INTO libero_actions 
                    (game_id, team_id, libero_id, replaced_player_id, replaced_position, action, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (new_game_id, team_id, libero_id, replaced_player_id, replaced_position, action, created_at))
            db.conn.commit()
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
    try:
        new_game_id = create_game_from_87()
        print(f"\nSetup complete! New game_id: {new_game_id}")
        sys.exit(0)
    except Exception as e:
        print(f"\nSetup failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

