"""
Test script to verify Supabase database connection.

Usage:
    python test_supabase_connection.py "your-connection-string-here"
    
Or set environment variable first:
    $env:SUPABASE_CONNECTION_STRING = "your-connection-string-here"
    python test_supabase_connection.py
"""

import sys
import os
from dbstuff.database import VideoStatsDB

def test_connection(connection_string=None):
    """Test the Supabase database connection."""
    
    print("=" * 60)
    print("VideoStats - Supabase Connection Test")
    print("=" * 60)
    
    try:
        # Create database instance
        if connection_string:
            print(f"\n✓ Using provided connection string")
            print(f"  Host: {connection_string.split('@')[1].split(':')[0] if '@' in connection_string else 'N/A'}")
            db = VideoStatsDB(connection_string=connection_string)
        else:
            print(f"\n✓ Using SUPABASE_CONNECTION_STRING environment variable")
            env_conn = os.getenv('SUPABASE_CONNECTION_STRING') or os.getenv('DATABASE_URL')
            if not env_conn:
                print("\n✗ ERROR: No connection string provided!")
                print("\nPlease either:")
                print("  1. Pass connection string as argument:")
                print("     python test_supabase_connection.py \"postgresql://...\"")
                print("  2. Set environment variable:")
                print("     $env:SUPABASE_CONNECTION_STRING = \"postgresql://...\"")
                return False
            print(f"  Host: {env_conn.split('@')[1].split(':')[0] if '@' in env_conn else 'N/A'}")
            db = VideoStatsDB()
        
        # Test connection
        print("\n✓ Connecting to database...")
        db.connect()
        print("  ✓ Connection successful!")
        
        # Test query - get PostgreSQL version
        print("\n✓ Testing query execution...")
        cursor = db.conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"  ✓ PostgreSQL version: {version.split(',')[0]}")
        
        # Test if tables exist
        print("\n✓ Checking for VideoStats tables...")
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('teams', 'players', 'games', 'rallies', 'contacts')
            ORDER BY table_name;
        """)
        tables = cursor.fetchall()
        
        if tables:
            print(f"  ✓ Found {len(tables)} VideoStats tables:")
            for table in tables:
                print(f"    - {table[0]}")
        else:
            print("  ⚠ No VideoStats tables found!")
            print("  → You need to run the schema migration:")
            print("     See database/migrations/01_postgres_schema.sql")
        
        # Test query classes
        print("\n✓ Testing query classes...")
        try:
            teams = db.teams.get_all_teams()
            print(f"  ✓ Teams query successful - found {len(teams)} teams")
            
            games = db.games.get_all_games()
            print(f"  ✓ Games query successful - found {len(games)} games")
        except Exception as e:
            print(f"  ⚠ Query class test failed: {e}")
            print("  → Make sure you've run the schema migration")
        
        # Close connection
        print("\n✓ Closing connection...")
        db.close()
        print("  ✓ Connection closed successfully")
        
        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED!")
        print("=" * 60)
        print("\nYour Supabase connection is working correctly!")
        print("You can now use VideoStats with Supabase.\n")
        
        return True
        
    except Exception as e:
        print(f"\n✗ ERROR: {type(e).__name__}")
        print(f"  {str(e)}")
        print("\n" + "=" * 60)
        print("✗ CONNECTION TEST FAILED")
        print("=" * 60)
        
        print("\nTroubleshooting:")
        print("1. Check your connection string format:")
        print("   postgresql://user:password@host:port/database")
        print("2. Verify your password is correct")
        print("3. Ensure you're using the pooled connection (port 6543)")
        print("4. Check your internet connection")
        print("5. See database/SUPABASE_SETUP.md for detailed help\n")
        
        return False

if __name__ == "__main__":
    connection_string = os.getenv('SUPABASE_URL')
    
    success = test_connection(connection_string)
    sys.exit(0 if success else 1)
