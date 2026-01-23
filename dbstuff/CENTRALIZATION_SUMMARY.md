# Database Query Centralization - Summary

## What Was Done

All database queries have been **centralized** into a new folder structure: `database/queries/`

### Files Created

**Query Module Files (12 files):**
1. `database/queries/__init__.py` - Exports all query classes
2. `database/queries/teams.py` - Team operations
3. `database/queries/players.py` - Player operations  
4. `database/queries/games.py` - Game operations
5. `database/queries/rallies.py` - Rally operations
6. `database/queries/contacts.py` - Contact operations
7. `database/queries/game_players.py` - Game roster operations
8. `database/queries/lineup.py` - Active lineup operations
9. `database/queries/rotation.py` - Rotation state operations
10. `database/queries/substitutions.py` - Substitution & libero operations
11. `database/queries/events.py` - Event logging operations
12. `database/queries/stats.py` - Player statistics operations
13. `database/queries/collections.py` - Clip collection operations

**Documentation Files (2 files):**
- `database/QUERY_REFACTORING.md` - Complete usage guide and migration instructions
- `database/CENTRALIZATION_SUMMARY.md` - This file

### Changes to database.py

1. **Added imports** for all query classes
2. **Added properties** for lazy-loading query class instances:
   - `db.teams` → TeamQueries
   - `db.players` → PlayerQueries
   - `db.games` → GameQueries
   - `db.rallies` → RallyQueries
   - `db.contacts` → ContactQueries
   - `db.game_players` → GamePlayerQueries
   - `db.lineup` → LineupQueries
   - `db.rotation` → RotationQueries
   - `db.substitutions` → SubstitutionQueries
   - `db.events` → EventQueries
   - `db.stats` → StatsQueries
   - `db.collections` → CollectionQueries

3. **Maintained backward compatibility** - All existing methods still work

## How to Use

### New Pattern (Recommended)

```python
db = VideoStatsDB()
db.connect()

# Access queries through domain properties
team_id = db.teams.add_team("Rockets")
player_id = db.players.add_player(team_id, "10", "John Doe")
game_id = db.games.start_game(team_us_id, team_them_id)
rally_id = db.rallies.start_rally(game_id, 1, team_us_id)
contact_id = db.contacts.add_contact(rally_id, 1, 'serve', team_id, player_id)
```

### Old Pattern (Still Works)

```python
db = VideoStatsDB()
db.connect()

# These existing calls still work
team_id = db.add_team("Rockets")
player_id = db.add_player(team_id, "10", "John Doe")
game_id = db.start_game(team_us_id, team_them_id)
```

## Benefits

✅ **Centralized** - All queries in one location
✅ **Organized** - Grouped by domain/table
✅ **Discoverable** - IDE autocomplete shows all available methods
✅ **Maintainable** - Easy to find and modify queries
✅ **Reusable** - No duplicate queries scattered across files
✅ **Testable** - Each query class can be tested independently
✅ **Backward Compatible** - Existing code continues to work

## Migration Strategy

**Phase 1: No Breaking Changes (Current)**
- All existing code works as-is
- Query classes are available for new code
- Old methods delegate to query classes

**Phase 2: Gradual Migration (Recommended)**
- As you work on files, migrate to new pattern
- Use `db.{domain}.{method}()` instead of direct SQL
- Remove inline cursor.execute() calls

**Phase 3: Complete Migration (Future)**
- All code uses query classes
- Consider deprecating old methods
- Full separation of concerns

## Next Steps

1. **Read** `database/QUERY_REFACTORING.md` for detailed usage examples
2. **Try** using the new pattern in your next feature/bugfix
3. **Migrate** files gradually as you work on them
4. **Add** new queries to appropriate query classes

## Statistics

- **Query files created**: 13
- **Query classes**: 12
- **Approximate methods**: 100+
- **Files affected**: 20+ application files now have centralized queries available
- **Backward compatibility**: 100% - no breaking changes

## File Locations

```
database/
├── queries/                    # NEW: All query classes
│   ├── __init__.py
│   ├── teams.py
│   ├── players.py
│   ├── games.py
│   ├── rallies.py
│   ├── contacts.py
│   ├── game_players.py
│   ├── lineup.py
│   ├── rotation.py
│   ├── substitutions.py
│   ├── events.py
│   ├── stats.py
│   └── collections.py
├── migrations/
│   └── 01_postgres_schema.sql
├── QUERY_REFACTORING.md       # NEW: Usage guide
└── CENTRALIZATION_SUMMARY.md  # NEW: This file
```

## Example: Before & After

### Before (Scattered queries in application files)

```python
# In data_entry.py
cursor = db.conn.cursor()
cursor.execute(
    """SELECT p.* FROM players p
       INNER JOIN game_players gp ON p.player_id = gp.player_id
       WHERE gp.game_id = %s AND gp.team_id = %s""",
    (game_id, team_id)
)
players = cursor.fetchall()

# In create_game_dialog.py (same query again!)
cursor = db.conn.cursor()
cursor.execute(
    """SELECT p.* FROM players p
       INNER JOIN game_players gp ON p.player_id = gp.player_id
       WHERE gp.game_id = %s AND gp.team_id = %s""",
    (game_id, team_id)
)
players = cursor.fetchall()
```

### After (Centralized, reusable)

```python
# In both files, now just:
players = db.game_players.get_game_players(game_id, team_id)
```

**Query defined once** in `database/queries/game_players.py`, **used everywhere**.

---

## Questions?

See `database/QUERY_REFACTORING.md` for:
- Complete API reference
- Migration examples
- How to add new queries
- Type hints and documentation
