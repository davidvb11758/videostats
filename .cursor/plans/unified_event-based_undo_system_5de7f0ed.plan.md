---
name: Unified Event-Based Undo System
overview: Extend the undo system to support undoing all game events (contacts, substitutions, libero actions, rotations, and point awards) by storing all actions in the events table and implementing a unified chronological undo that restores the previous state for each event type.
todos:
  - id: "1"
    content: "Update database schema to add new event types: contact and point_awarded"
    status: completed
  - id: "2"
    content: Add event logging for contacts in data_entry.py record_contact() method
    status: completed
    dependencies:
      - "1"
  - id: "3"
    content: Add event logging for point awards in data_entry.py end_rally() and on_point_awarded_from_mapper() methods
    status: completed
    dependencies:
      - "1"
  - id: "4"
    content: Enhance substitution event payloads with active_lineup snapshots in lineup_manager.py
    status: completed
    dependencies:
      - "1"
  - id: "5"
    content: Enhance libero event payloads with active_lineup snapshots in lineup_manager.py
    status: completed
    dependencies:
      - "1"
  - id: "6"
    content: Enhance rotation event payloads with active_lineup and rotation_state snapshots in lineup_manager.py
    status: completed
    dependencies:
      - "1"
  - id: "7"
    content: Create lineup restoration methods in lineup_manager.py (_restore_active_lineup_from_snapshot, _restore_rotation_state_from_snapshot)
    status: completed
    dependencies:
      - "4"
      - "5"
      - "6"
  - id: "8"
    content: Replace undo_last_contact() with unified undo_last_event() in data_entry.py
    status: completed
    dependencies:
      - "2"
      - "3"
      - "7"
  - id: "9"
    content: Implement _undo_contact_event() handler in data_entry.py - this should extract contact_id from event payload and call the existing undo_last_contact() logic/method to preserve all existing contact deletion functionality (including cascaded outcome reversals, rally un-ending, state restoration)
    status: completed
    dependencies:
      - "8"
  - id: "10"
    content: Implement _undo_point_awarded_event() handler in data_entry.py
    status: completed
    dependencies:
      - "8"
  - id: "11"
    content: Implement _undo_substitution_event() handler in data_entry.py
    status: completed
    dependencies:
      - "8"
      - "7"
  - id: "12"
    content: Implement _undo_libero_event() handler in data_entry.py
    status: completed
    dependencies:
      - "8"
      - "7"
  - id: "13"
    content: Implement _undo_rotation_event() handler in data_entry.py
    status: completed
    dependencies:
      - "8"
      - "7"
  - id: "14"
    content: Update undo button state check methods in data_entry.py and coordinate_mapper.py to check for any events (not just contacts)
    status: completed
    dependencies:
      - "8"
---

# Unified Event-Based Undo System

## Overview

Extend the undo functionality to support all game events (contacts, substitutions, libero actions, rotations, and point awards) by storing them in the events table and implementing a unified chronological undo system.

## Architecture Changes

### 1. Database Schema Updates

**File: `database.py`**

- Add new event types to the events table CHECK constraint:
- `'contact'` - for player contacts
- `'point_awarded'` - for point awards
- Update constraint: `CHECK(event_type IN ('rotation', 'substitution', 'libero', 'server_change', 'initial_setup', 'contact', 'point_awarded'))`
- Add migration to update existing databases with new event types

### 2. Event Logging for Contacts

**File: `data_entry.py`**

- In `record_contact()` method, after successfully adding a contact:
- Log a `'contact'` event to the events table
- Event payload should include:
    ```json
                    {
                      "contact_id": <contact_id>,
                      "rally_id": <rally_id>,
                      "sequence_number": <sequence_number>,
                      "player_id": <player_id>,
                      "contact_type": <contact_type>,
                      "team_id": <team_id>,
                      "x": <x>,
                      "y": <y>,
                      "timecode": <timecode>,
                      "outcome": <outcome>,
                      "rating": <rating>
                    }
    ```




- Use `lineup_manager._log_event()` or create a direct logging method

### 3. Event Logging for Point Awards

**File: `data_entry.py`**

- In `end_rally()` method, after calling `self.db.end_rally()`:
- Log a `'point_awarded'` event to the events table
- Event payload should include:
    ```json
                    {
                      "rally_id": <rally_id>,
                      "point_winner_id": <point_winner_id>,
                      "rally_end_time": <rally_end_time>,
                      "score_us": <score_us>,
                      "score_them": <score_them>,
                      "auto_rotated": <boolean>  // if rotation occurred
                    }
    ```




- In `on_point_awarded_from_mapper()`, also log the point_awarded event

**File: `coordinate_mapper.py`**

- In `award_point()` method, after calling `self.db.end_rally()`:
- Log a `'point_awarded'` event (or emit signal that triggers logging in data_entry)

### 4. Enhanced Event Payloads for Existing Events

**File: `lineup_manager.py`**

- Update `substitution()` method to include more state in event payload:
- Add `substitution_id` to payload
- Include `active_lineup_snapshot_before` and `active_lineup_snapshot_after` for restoration
- Update `libero_replace()` method to include more state:
- Add `libero_action_id` to payload
- Include `active_lineup_snapshot_before` and `active_lineup_snapshot_after`
- Update `rotate()` method to include more state:
- Include `active_lineup_snapshot_before` and `active_lineup_snapshot_after`
- Include `rotation_state_before` and `rotation_state_after`

### 5. Unified Undo Implementation

**File: `data_entry.py`**

