"""
Contact-related database queries.
"""
import psycopg2.extras
from typing import Optional, List


class ContactQueries:
    """Handles all contact-related database operations."""
    
    def __init__(self, conn):
        """
        Initialize with database connection.
        
        Args:
            conn: psycopg2 database connection
        """
        self.conn = conn
    
    def add_contact(self, rally_id: int, sequence_number: int, contact_type: str, 
                   team_id: int, player_id: Optional[int] = None, 
                   x: Optional[int] = None, y: Optional[int] = None,
                   timecode: Optional[int] = None,
                   outcome: str = 'continue', rating: Optional[int] = None) -> int:
        """
        Add a ball contact and return contact_id.
        
        Args:
            rally_id: The rally ID
            sequence_number: The sequence number within the rally
            contact_type: Type of contact (serve, pass, set, attack, etc.)
            team_id: The team ID
            player_id: Optional player ID
            x: Optional x coordinate on the court
            y: Optional y coordinate on the court
            timecode: Optional video timecode in milliseconds
            outcome: Outcome of the contact (continue, ace, kill, error, down, stuff)
            rating: Optional rating (integer) for the contact
            
        Returns:
            contact_id of the newly created contact
        """
        # Coerce x, y to native int so numpy types never reach psycopg2
        x = int(x) if x is not None else None
        y = int(y) if y is not None else None
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO contacts (rally_id, sequence_number, contact_type, team_id, 
                                    player_id, x, y, timecode, outcome, rating)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING contact_id""",
            (rally_id, sequence_number, contact_type, team_id, player_id, x, y, 
             timecode, outcome, rating)
        )
        contact_id = cursor.fetchone()[0]
        self.conn.commit()
        return contact_id
    
    def update_contact(self, contact_id: int, player_id: Optional[int] = None,
                      contact_type: Optional[str] = None, outcome: Optional[str] = None,
                      rating: Optional[int] = None, timecode: Optional[int] = None,
                      x: Optional[int] = None, y: Optional[int] = None):
        """
        Update contact fields.
        
        Args:
            contact_id: The contact ID
            player_id: Optional new player ID
            contact_type: Optional new contact type
            outcome: Optional new outcome
            rating: Optional new rating
            timecode: Optional new timecode
            x: Optional new x coordinate
            y: Optional new y coordinate
        """
        updates = []
        params = []
        
        if player_id is not None:
            updates.append("player_id = %s")
            params.append(player_id)
        if contact_type is not None:
            updates.append("contact_type = %s")
            params.append(contact_type)
        if outcome is not None:
            updates.append("outcome = %s")
            params.append(outcome)
        if rating is not None:
            updates.append("rating = %s")
            params.append(rating)
        if timecode is not None:
            updates.append("timecode = %s")
            params.append(timecode)
        if x is not None:
            updates.append("x = %s")
            params.append(x)
        if y is not None:
            updates.append("y = %s")
            params.append(y)
        
        if updates:
            params.append(contact_id)
            cursor = self.conn.cursor()
            cursor.execute(
                f"UPDATE contacts SET {', '.join(updates)} WHERE contact_id = %s",
                tuple(params)
            )
            self.conn.commit()
    
    def update_contact_outcome(self, contact_id: int, outcome: str):
        """
        Update the outcome of a contact.
        
        Args:
            contact_id: The contact ID to update
            outcome: The outcome value (continue, ace, kill, error, down, stuff)
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE contacts SET outcome = %s WHERE contact_id = %s",
            (outcome, contact_id)
        )
        self.conn.commit()
    
    def update_contact_position(self, rally_id: int, sequence_number: int, 
                               x: int, y: int):
        """
        Update contact position coordinates.
        
        Args:
            rally_id: The rally ID
            sequence_number: The sequence number
            x: New x coordinate
            y: New y coordinate
        """
        # Coerce to native int so numpy types never reach psycopg2
        x, y = int(x), int(y)
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE contacts SET x = %s, y = %s WHERE rally_id = %s AND sequence_number = %s",
            (x, y, rally_id, sequence_number)
        )
        self.conn.commit()
    
    def delete_contact(self, contact_id: int) -> bool:
        """
        Delete a contact by ID.
        
        Args:
            contact_id: The contact ID to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM contacts WHERE contact_id = %s", (contact_id,))
            self.conn.commit()
            return cursor.rowcount > 0
        except Exception:
            return False
    
    def get_contact_by_id(self, contact_id: int) -> Optional[dict]:
        """
        Get contact by ID.
        
        Args:
            contact_id: The contact ID
            
        Returns:
            Contact record as dict or None if not found
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT * FROM contacts WHERE contact_id = %s", (contact_id,))
        return cursor.fetchone()
    
    def get_rally_contacts(self, rally_id: int, exclude_down: bool = False) -> List[dict]:
        """
        Get all contacts for a rally, ordered by sequence number.
        
        Args:
            rally_id: The rally ID
            exclude_down: If True, exclude 'down' contacts
            
        Returns:
            List of contact records
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if exclude_down:
            cursor.execute(
                """SELECT * FROM contacts 
                   WHERE rally_id = %s AND contact_type != 'down'
                   ORDER BY sequence_number""",
                (rally_id,)
            )
        else:
            cursor.execute(
                "SELECT * FROM contacts WHERE rally_id = %s ORDER BY sequence_number",
                (rally_id,)
            )
        return cursor.fetchall()
    
    def get_last_contact(self, rally_id: int) -> Optional[dict]:
        """
        Get the most recent contact in a rally.
        
        Args:
            rally_id: The rally ID
            
        Returns:
            Contact record or None if no contacts exist
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            """SELECT * FROM contacts 
               WHERE rally_id = %s
               ORDER BY sequence_number DESC
               LIMIT 1""",
            (rally_id,)
        )
        return cursor.fetchone()
    
    def get_current_rally_sequence(self, rally_id: int) -> int:
        """
        Get the next sequence number for a rally.
        
        Args:
            rally_id: The rally ID
            
        Returns:
            Next available sequence number
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT MAX(sequence_number) FROM contacts WHERE rally_id = %s",
            (rally_id,)
        )
        result = cursor.fetchone()[0]
        return (result or 0) + 1
    
    def get_contacts_by_rally_and_team(self, rally_id: int, team_id: int,
                                      exclude_down: bool = False) -> List[dict]:
        """
        Get contacts for a rally filtered by team.
        
        Args:
            rally_id: The rally ID
            team_id: The team ID
            exclude_down: If True, exclude 'down' contacts
            
        Returns:
            List of contact records
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if exclude_down:
            cursor.execute(
                """SELECT * FROM contacts 
                   WHERE rally_id = %s AND team_id = %s AND contact_type != 'down'
                   ORDER BY sequence_number""",
                (rally_id, team_id)
            )
        else:
            cursor.execute(
                """SELECT * FROM contacts 
                   WHERE rally_id = %s AND team_id = %s
                   ORDER BY sequence_number""",
                (rally_id, team_id)
            )
        return cursor.fetchall()
    
    def get_contact_position(self, contact_id: int) -> Optional[tuple]:
        """
        Get rally_id and sequence_number for a contact.
        
        Args:
            contact_id: The contact ID
            
        Returns:
            Tuple of (rally_id, sequence_number) or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT rally_id, sequence_number FROM contacts WHERE contact_id = %s",
            (contact_id,)
        )
        return cursor.fetchone()
    
    def get_contact_rating(self, contact_id: int) -> Optional[int]:
        """
        Get rating for a contact.
        
        Args:
            contact_id: The contact ID
            
        Returns:
            Rating value or None
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT rating FROM contacts WHERE contact_id = %s",
            (contact_id,)
        )
        result = cursor.fetchone()
        return result[0] if result else None
    
    def get_contacts_before_sequence(self, rally_id: int, sequence_number: int,
                                    contact_type: Optional[str] = None) -> List[dict]:
        """
        Get contacts before a specific sequence number in a rally.
        
        Args:
            rally_id: The rally ID
            sequence_number: The sequence number threshold
            contact_type: Optional filter by contact type
            
        Returns:
            List of contact records
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if contact_type:
            cursor.execute(
                """SELECT * FROM contacts 
                   WHERE rally_id = %s AND sequence_number < %s AND contact_type = %s
                   ORDER BY sequence_number""",
                (rally_id, sequence_number, contact_type)
            )
        else:
            cursor.execute(
                """SELECT * FROM contacts 
                   WHERE rally_id = %s AND sequence_number < %s
                   ORDER BY sequence_number""",
                (rally_id, sequence_number)
            )
        return cursor.fetchall()
    
    def get_contacts_after_sequence(self, rally_id: int, sequence_number: int,
                                   team_id: Optional[int] = None) -> List[dict]:
        """
        Get contacts after a specific sequence number in a rally.
        
        Args:
            rally_id: The rally ID
            sequence_number: The sequence number threshold
            team_id: Optional filter by team
            
        Returns:
            List of contact records
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if team_id is not None:
            cursor.execute(
                """SELECT * FROM contacts 
                   WHERE rally_id = %s AND team_id = %s AND sequence_number > %s
                   ORDER BY sequence_number""",
                (rally_id, team_id, sequence_number)
            )
        else:
            cursor.execute(
                """SELECT * FROM contacts 
                   WHERE rally_id = %s AND sequence_number > %s
                   ORDER BY sequence_number""",
                (rally_id, sequence_number)
            )
        return cursor.fetchall()
    
    def count_contacts_by_outcome(self, rally_id: int, outcome: str) -> int:
        """
        Count contacts with specific outcome in a rally.
        
        Args:
            rally_id: The rally ID
            outcome: The outcome to count
            
        Returns:
            Count of matching contacts
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM contacts WHERE rally_id = %s AND outcome = %s",
            (rally_id, outcome)
        )
        return cursor.fetchone()[0]
    
    def get_contacts_for_game(self, game_id: int) -> List[dict]:
        """
        Get all contacts for a game with player, contact type, outcome, and rating.
        
        Args:
            game_id: The game ID
            
        Returns:
            List of contact records with player_id, contact_type, outcome, rating
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT 
                c.player_id,
                c.contact_type,
                c.outcome,
                c.rating
            FROM contacts c
            INNER JOIN rallies r ON c.rally_id = r.rally_id
            WHERE r.game_id = %s AND c.player_id IS NOT NULL
            ORDER BY r.rally_number, c.sequence_number
        """, (game_id,))
        return cursor.fetchall()
    
    def count_aces_for_player(self, game_id: int, player_id: int) -> int:
        """
        Count aces for a player in a game.
        
        Args:
            game_id: The game ID
            player_id: The player ID
            
        Returns:
            Count of aces
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) as ace_count
            FROM contacts c
            INNER JOIN rallies r ON c.rally_id = r.rally_id
            WHERE r.game_id = %s AND c.player_id = %s 
            AND c.contact_type = 'serve' AND c.outcome = 'ace'
        """, (game_id, player_id))
        return cursor.fetchone()[0]
    
    def count_assists_for_player(self, game_id: int, player_id: int) -> int:
        """
        Count assists for a player in a game.
        
        Args:
            game_id: The game ID
            player_id: The player ID
            
        Returns:
            Count of assists
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) as assist_count
            FROM contacts c
            INNER JOIN rallies r ON c.rally_id = r.rally_id
            WHERE r.game_id = %s AND c.player_id = %s 
            AND c.contact_type = 'set' AND c.outcome = 'assist'
        """, (game_id, player_id))
        return cursor.fetchone()[0]
    
    def get_receive_contacts_for_game(self, game_id: int, team_us_id: int) -> List[dict]:
        """
        Get all receive contacts for team_us in a game.
        
        Args:
            game_id: The game ID
            team_us_id: The team_us ID
            
        Returns:
            List of receive contact records with details
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT 
                c.contact_id,
                c.rally_id,
                c.sequence_number,
                c.team_id as receive_team_id,
                c.player_id,
                c.x,
                c.y,
                c.rating,
                COALESCE(c.rating_manual, 0) as rating_manual,
                r.serving_team_id
            FROM contacts c
            INNER JOIN rallies r ON c.rally_id = r.rally_id
            WHERE r.game_id = %s 
            AND c.contact_type = 'receive'
            AND c.team_id = %s
            ORDER BY r.rally_number, c.sequence_number
        """, (game_id, team_us_id))
        return cursor.fetchall()
    
    def get_next_contact_in_rally(self, rally_id: int, sequence_number: int) -> Optional[dict]:
        """
        Get the next contact in a rally after a given sequence number.
        
        Args:
            rally_id: The rally ID
            sequence_number: Current sequence number
            
        Returns:
            Next contact record or None
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT 
                contact_type,
                team_id,
                x,
                y
            FROM contacts
            WHERE rally_id = %s AND sequence_number = %s
            ORDER BY sequence_number
            LIMIT 1
        """, (rally_id, sequence_number + 1))
        return cursor.fetchone()
    
    def update_contact_rating(self, contact_id: int, rating: int):
        """
        Update the rating for a contact.
        
        Args:
            contact_id: The contact ID
            rating: The rating value
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE contacts
            SET rating = %s
            WHERE contact_id = %s
        """, (rating, contact_id))
        self.conn.commit()
    
    def get_max_sequence_number(self, rally_id: int) -> Optional[int]:
        """
        Get the maximum sequence number for a rally.
        
        Args:
            rally_id: The rally ID
            
        Returns:
            Maximum sequence number or None if no contacts exist
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT MAX(sequence_number) FROM contacts WHERE rally_id = %s",
            (rally_id,)
        )
        result = cursor.fetchone()
        return result[0] if result and result[0] else None
    
    def count_contacts_in_rally(self, rally_id: int) -> int:
        """
        Count contacts in a rally.
        
        Args:
            rally_id: The rally ID
            
        Returns:
            Number of contacts in the rally
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM contacts WHERE rally_id = %s",
            (rally_id,)
        )
        return cursor.fetchone()[0]
    
    def get_rally_contacts_reverse(self, rally_id: int, limit: Optional[int] = None) -> List[dict]:
        """
        Get contacts for a rally in reverse order (most recent first).
        
        Args:
            rally_id: The rally ID
            limit: Optional limit on number of contacts
            
        Returns:
            List of contact records
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        query = """
            SELECT team_id, contact_type, sequence_number
            FROM contacts 
            WHERE rally_id = %s
            ORDER BY sequence_number DESC
        """
        if limit:
            query += f" LIMIT {limit}"
        cursor.execute(query, (rally_id,))
        return cursor.fetchall()
    
    def get_last_contact_by_team(self, rally_id: int, team_id: int) -> Optional[dict]:
        """
        Get the last contact by a specific team in a rally.
        
        Args:
            rally_id: The rally ID
            team_id: The team ID
            
        Returns:
            Contact record or None if not found
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT contact_id, sequence_number, player_id, contact_type
            FROM contacts
            WHERE rally_id = %s AND team_id = %s
            ORDER BY sequence_number DESC
            LIMIT 1
        """, (rally_id, team_id))
        return cursor.fetchone()
    
    def get_contact_by_rally_and_sequence(self, rally_id: int, sequence_number: int) -> Optional[dict]:
        """
        Get a specific contact by rally_id and sequence_number.
        
        Args:
            rally_id: The rally ID
            sequence_number: The sequence number
            
        Returns:
            Contact record or None if not found
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT contact_id, contact_type, team_id
            FROM contacts
            WHERE rally_id = %s AND sequence_number = %s
        """, (rally_id, sequence_number))
        return cursor.fetchone()
    
    def get_contact_rating(self, contact_id: int) -> Optional[int]:
        """
        Get the rating of a contact.
        
        Args:
            contact_id: The contact ID
            
        Returns:
            Rating value or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT rating FROM contacts WHERE contact_id = %s", (contact_id,))
        result = cursor.fetchone()
        return result[0] if result else None
    
    def get_contact_full_details(self, rally_id: int, sequence_number: int) -> Optional[dict]:
        """
        Get full contact details by rally and sequence.
        
        Args:
            rally_id: The rally ID
            sequence_number: The sequence number
            
        Returns:
            Contact record with all fields or None if not found
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT contact_id, rally_id, sequence_number, player_id, contact_type, team_id, outcome
            FROM contacts
            WHERE rally_id = %s AND sequence_number = %s
        """, (rally_id, sequence_number))
        return cursor.fetchone()
    
    def get_contact_full_details_by_id(self, contact_id: int) -> Optional[dict]:
        """
        Get full contact details by contact_id.
        
        Args:
            contact_id: The contact ID
            
        Returns:
            Contact record with all fields or None if not found
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT contact_id, rally_id, sequence_number, player_id, contact_type, team_id, outcome
            FROM contacts
            WHERE contact_id = %s
        """, (contact_id,))
        return cursor.fetchone()
    
    def count_team_contacts_after_sequence(self, rally_id: int, team_id: int, after_sequence: int) -> int:
        """
        Count contacts by a team after a specific sequence number.
        
        Args:
            rally_id: The rally ID
            team_id: The team ID
            after_sequence: Sequence number to count after
            
        Returns:
            Count of contacts
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) 
            FROM contacts
            WHERE rally_id = %s AND team_id = %s AND sequence_number > %s
        """, (rally_id, team_id, after_sequence))
        return cursor.fetchone()[0]
    
    def get_max_team_us_sequence(self, rally_id: int, team_us_id: int) -> Optional[int]:
        """
        Get the maximum sequence number for team_us in a rally.
        
        Args:
            rally_id: The rally ID
            team_us_id: The team_us ID
            
        Returns:
            Maximum sequence number or None if no team_us contacts
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT MAX(sequence_number) as last_team_us_seq
            FROM contacts
            WHERE rally_id = %s AND team_id = %s
        """, (rally_id, team_us_id))
        result = cursor.fetchone()
        return result[0] if result and result[0] else None
    
    def count_contacts_for_game(self, game_id: int) -> int:
        """
        Count contacts for a game.
        
        Args:
            game_id: The game ID
            
        Returns:
            Number of contacts
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) 
            FROM contacts c
            INNER JOIN rallies r ON c.rally_id = r.rally_id
            WHERE r.game_id = %s
        """, (game_id,))
        return cursor.fetchone()[0] or 0
    
    def count_contacts_by_game(self, game_id: int) -> int:
        """Alias for count_contacts_for_game for consistency."""
        return self.count_contacts_for_game(game_id)
    
    def count_team_contacts_excluding_down(self, rally_id: int, team_id: int) -> int:
        """
        Count contacts by a team in a rally, excluding 'down' contacts.
        
        Args:
            rally_id: The rally ID
            team_id: The team ID
            
        Returns:
            Number of contacts (excluding 'down')
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) 
            FROM contacts 
            WHERE rally_id = %s AND team_id = %s AND contact_type != 'down'
        """, (rally_id, team_id))
        return cursor.fetchone()[0] or 0
    
    def get_first_contact_in_rally(self, rally_id: int) -> Optional[dict]:
        """
        Get the first contact in a rally (usually the serve).
        
        Args:
            rally_id: The rally ID
            
        Returns:
            Contact record or None if no contacts
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT contact_type, team_id 
            FROM contacts 
            WHERE rally_id = %s 
            ORDER BY sequence_number ASC 
            LIMIT 1
        """, (rally_id,))
        return cursor.fetchone()
    
    def get_last_contact_excluding_down(self, rally_id: int) -> Optional[dict]:
        """
        Get the most recent non-down contact in a rally.
        
        Args:
            rally_id: The rally ID
            
        Returns:
            Contact record or None if no contacts
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT contact_type, team_id 
            FROM contacts 
            WHERE rally_id = %s AND contact_type != 'down'
            ORDER BY sequence_number DESC 
            LIMIT 1
        """, (rally_id,))
        return cursor.fetchone()
    
    def get_last_team_contact_excluding_down(self, rally_id: int, team_id: int) -> Optional[dict]:
        """
        Get the last contact by a team, excluding 'down' contacts.
        
        Args:
            rally_id: The rally ID
            team_id: The team ID
            
        Returns:
            Contact record or None if not found
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT team_id 
            FROM contacts 
            WHERE rally_id = %s AND contact_type != 'down'
            ORDER BY sequence_number DESC 
            LIMIT 1
        """, (rally_id,))
        return cursor.fetchone()
    
    def get_previous_contact_by_type(self, rally_id: int, sequence_number: int, 
                                      contact_types: List[str]) -> Optional[dict]:
        """
        Get the previous contact before a sequence number with specific contact types.
        
        Args:
            rally_id: The rally ID
            sequence_number: The sequence number to search before
            contact_types: List of contact types to match
            
        Returns:
            Contact record or None if not found
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        # Build placeholders for the IN clause
        placeholders = ','.join(['%s'] * len(contact_types))
        query = f"""
            SELECT contact_id, contact_type, outcome
            FROM contacts
            WHERE rally_id = %s AND sequence_number < %s 
            AND contact_type IN ({placeholders})
            ORDER BY sequence_number DESC
            LIMIT 1
        """
        params = [rally_id, sequence_number] + contact_types
        cursor.execute(query, params)
        return cursor.fetchone()
    
    def get_serve_contact_by_rally(self, rally_id: int) -> Optional[dict]:
        """
        Get the serve contact for a rally.
        
        Args:
            rally_id: The rally ID
            
        Returns:
            Serve contact record or None if not found
        """
        cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT contact_type, team_id 
            FROM contacts 
            WHERE rally_id = %s AND contact_type = 'serve'
            ORDER BY sequence_number ASC 
            LIMIT 1
        """, (rally_id,))
        return cursor.fetchone()