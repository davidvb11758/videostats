---
name: Replace Main Menu with RocketsVideoStats
overview: Replace main_menu.py with a new RocketsVideoStats.py that loads RocketsVideoStats.ui, adds a game selection combo box, modifies existing methods to use game_id, and adds four new button methods.
todos: []
---

#Replace Main Menu with RocketsVideoStats

## Overview

Create a new main menu implementation (`RocketsVideoStats.py`) that loads the PySide6 Designer UI file (`RocketsVideoStats.ui`), replacing the current programmatic UI in `main_menu.py`. The new implementation will add game selection functionality and modify existing methods to work with a selected game.

## Files to Create/Modify

### 1. Create `RocketsVideoStats.py`

- New file that loads `RocketsVideoStats.ui` using `QUiLoader`
- Initialize database connection (same as current `main_menu.py`)
- Connect UI signals to methods

### 2. Migrate Existing Methods (Work As-Is)

These methods from `main_menu.py` can be copied directly:

- `create_new_team()` → connected to `btn_create_team`
- `edit_existing_team()` → connected to `btn_edit_team`
- `create_new_game()` → connected to `btn_create_game`
- `view_reports()` → connected to `btn_view_reports`

### 3. Add Game Selection Combo Box

- Add `populate_game_combo()` method to populate `combo_select_game`
- Use same SQL query pattern as `view_paths.py` lines 1760-1789
- Store game data in combo box items using `Qt.UserRole` (same pattern as `view_paths.py`)
- Format: `"Game {game_id}: {team_us_name} vs {team_them_name} ({game_date})"`
- Add "Select a game" as first item with `None` as data
- Connect `combo_select_game.currentIndexChanged` to update `self.selected_game_id`

### 4. Modify `view_ball_paths()` Method

- Current: Opens `ContactPathViewer` without game_id (line 173 in `main_menu.py`)
- New: Get `game_id` from `combo_select_game.currentData(Qt.UserRole)`
- Validate game_id is selected (show warning if not)
- Modify `ContactPathViewer.__init__()` to accept optional `game_id` parameter
- After creating `ContactPathViewer`, if `game_id` provided, set it and trigger game selection:
- Set `path_viewer.game_id` directly
- Call `path_viewer.on_game_selected()` with appropriate index
- Or use `path_viewer.ui.comboBox.setCurrentIndex()` to select the game

### 5. Modify `resume_data_entry()` Method

- Current: Shows dialog to select game (lines 188-306 in `main_menu.py`)
- New: Get `game_id` from `combo_select_game.currentData(Qt.UserRole)`
- Validate game_id is selected (show warning if not)
- Query database for game data using `game_id` (same query pattern as lines 192-200)
- Pass `game_id` directly to `DataEntryWindow` (remove dialog selection logic)

### 6. Add New Button Methods (Stubs)

Create placeholder methods for new buttons:

- `edit_game_setup()` → connected to `btn_edit_game_setup`
- Stub: Show message "Edit Game Setup - Not yet implemented"
- `refresh_statistics()` → connected to `btn_refresh_statistics`
- Stub: Show message "Refresh Statistics - Not yet implemented"
- `end_game()` → connected to `btn_end_game`
- Stub: Show message "End Game - Not yet implemented"
- `close_app()` → connected to `btn_close_app`
- Close database connection
- Call `QApplication.quit()` or `self.close()`

### 7. Update `main.py`

- Change import from `from main_menu import MainMenuWindow` to `from RocketsVideoStats import RocketsVideoStatsWindow` (or appropriate class name)
- Update instantiation: `window = RocketsVideoStatsWindow()`

### 8. Handle Game Combo Box Updates

- Add method to refresh combo box when new game is created
- Call `populate_game_combo()` after successful game creation
- Optionally auto-select newly created game in combo box

## Implementation Details

### ContactPathViewer Modification

The `ContactPathViewer.__init__()` currently accepts `(ui_widget, db)`. Need to:

- Add optional `game_id=None` parameter
- After `populate_games_dropdown()` (line 1453), if `game_id` provided:
- Find the combo box index that matches the `game_id`
- Set `self.game_id`, `self.team_us_id`, `self.team_them_id` from stored data
- Call `self.on_game_selected()` with the found index, or manually set the combo box

### Game Data Storage Pattern

Follow the pattern from `view_paths.py` lines 1783-1789:

```python
self.ui.combo_select_game.setItemData(index, {
    'game_id': game_id,
    'team_us_id': team_us_id,
    'team_them_id': team_them_id,
    'team_us_name': team_us_name,
    'team_them_name': team_them_name
}, Qt.UserRole)
```



### Error Handling

- Validate `game_id` is selected before calling methods that require it
- Show `QMessageBox.warning` if game not selected when needed
- Handle case where combo box has no games (show appropriate message)

## Dependencies

- `RocketsVideoStats.ui` must exist (already confirmed)
- All existing dialog classes: `CreateTeamDialog`, `EditTeamDialog`, `CreateGameDialog`, `StatsApp`
- `ContactPathViewer` from `view_paths.py` (needs minor modification)
- `DataEntryWindow` from `data_entry.py`

## Testing Considerations

- Test with no games in database
- Test with single game
- Test with multiple games
- Test game selection and button functionality