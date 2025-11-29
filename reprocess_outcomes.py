"""
Re-process all completed rallies to apply the correct outcome logic.

This script can be run whenever you need to update outcomes for existing rallies.
It will apply all the current outcome rules:
- Ace: Serve that wins the point (or serve followed by receive error)
- Kill: Attack that wins the point (or attack/freeball/block followed by pass error)
- Stuff: Block that wins the point (prior contact marked as error)
- Error: Contact by losing team that causes them to lose
- Down: Floor contacts
- Continue: All other contacts
"""

import sqlite3
from database import VideoStatsDB

def assign_rally_outcomes(db, rally_id: int, point_winner_id: int, team_us_id: int, team_them_id: int):
    """Apply the assign_rally_outcomes logic to a specific rally."""
    if not db.conn:
        db.connect()
    
    # Get all contacts in this rally
    contacts = db.get_rally_contacts(rally_id)
    
    if not contacts:
        return
    
    # Determine losing team
    losing_team_id = team_them_id if point_winner_id == team_us_id else team_us_id
    
    # Get the very last player contact (not floor contact)
    last_player_contact = None
    for contact in reversed(contacts):
        if contact[4] != 'down':  # contact_type != 'down'
            last_player_contact = contact
            break
    
    if not last_player_contact:
        return
    
    contact_id = last_player_contact[0]
    contact_type = last_player_contact[4]
    team_id = last_player_contact[5]
    
    outcome = 'continue'  # Default
    
    # If the last contact was by the losing team, it's an error
    if team_id == losing_team_id:
        outcome = 'error'
    
    # If the last contact was by the winning team
    elif team_id == point_winner_id:
        # Check if it's a serve (could be an ace)
        if contact_type == 'serve':
            opponent_contacts_after_serve = 0
            for contact in contacts:
                if contact[4] != 'down' and contact[5] == losing_team_id:
                    opponent_contacts_after_serve += 1
            
            if opponent_contacts_after_serve <= 1:
                outcome = 'ace'
        
        # Check if it's an attack (could be a kill)
        elif contact_type == 'attack':
            outcome = 'kill'
        
        # Check if it's a block (could be a stuff)
        elif contact_type == 'block':
            outcome = 'stuff'
    
    # Update the outcome for this contact
    if outcome != 'continue':
        db.update_contact_outcome(contact_id, outcome)
    
    # Additional rules: Set outcomes for prior contacts based on subsequent errors
    contacts = db.get_rally_contacts(rally_id)  # Refresh to get updated outcomes
    
    for i, contact in enumerate(contacts):
        contact_id = contact[0]
        contact_type = contact[4]
        current_outcome = contact[8]
        
        # Rule 1: If this is a receive with error, find prior serve and mark it as ace
        if contact_type == 'receive' and current_outcome == 'error':
            for j in range(i - 1, -1, -1):
                prior_contact = contacts[j]
                prior_contact_id = prior_contact[0]
                prior_contact_type = prior_contact[4]
                
                if prior_contact_type == 'serve':
                    db.update_contact_outcome(prior_contact_id, 'ace')
                    break
        
        # Rule 2: If this is a pass with error, find prior attack/freeball/block and mark it as kill
        elif contact_type == 'pass' and current_outcome == 'error':
            for j in range(i - 1, -1, -1):
                prior_contact = contacts[j]
                prior_contact_id = prior_contact[0]
                prior_contact_type = prior_contact[4]
                
                if prior_contact_type in ['attack', 'freeball', 'block']:
                    db.update_contact_outcome(prior_contact_id, 'kill')
                    break
        
        # Rule 3: If this is a block with stuff outcome, mark prior contact as error
        elif contact_type == 'block' and current_outcome == 'stuff':
            for j in range(i - 1, -1, -1):
                prior_contact = contacts[j]
                prior_contact_id = prior_contact[0]
                prior_contact_type = prior_contact[4]
                
                # Skip 'down' contacts
                if prior_contact_type == 'down':
                    continue
                
                # Mark the prior contact as error
                db.update_contact_outcome(prior_contact_id, 'error')
                break


if __name__ == "__main__":
    # Main processing
    db = VideoStatsDB()
    db.connect()

    # Get all completed rallies (those with a point_winner_id)
    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT r.rally_id, r.point_winner_id, g.team_us_id, g.team_them_id
        FROM rallies r
        INNER JOIN games g ON r.game_id = g.game_id
        WHERE r.point_winner_id IS NOT NULL
        ORDER BY r.rally_id
    """)

    rallies = cursor.fetchall()

    print(f"\n{'='*80}")
    print(f"RE-PROCESSING ALL COMPLETED RALLIES")
    print(f"{'='*80}")
    print(f"Found {len(rallies)} completed rallies to process\n")

    # Reset all outcomes to 'continue' first (except 'down' which stays as 'down')
    print("Step 1: Resetting all outcomes to default...")
    cursor.execute("""
        UPDATE contacts 
        SET outcome = 'continue'
        WHERE outcome != 'down'
    """)
    db.conn.commit()
    print(f"  Reset {cursor.rowcount} contacts to 'continue'\n")

    # Now process each rally
    print("Step 2: Re-processing each rally with outcome logic...")
    processed = 0
    aces_assigned = 0
    kills_assigned = 0
    errors_assigned = 0

    for rally_id, point_winner_id, team_us_id, team_them_id in rallies:
        # Count outcomes before
        cursor.execute("SELECT COUNT(*) FROM contacts WHERE rally_id = ? AND outcome = 'ace'", (rally_id,))
        aces_before = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM contacts WHERE rally_id = ? AND outcome = 'kill'", (rally_id,))
        kills_before = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM contacts WHERE rally_id = ? AND outcome = 'error'", (rally_id,))
        errors_before = cursor.fetchone()[0]
        
        # Process the rally
        assign_rally_outcomes(db, rally_id, point_winner_id, team_us_id, team_them_id)
        
        # Count outcomes after
        cursor.execute("SELECT COUNT(*) FROM contacts WHERE rally_id = ? AND outcome = 'ace'", (rally_id,))
        aces_after = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM contacts WHERE rally_id = ? AND outcome = 'kill'", (rally_id,))
        kills_after = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM contacts WHERE rally_id = ? AND outcome = 'error'", (rally_id,))
        errors_after = cursor.fetchone()[0]
        
        # Track changes
        if aces_after > aces_before or kills_after > kills_before or errors_after > errors_before:
            aces_assigned += (aces_after - aces_before)
            kills_assigned += (kills_after - kills_before)
            errors_assigned += (errors_after - errors_before)
        
        processed += 1
        if processed % 10 == 0:
            print(f"  Processed {processed}/{len(rallies)} rallies...")

    print(f"  Processed {processed}/{len(rallies)} rallies\n")

    print(f"{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"Total rallies processed: {processed}")
    print(f"Aces assigned: {aces_assigned}")
    print(f"Kills assigned: {kills_assigned}")
    print(f"Errors assigned: {errors_assigned}")

    # Show outcome distribution
    cursor.execute("""
        SELECT outcome, COUNT(*) as count
        FROM contacts
        GROUP BY outcome
        ORDER BY count DESC
    """)
    outcome_counts = cursor.fetchall()

    print(f"\nFinal outcome distribution:")
    for outcome, count in outcome_counts:
        print(f"  {outcome:10s}: {count:4d}")

    print(f"\n{'='*80}")
    print("✓ ALL RALLIES RE-PROCESSED SUCCESSFULLY!")
    print(f"{'='*80}\n")

    db.close()

