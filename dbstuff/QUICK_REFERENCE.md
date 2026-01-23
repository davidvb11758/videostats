# Database Query Quick Reference

## Setup

```python
from database import VideoStatsDB

db = VideoStatsDB()
db.connect()
```

## Common Queries

### Teams

```python
# Create
team_id = db.teams.add_team("Team Name")

# Read
all_teams = db.teams.get_all_teams()
team = db.teams.get_team_by_id(team_id)
team_name = db.teams.get_team_name(team_id)
```

### Players

```python
# Create
player_id = db.players.add_player(team_id, "10", "Player Name")

# Read
player = db.players.get_player_by_id(player_id)
player = db.players.get_player_by_number(team_id, "10")
all_players = db.players.get_players_by_team(team_id)
liberos = db.players.get_liberos_by_team(team_id)

# Update
db.players.update_player_role(player_id, "OH")
db.players.update_player_active_status(player_id, True)
```

### Games

```python
# Create
game_id = db.games.start_game(team_us_id, team_them_id, notes="Game notes")

# Read
game = db.games.get_game_by_id(game_id)
team_us_id, team_them_id = db.games.get_game_teams(game_id)
all_games = db.games.get_all_games()
team_games = db.games.get_all_games(team_id=team_id)

# Update
db.games.update_game_video_path(game_id, "/path/to/video.mp4")
db.games.mark_game_ended(game_id)

# Delete
deleted = db.games.delete_game(game_id)  # Returns count dict
```

### Game Roster (game_players)

```python
# Add player to game
db.game_players.add_player_to_game(game_id, team_id, player_id, "OH")

# Get roster
players = db.game_players.get_game_players(game_id, team_id)
player = db.game_players.get_player_by_number_for_game(game_id, team_id, "10")

# Remove
db.game_players.remove_player_from_game(game_id, team_id, player_id)
```

### Rallies

```python
# Create
rally_id = db.rallies.start_rally(game_id, rally_number=1, serving_team_id=team_id)

# Read
rally = db.rallies.get_rally_by_id(rally_id)
rallies = db.rallies.get_rallies_by_game(game_id)
completed = db.rallies.get_rallies_by_game(game_id, completed_only=True)
max_number = db.rallies.get_max_rally_number(game_id)

# Update
db.rallies.end_rally(rally_id, point_winner_id=team_id)
db.rallies.unend_rally(rally_id)

# Delete
db.rallies.delete_rally(rally_id)
```

### Contacts

```python
# Create
contact_id = db.contacts.add_contact(
    rally_id=rally_id,
    sequence_number=1,
    contact_type='serve',
    team_id=team_id,
    player_id=player_id,
    x=100, y=200,
    timecode=5000,
    outcome='continue',
    rating=3
)

# Read
contact = db.contacts.get_contact_by_id(contact_id)
contacts = db.contacts.get_rally_contacts(rally_id)
contacts = db.contacts.get_rally_contacts(rally_id, exclude_down=True)
last = db.contacts.get_last_contact(rally_id)
next_seq = db.contacts.get_current_rally_sequence(rally_id)

# Update
db.contacts.update_contact_outcome(contact_id, 'ace')
db.contacts.update_contact_position(rally_id, sequence_number, x=150, y=250)

# Delete
db.contacts.delete_contact(contact_id)
```

### Active Lineup

```python
# Set position
db.lineup.set_lineup_position(
    game_id, team_id, 
    position_number=1, 
    player_id=player_id, 
    role_code='OH',
    is_server=True
)

# Get lineup
lineup = db.lineup.get_active_lineup(game_id, team_id)
player = db.lineup.get_player_at_position(game_id, team_id, position_number=1)
server_pos = db.lineup.get_server_position(game_id, team_id)

# Update
db.lineup.set_server(game_id, team_id, position_number=1)
db.lineup.clear_lineup(game_id, team_id)
```

### Rotation

```python
# Set rotation
db.rotation.set_rotation_state(
    team_id, game_id,
    rotation_order=[1,6,5,4,3,2],
    rotation_index=0,
    serving=True
)

# Get rotation
rotation = db.rotation.get_rotation_state(game_id, team_id)

# Update
db.rotation.update_rotation_index(game_id, team_id, rotation_index=1)
db.rotation.set_serving_team(game_id, team_id, serving=True)
```

### Substitutions & Libero

```python
# Substitution
sub_id = db.substitutions.add_substitution(
    team_id, 
    out_player_id=1, 
    in_player_id=2,
    game_id=game_id
)
subs = db.substitutions.get_substitutions_for_game(game_id)

# Libero
action_id = db.substitutions.add_libero_action(
    team_id,
    libero_id=3,
    replaced_player_id=4,
    replaced_position=5,
    action='enter',
    game_id=game_id
)
libero_actions = db.substitutions.get_libero_actions_for_game(game_id, team_id)
```

### Events

```python
# Log event
event_id = db.events.log_event(
    game_id, team_id, 
    'rotation', 
    {'action': 'rotate_clockwise', 'from_index': 0, 'to_index': 1}
)

# Get events
events = db.events.get_events_for_game(game_id)
events = db.events.get_events_for_game(game_id, exclude_initial_setup=True)
initial = db.events.get_initial_setup_event(game_id, team_id)
```

### Player Stats

```python
# Update stats
db.stats.upsert_player_stats(game_id, player_id, {
    'serve_attempts': 10,
    'serve_aces': 3,
    'serve_errors': 1,
    'attack_attempts': 15,
    'attack_kills': 8
})

# Get stats
stats = db.stats.get_player_stats(game_id, player_id)
all_stats = db.stats.get_all_player_stats_for_game(game_id)
team_stats = db.stats.get_team_player_stats(game_id, team_id)
```

### Collections

```python
# Create collection
collection_id = db.collections.create_collection("Best Serves", "Top serving highlights")

# Add clips
db.collections.add_clip_to_collection(collection_id, contact_id, game_id, order_index=1)
clips = db.collections.get_collection_clips(collection_id)

# Star ratings
db.collections.set_clip_star_rating(contact_id, game_id, star_rating=5)
rating = db.collections.get_clip_star_rating(contact_id, game_id)
```

## Pattern Summary

All queries follow this pattern:

```python
db.{domain}.{action}_{object}({parameters})
```

Examples:
- `db.teams.add_team(name)` - Add a team
- `db.players.get_player_by_id(id)` - Get a player
- `db.games.update_game_video_path(id, path)` - Update game
- `db.contacts.delete_contact(id)` - Delete contact

## Return Types

- **Create operations** return the new ID (int)
- **Get single** operations return dict or None
- **Get multiple** operations return List[dict]
- **Update operations** return None (commit automatically)
- **Delete operations** return bool or count

## Type Hints

All methods have type hints:

```python
def add_team(self, name: str) -> int:
def get_team_by_id(self, team_id: int) -> Optional[dict]:
def get_all_teams(self) -> List[tuple]:
```

Use IDE autocomplete to see parameter types and return values!