- Refactor existing `undo_last_contact()` method:
- Extract the core contact deletion logic into a helper method `_undo_contact_by_id(contact_id)` that handles:
    - Getting contact details from database
    - Handling cascaded outcome reversals (block stuff→continue, serve ace→continue, attack kill→continue)
    - Deleting contact from contacts table via `self.db.delete_contact(contact_id)`
    - Un-ending rally if needed (`self.db.unend_rally()`)
    - Restoring state variables (current_sequence, rally_in_progress, current_rally_id, opponent_contact_count)
    - Updating UI state (`update_ui_state()`)
- Keep existing `undo_last_contact()` method but have it find the last contact and call `_undo_contact_by_id()`
- Create new `undo_last_event()` method to replace direct calls to `undo_last_contact()`:
- Query events table for most recent event (any type) for the current game
- Order by `created_at DESC` and `id DESC` to get chronological order
- Based on `event_type`, call appropriate undo handler:
    - `'contact'`: Call `_undo_contact_event(event_payload)`
    - `'point_awarded'`: Call `_undo_point_awarded_event(event_payload)`
    - `'substitution'`: Call `_undo_substitution_event(event_payload)`
    - `'libero'`: Call `_undo_libero_event(event_payload)`
    - `'rotation'`: Call `_undo_rotation_event(event_payload)`
    - `'server_change'`: Call `_undo_server_change_event(event_payload)` (if needed)
- After successful undo, delete the event record from events table
- Create undo handlers for each event type:
- `_undo_contact_event(event_payload)`: 
- Extract `contact_id` from event payload
- Call `_undo_contact_by_id(contact_id)` to preserve ALL existing contact deletion logic
- Return result tuple (player_name, player_number, contact_type) for popup display
- `_undo_point_awarded_event(event_payload)`: Un-end rally, restore score, restore rotation if needed
- `_undo_substitution_event(event_payload)`: Reverse substitution using active_lineup snapshots
- `_undo_libero_event(event_payload)`: Reverse libero action using active_lineup snapshots
- `_undo_rotation_event(event_payload)`: Reverse rotation using active_lineup and rotation_state snapshots

**File: `lineup_manager.py`**

- Add methods to restore lineup state from snapshots:
- `_restore_active_lineup_from_snapshot(game_id, team_id, snapshot)`: Restore active_lineup table
- `_restore_rotation_state_from_snapshot(game_id, team_id, snapshot)`: Restore rotation_state table
- Add method to delete substitution/libero records:
- `_delete_substitution(substitution_id)`
- `_delete_libero_action(libero_action_id)`

### 6. Update Undo Button State Check

**File: `data_entry.py`**

- Update `_has_contact_to_undo()` → rename to `_has_event_to_undo()`:
- Check if there are any events (any type) for the current game
- Query: `SELECT COUNT(*) FROM events WHERE game_id = ? AND event_type != 'initial_setup'`

**File: `coordinate_mapper.py`**

- Update `_has_contact_to_undo()` → rename to `_has_event_to_undo()`:
- Same logic as data_entry.py

### 7. Undo Point Awarded Implementation

**File: `data_entry.py`**

- `_undo_point_awarded_event(event_payload)`:
- Extract `rally_id`, `point_winner_id`, `score_us`, `score_them`, `auto_rotated`
- Call `self.db.unend_rally(rally_id)` to un-end the rally
- Restore score: `self.score_us = score_us`, `self.score_them = score_them`
- If `auto_rotated` was true, reverse the rotation:
    - Get rotation_state before rotation from payload
    - Restore active_lineup and rotation_state to previous state
- Restore rally state: `self.rally_in_progress = True`, `self.current_rally_id = rally_id`
- Update UI state

### 8. Undo Substitution Implementation

**File: `data_entry.py`**

- `_undo_substitution_event(event_payload)`:
- Extract `substitution_id`, `active_lineup_snapshot_before`, `out_player_id`, `in_player_id`
- Delete the substitution record from substitutions table
- Restore active_lineup from `active_lineup_snapshot_before`
- Update player active status (mark in_player as inactive, out_player as active)
- Update UI (player buttons)

### 9. Undo Libero Action Implementation

**File: `data_entry.py`**

- `_undo_libero_event(event_payload)`:
- Extract `libero_action_id`, `active_lineup_snapshot_before`, `action` (enter/exit)
- Delete the libero_action record from libero_actions table
- Restore active_lineup from `active_lineup_snapshot_before`
- Update player active status
- Update UI

### 10. Undo Rotation Implementation

**File: `data_entry.py`**

- `_undo_rotation_event(event_payload)`:
- Extract `active_lineup_snapshot_before`, `rotation_state_before`
- Restore active_lineup from snapshot
- Restore rotation_state from snapshot
- Update UI (player buttons)

## Implementation Order

1. Update database schema (add new event types)
2. Add event logging for contacts in `record_contact()`
3. Add event logging for point awards in `end_rally()` and `on_point_awarded_from_mapper()`
4. Enhance existing event payloads (substitution, libero, rotation) with snapshots
5. Implement unified `undo_last_event()` method
6. Implement individual undo handlers for each event type
7. Update undo button state checks
8. Test each undo scenario

## Key Considerations

- Events must be stored in chronological order (use `created_at` and `id` for ordering)
- Snapshot data in payloads must be complete enough to restore state
- Undoing a point award may need to reverse an auto-rotation
- Undoing substitutions/libero must restore active_lineup correctly
- The contacts table remains unchanged - events table is for undo tracking only
- Initial_setup events should never be undone (excluded from undo queries)
- **IMPORTANT**: When undoing a contact event, preserve ALL existing contact deletion logic from `undo_last_contact()` method, including:
- Deleting contact from contacts table via `self.db.delete_contact(contact_id)`
- Handling cascaded outcome reversals (block stuff→continue, serve ace→continue, attack kill→continue)