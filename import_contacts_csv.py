"""
Script to import contacts from CSV file into the database.
Usage: python import_contacts_csv.py <csv_file_path>
"""

import sys
import csv
from database import VideoStatsDB


def import_contacts_from_csv(db: VideoStatsDB, csv_file_path: str):
    """Import contacts from CSV file into the database.
    
    CSV format should have columns:
    rally_id, sequence_number, player_id, contact_type, team_id, x, y, timecode, outcome, rating
    
    Note: player_id, x, y, timecode, outcome, and rating can be empty/NULL
    """
    if not db.conn:
        db.connect()
    
    cursor = db.conn.cursor()
    
    imported_count = 0
    error_count = 0
    
    with open(csv_file_path, 'r', newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        
        for row_num, row in enumerate(reader, start=2):  # Start at 2 (row 1 is header)
            try:
                # Parse required fields
                rally_id = int(row['rally_id'])
                sequence_number = int(row['sequence_number'])
                contact_type = row['contact_type'].strip()
                team_id = int(row['team_id'])
                
                # Parse optional fields (can be empty)
                player_id = int(row['player_id']) if row.get('player_id', '').strip() else None
                x = int(row['x']) if row.get('x', '').strip() else None
                y = int(row['y']) if row.get('y', '').strip() else None
                timecode = int(row['timecode']) if row.get('timecode', '').strip() else None
                outcome = row.get('outcome', 'continue').strip() or 'continue'
                rating = int(row['rating']) if row.get('rating', '').strip() else None
                
                # Insert into database
                cursor.execute("""
                    INSERT INTO contacts 
                    (rally_id, sequence_number, player_id, contact_type, team_id, x, y, timecode, outcome, rating)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (rally_id, sequence_number, player_id, contact_type, team_id, x, y, timecode, outcome, rating))
                
                imported_count += 1
                
            except ValueError as e:
                print(f"Error on row {row_num}: Invalid number format - {e}")
                error_count += 1
            except KeyError as e:
                print(f"Error on row {row_num}: Missing required column - {e}")
                error_count += 1
            except Exception as e:
                print(f"Error on row {row_num}: {e}")
                error_count += 1
    
    db.conn.commit()
    
    print(f"\nImport complete!")
    print(f"  Successfully imported: {imported_count} contacts")
    print(f"  Errors: {error_count}")
    
    return imported_count, error_count


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python import_contacts_csv.py <csv_file_path>")
        print("\nExample:")
        print("  python import_contacts_csv.py contacts_import_example.csv")
        sys.exit(1)
    
    csv_file_path = sys.argv[1]
    
    # Initialize database
    db = VideoStatsDB()
    db.connect()
    
    try:
        import_contacts_from_csv(db, csv_file_path)
    except FileNotFoundError:
        print(f"Error: File not found: {csv_file_path}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        db.close()

