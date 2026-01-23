# Supabase Connection Setup

This guide explains how to connect your VideoStats application to a Supabase PostgreSQL database.

## What is Supabase?

Supabase is a hosted PostgreSQL database service that provides:
- Fully managed PostgreSQL databases
- Connection pooling (via PgBouncer)
- Automatic backups
- Built-in authentication and APIs
- Free tier available

## Connection Methods

### Method 1: Environment Variable (Recommended)

Set the `SUPABASE_CONNECTION_STRING` environment variable:

**Windows (PowerShell):**
```powershell
$env:SUPABASE_CONNECTION_STRING = "postgresql://postgres.[project-ref]:[password]@aws-0-us-west-1.pooler.supabase.com:6543/postgres"
```

**Windows (Command Prompt):**
```cmd
set SUPABASE_CONNECTION_STRING=postgresql://postgres.[project-ref]:[password]@aws-0-us-west-1.pooler.supabase.com:6543/postgres
```

**Linux/Mac:**
```bash
export SUPABASE_CONNECTION_STRING="postgresql://postgres.[project-ref]:[password]@aws-0-us-west-1.pooler.supabase.com:6543/postgres"
```

Then run your application normally:
```python
from database import VideoStatsDB

db = VideoStatsDB()  # Automatically uses SUPABASE_CONNECTION_STRING
db.connect()
```

### Method 2: Pass Connection String Directly

```python
from database import VideoStatsDB

connection_string = "postgresql://postgres.[project-ref]:[password]@aws-0-us-west-1.pooler.supabase.com:6543/postgres"

db = VideoStatsDB(connection_string=connection_string)
db.connect()
```

### Method 3: Use DATABASE_URL (Alternative)

Supabase also works with the standard `DATABASE_URL` environment variable:

```powershell
$env:DATABASE_URL = "postgresql://postgres.[project-ref]:[password]@aws-0-us-west-1.pooler.supabase.com:6543/postgres"
```

## Getting Your Supabase Connection String

1. Go to your Supabase project dashboard: https://app.supabase.com
2. Click on your project
3. Go to **Settings** → **Database**
4. Scroll down to **Connection String**
5. Select **Connection Pooling** tab (recommended for better performance)
6. Choose **Transaction** mode
7. Copy the connection string that looks like:
   ```
   postgresql://postgres.[project-ref]:[password]@aws-0-us-west-1.pooler.supabase.com:6543/postgres
   ```
8. Replace `[password]` with your actual database password

## Connection String Format

```
postgresql://[user]:[password]@[host]:[port]/[database]?[options]
```

**Supabase Example:**
```
postgresql://postgres.abcdefghijklmnop:mySecretPassword@aws-0-us-west-1.pooler.supabase.com:6543/postgres
```

**Components:**
- `user`: Usually `postgres.[project-ref]` for Supabase
- `password`: Your database password (set during project creation)
- `host`: Supabase pooler hostname (e.g., `aws-0-us-west-1.pooler.supabase.com`)
- `port`: Usually `6543` for pooled connections, `5432` for direct connections
- `database`: Usually `postgres`

## Connection Pooling vs Direct Connection

Supabase provides two connection types:

### Connection Pooling (Port 6543) - **RECOMMENDED**
- Uses PgBouncer for connection pooling
- Better for applications with many short-lived connections
- Required for serverless/edge functions
- Mode options: Transaction (recommended), Session

### Direct Connection (Port 5432)
- Direct connection to PostgreSQL
- Use for long-running processes or when you need full PostgreSQL features
- Limited number of connections (depends on your plan)

**For VideoStats, use Connection Pooling (port 6543) in Transaction mode.**

## Setting Up Your Database Schema

After connecting, you need to run the migration to create all tables:

1. Connect to your Supabase database using the SQL Editor in the Supabase dashboard
2. Copy the contents of `database/migrations/01_postgres_schema.sql`
3. Paste and run it in the SQL Editor

Alternatively, you can use `psql`:
```bash
psql "postgresql://postgres.[project-ref]:[password]@aws-0-us-west-1.pooler.supabase.com:6543/postgres" -f database/migrations/01_postgres_schema.sql
```

## Security Best Practices

1. **Never commit connection strings to git**
   - Add `.env` files to `.gitignore`
   - Use environment variables for production

2. **Use different databases for development/production**
   - Create separate Supabase projects for dev and prod
   - Use different connection strings for each environment

3. **Rotate passwords regularly**
   - Change your database password periodically
   - Update the connection string in your environment variables

4. **Use connection pooling**
   - Always use the pooled connection (port 6543) for better performance
   - Set appropriate pool size limits in Supabase settings

## Troubleshooting

### Connection Timeout
- Check your internet connection
- Verify the connection string is correct
- Ensure your IP is not blocked (Supabase allows all IPs by default)

### Authentication Failed
- Double-check your password in the connection string
- Verify you're using the correct project reference
- Reset your database password in Supabase settings if needed

### SSL/TLS Errors
Supabase requires SSL. If you get SSL errors, add `sslmode=require` to your connection string:
```
postgresql://postgres.[project-ref]:[password]@aws-0-us-west-1.pooler.supabase.com:6543/postgres?sslmode=require
```

### Too Many Connections
- Use connection pooling (port 6543) instead of direct connections
- Close connections when done: `db.close()`
- Check your Supabase plan's connection limits

## Example: Complete Setup

```python
# Option 1: Using environment variable
import os
os.environ['SUPABASE_CONNECTION_STRING'] = "postgresql://postgres.abcdefgh:myPassword@aws-0-us-west-1.pooler.supabase.com:6543/postgres"

from database import VideoStatsDB

db = VideoStatsDB()
db.connect()

# Use the database
teams = db.teams.get_all_teams()
print(teams)

db.close()
```

```python
# Option 2: Direct connection string
from database import VideoStatsDB

db = VideoStatsDB(
    connection_string="postgresql://postgres.abcdefgh:myPassword@aws-0-us-west-1.pooler.supabase.com:6543/postgres"
)
db.connect()

# Use the database
teams = db.teams.get_all_teams()
print(teams)

db.close()
```

## Switching Between Local and Supabase

You can easily switch between local PostgreSQL and Supabase:

```python
import os
from database import VideoStatsDB

# For local development
if os.getenv('ENVIRONMENT') == 'local':
    db = VideoStatsDB(db_config={
        'host': 'localhost',
        'port': 5432,
        'database': 'videostats',
        'user': 'postgres',
        'password': 'localpassword'
    })
else:
    # For production (Supabase)
    db = VideoStatsDB()  # Uses SUPABASE_CONNECTION_STRING env var

db.connect()
```

## Next Steps

1. Set up your Supabase project
2. Get your connection string
3. Set the `SUPABASE_CONNECTION_STRING` environment variable
4. Run the schema migration
5. Test the connection
6. Start using VideoStats with Supabase!

## Support

- Supabase Documentation: https://supabase.com/docs
- Supabase Support: https://supabase.com/support
- VideoStats Issues: (your repository issues page)
