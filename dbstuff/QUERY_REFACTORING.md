# Database Query Refactoring Guide

## Overview

All database queries have been centralized into the `database/queries/` folder, organized by table/domain. This improves code organization, maintainability, and makes it easier to find and modify queries.

## New Structure

```
database/
├── queries/
│   ├── __init__.py              # Exports all query classes
│   ├── teams.py                 # Team-related queries
│   ├── players.py               # Player-related queries
│   ├── games.py                 # Game-related queries
│   ├── rallies.py               # Rally-related queries
│   ├── contacts.py              # Contact-related queries
│   ├── game_players.py          # Game roster (game_players table)
│   ├── lineup.py                # Active lineup queries
│   ├── rotation.py              # Rotation state queries
│   ├── substitutions.py         # Substitution & libero action queries
│   ├── events.py                # Event logging queries
│   ├── stats.py                 # Player stats queries
│   └── collections.py           # Clip collection queries
```

## Usage

### New Way (Recommended)

Access query methods through the database object's properties:

```python
from database import VideoStatsDB

db = VideoStatsDB()
db.connect()

# Teams
team_id = db.teams.add_team("Rockets")
all_teams = db.teams.get_all_teams()
team = db.teams.get_team_by_id(team_id)

# Players
player_id = db.players.add_player(team_id, "10", "John Doe")
player = db.players.get_player_by_number(team_id, "10")
team_players = db.players.get_players_by_team(team_id)

# Games
game_id = db.games.start_game(team_us_id, team_them_id, notes="Important match")
game = db.games.get_game_by_id(game_id)
db.games.update_game_video_path(game_id, "/path/to/video.mp4")

# Rallies
rally_id = db.rallies.start_rally(game_id, rally_number=1, serving_team_id=team_us_id)
db.rallies.end_rally(rally_id, point_winner_id=team_us_id)
rallies = db.rallies.get_rallies_by_game(game_id)

# Contacts
contact_id = db.contacts.add_contact(
    rally_id=rally_id,
    sequence_number=1,
    contact_type='serve',
    team_id=team_us_id,
    player_id=player_id,
    x=100, y=200,
    timecode=5000
)
contacts = db.contacts.get_rally_contacts(rally_id)
db.contacts.update_contact_outcome(contact_id, 'ace')

# Game Players (roster)
db.game_players.add_player_to_game(game_id, team_id, player_id, game_role_code='OH')
roster = db.game_players.get_game_players(game_id, team_id)

# Lineup
db.lineup.set_lineup_position(game_id, team_id, position_number=1, player_id=player_id, role_code='OH')
lineup = db.lineup.get_active_lineup(game_id, team_id)
db.lineup.set_server(game_id, team_id, position_number=1)

# Rotation
db.rotation.set_rotation_state(team_id, game_id, rotation_order=[1,6,5,4,3,2], rotation_index=0, serving=True)
rotation = db.rotation.get_rotation_state(game_id, team_id)

# Substitutions
sub_id = db.substitutions.add_substitution(team_id, out_player_id=1, in_player_id=2, game_id=game_id)
subs = db.substitutions.get_substitutions_for_game(game_id)

# Libero Actions
action_id = db.substitutions.add_libero_action(team_id, libero_id=3, replaced_player_id=4, 
                                                replaced_position=5, action='enter', game_id=game_id)
libero_actions = db.substitutions.get_libero_actions_for_game(game_id, team_id)

# Events
event_id = db.events.log_event(game_id, team_id, 'rotation', {'action': 'rotate_clockwise'})
events = db.events.get_events_for_game(game_id, exclude_initial_setup=True)

# Stats
db.stats.upsert_player_stats(game_id, player_id, {
    'serve_attempts': 10,
    'serve_aces': 3,
    'serve_errors': 1
})
stats = db.stats.get_player_stats(game_id, player_id)
all_stats = db.stats.get_all_player_stats_for_game(game_id)

# Collections
collection_id = db.collections.create_collection("Best Serves", "Top serving highlights")
db.collections.add_clip_to_collection(collection_id, contact_id, game_id, order_index=1)
clips = db.collections.get_collection_clips(collection_id)
db.collections.set_clip_star_rating(contact_id, game_id, star_rating=5)
```

