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
