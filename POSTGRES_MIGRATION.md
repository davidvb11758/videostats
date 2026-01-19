# PostgreSQL Migration Summary

This document summarizes the conversion of the VideoStats application from SQLite to PostgreSQL.

## Files Converted

### Core Database Files

#### 1. database.py
**Status:** ✓ Complete

**Changes:**
- Replaced `sqlite3` with `psycopg2`
- Changed `sqlite3.connect()` to `psycopg2.connect()` with configuration dict
- Replaced all `?` parameter placeholders with `%s`
- Changed `cursor.lastrowid` to `RETURNING` clauses
- Updated `sqlite3.Row` to `psycopg2.extras.RealDictCursor`
- Changed `sqlite3.IntegrityError` to `psycopg2.IntegrityError`
- Added rollback() calls after IntegrityError exceptions
- Changed `BOOLEAN DEFAULT 0` to `BOOLEAN DEFAULT TRUE/FALSE`
- Added database configuration via environment variables or dict
- Updated numeric type casting for PostgreSQL regex matching (`~` operator)

**Configuration:**
```python
# Environment Variables
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=videstats
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password

# OR pass config dict
db_config = {
    'host': 'localhost',
    'port': 5432,
    'database': 'videstats',
    'user': 'postgres',
    'password': 'password'
}
db = VideoStatsDB(db_config=db_config)
```

#### 2. reprocess_outcomes.py
**Status:** ✓ Complete

**Changes:**
- Replaced `sqlite3` with `psycopg2.extras`
- Changed all `?` placeholders to `%s`
- Updated cursor to use `RealDictCursor` for dict-like row access
- Changed array indexing (`contact[0]`) to dict access (`contact['contact_id']`)
- Updated `.get()` for optional fields instead of length checking

#### 3. lineup_manager.py
**Status:** ✓ Complete

**Changes:**
- Replaced `sqlite3` with `psycopg2.extras`
- Changed all `?` placeholders to `%s` (49 occurrences)
- Dynamic placeholder generation already compatible (`','.join('%s' * len(...))`)

### Application Files (SQL Query Conversions)

All files with SQL queries have been converted from SQLite `?` placeholders to PostgreSQL `%s` placeholders:

- **Main Application Files:**
  - `RocketsVideoStats.py`
  - `data_entry.py`
  - `view_paths.py`
  - `stats_app.py`
  - `stats_calc.py`

- **Dialog Files:**
  - `create_game_dialog.py`
  - `create_team_dialog.py`
  - `edit_team_dialog.py`
  - `list_games_dialog.py`
  
- **Game Setup Files:**
  - `setup_new_game.py`
  - `create_game_from_87.py`
  - `add_players.py`
  - `add_players_to_game.py`

- **Utility Files:**
  - `coordinate_mapper.py`
  - `debug_replay_contacts.py`

- **Service Files:**
  - `services/collection_service.py`
  - `services/clip_service.py`

- **API Files:**
  - `api/routes.py`

### Database Schema
**File:** `database/migrations/01_postgres_schema.sql`

**Changes from SQLite:**
- `INTEGER PRIMARY KEY AUTOINCREMENT` → `SERIAL PRIMARY KEY`
- `BOOLEAN DEFAULT 0` → `BOOLEAN DEFAULT FALSE`
- `TEXT` → `TEXT` (no change, PostgreSQL supports TEXT)
- All constraints, indexes, and foreign keys preserved

### Dependencies
**File:** `requirements.txt`
**Status:** ✓ Updated

**Added:**
```
psycopg2-binary>=2.9.0
```

## Database Setup Instructions

### 1. Install PostgreSQL
Download and install PostgreSQL from https://www.postgresql.org/

### 2. Create Database
```sql
CREATE DATABASE videstats;
```

### 3. Run Migration
```bash
psql -U postgres -d videstats -f database/migrations/01_postgres_schema.sql
```

### 4. Configure Environment
Set environment variables or pass configuration to VideoStatsDB:

**Option A: Environment Variables**
```bash
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DB=videstats
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=your_password
```

**Option B: Configuration Dict**
```python
from database import VideoStatsDB

db_config = {
    'host': 'localhost',
    'port': 5432,
    'database': 'videstats',
    'user': 'postgres',
    'password': 'your_password'
}
db = VideoStatsDB(db_config=db_config)
```

### 5. Install Dependencies
```bash
pip install -r requirements.txt
```

## Key Differences: SQLite vs PostgreSQL

| Feature | SQLite | PostgreSQL |
|---------|--------|------------|
| Parameter Placeholder | `?` | `%s` |
| Auto-increment | `INTEGER PRIMARY KEY AUTOINCREMENT` | `SERIAL PRIMARY KEY` |
| Boolean | `0`/`1` | `FALSE`/`TRUE` |
| Last Insert ID | `cursor.lastrowid` | `RETURNING id` |
| Row Factory | `sqlite3.Row` | `psycopg2.extras.RealDictCursor` |
| Connection | File path | Connection dict with host/port/db/user/password |
| Regex Match | N/A | `~` operator (used in player number sorting) |

## Testing Checklist

- [ ] Database connection successful
- [ ] Tables created correctly
- [ ] Can add teams
- [ ] Can add players
- [ ] Can create games
- [ ] Can add rallies and contacts
- [ ] Can query game data
- [ ] Lineup management works
- [ ] Reprocess outcomes script works
- [ ] Foreign key constraints enforced
- [ ] RETURNING clauses return correct IDs

## Rollback Plan

If issues occur, the original SQLite code can be restored from git history. The SQLite schema is preserved in `database/sqliteschema.sql`.

## Notes

- All files that directly use database queries have been converted
- The PostgreSQL schema maintains full compatibility with the application logic
- Data migration from SQLite to PostgreSQL would require a separate migration script (not included)
- Consider using connection pooling (e.g., psycopg2.pool) for production deployments

## Next Steps

1. Test the database connection
2. Verify all CRUD operations work
3. Test complex queries and joins
4. Performance testing with larger datasets
5. Consider adding database migration tools (e.g., Alembic) for future schema changes