### Old Way (Still Supported for Backward Compatibility)

The existing methods in `database.py` still work and delegate to the query classes:

```python
db = VideoStatsDB()
db.connect()

# These still work:
team_id = db.add_team("Rockets")
player_id = db.add_player(team_id, "10", "John Doe")
game_id = db.start_game(team_us_id, team_them_id)
# ... etc
```

## Migration Guide

### For Existing Code

1. **No immediate changes required** - All existing code will continue to work
2. **Gradual migration recommended** - As you work on files, migrate to the new pattern
3. **Benefits of migrating:**
   - Better IDE autocomplete (you can see all available methods)
   - Easier to find related queries
   - Clearer code organization

### Migration Examples

#### Before:
```python
cursor = db.conn.cursor()
cursor.execute(
    "SELECT * FROM teams WHERE team_id = %s",
    (team_id,)
)
team = cursor.fetchone()
```

#### After:
```python
team = db.teams.get_team_by_id(team_id)
```

---

#### Before:
```python
cursor = db.conn.cursor()
cursor.execute(
    """SELECT p.* FROM players p
       INNER JOIN game_players gp ON p.player_id = gp.player_id
       WHERE gp.game_id = %s AND gp.team_id = %s""",
    (game_id, team_id)
)
players = cursor.fetchall()
```

#### After:
```python
players = db.game_players.get_game_players(game_id, team_id)
```

## Adding New Queries

When you need to add a new database query:

1. Identify which domain it belongs to (teams, players, games, etc.)
2. Add the method to the appropriate query class in `database/queries/`
3. Use the new method directly: `db.{domain}.{method_name}()`

Example - adding a method to get players by role:

```python
# In database/queries/players.py

def get_players_by_role(self, team_id: int, role_code: str) -> List[dict]:
    """Get all players with a specific role."""
    cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute(
        "SELECT * FROM players WHERE team_id = %s AND role_code = %s",
        (team_id, role_code)
    )
    return cursor.fetchall()
```

Then use it:
```python
setters = db.players.get_players_by_role(team_id, 'S')
```

## Benefits

1. **Centralized Queries**: All SQL queries are in one place
2. **Better Organization**: Queries grouped by domain/table
3. **Easier Maintenance**: Find and modify queries quickly
4. **Reduced Duplication**: Reusable query methods
5. **Better Testing**: Each query class can be tested independently
6. **IDE Support**: Better autocomplete and method discovery
7. **Type Safety**: Type hints on all query methods

## Query Class Reference

Each query class provides methods for CRUD operations on its respective table(s):

- **TeamQueries**: add_team, get_all_teams, get_team_by_id, get_team_name
- **PlayerQueries**: add_player, get_player_by_id, get_player_by_number, get_players_by_team, update_player_role, etc.
- **GameQueries**: start_game, get_game_by_id, update_game_video_path, save_game_court_boundaries, delete_game, etc.
- **RallyQueries**: start_rally, end_rally, get_rally_by_id, get_rallies_by_game, etc.
- **ContactQueries**: add_contact, update_contact, delete_contact, get_rally_contacts, get_last_contact, etc.
- **GamePlayerQueries**: add_player_to_game, remove_player_from_game, get_game_players, etc.
- **LineupQueries**: get_active_lineup, set_lineup_position, clear_lineup, set_server, etc.
- **RotationQueries**: get_rotation_state, set_rotation_state, update_rotation_index, etc.
- **SubstitutionQueries**: add_substitution, add_libero_action, get_substitutions_for_game, etc.
- **EventQueries**: log_event, get_events_for_game, update_event_payload, etc.
- **StatsQueries**: get_player_stats, upsert_player_stats, get_team_player_stats, etc.
- **CollectionQueries**: create_collection, add_clip_to_collection, set_clip_star_rating, etc.

See individual query class files for complete method documentation.
