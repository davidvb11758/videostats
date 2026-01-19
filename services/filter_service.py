"""
Filter service for parsing and validating filter criteria.
"""

from typing import Dict, List, Optional


class FilterService:
    """Service for handling filter logic."""
    
    CONTACT_TYPE_MAPPING = {
        'serve': 'serve',
        'receive': 'receive',
        'pass': 'pass',
        'set': 'set',
        'attack': 'attack',
        'freeball': 'freeball',
        'block': 'block',
        'down': 'down'
    }
    
    OUTCOME_MAPPING = {
        'continue': 'continue',
        'ace': 'ace',
        'kill': 'kill',
        'stuff': 'stuff',
        'error': 'error',
        'down': 'down',
        'assist': 'assist',
        'fault': 'fault'
    }
    
    @staticmethod
    def parse_filters_from_ui(ui_widgets) -> Dict:
        """
        Parse filters from PySide6 UI widgets.
        
        Args:
            ui_widgets: Object with UI widget attributes (checkboxes, lists, etc.)
            
        Returns:
            Dictionary with filter criteria
        """
        filters = {
            'player_ids': [],
            'all_players_selected': False,
            'team_ids': [],
            'contact_types': [],
            'outcomes': [],
            'ratings': [],
            'use_rating_filter': False
        }
        
        # Parse player selection
        if hasattr(ui_widgets, 'player_list_widget') and ui_widgets.player_list_widget:
            selected_items = ui_widgets.player_list_widget.selectedItems()
            for item in selected_items:
                player_id = item.data(Qt.UserRole)
                if player_id is None:
                    filters['all_players_selected'] = True
                    break
                else:
                    filters['player_ids'].append(player_id)
        
        # Parse team filters
        show_team_a = True
        show_team_b = True
        if hasattr(ui_widgets, 'team_filter_checkbox_a') and ui_widgets.team_filter_checkbox_a:
            show_team_a = ui_widgets.team_filter_checkbox_a.isChecked()
        if hasattr(ui_widgets, 'team_filter_checkbox_b') and ui_widgets.team_filter_checkbox_b:
            show_team_b = ui_widgets.team_filter_checkbox_b.isChecked()
        
        if hasattr(ui_widgets, 'team_us_id') and hasattr(ui_widgets, 'team_them_id'):
            if show_team_a:
                filters['team_ids'].append(ui_widgets.team_us_id)
            if show_team_b:
                filters['team_ids'].append(ui_widgets.team_them_id)
        
        # Parse contact types
        # Try new format first (contact_checkboxes dict)
        if hasattr(ui_widgets, 'contact_checkboxes') and ui_widgets.contact_checkboxes:
            for contact_type_key, checkbox in ui_widgets.contact_checkboxes.items():
                if checkbox.isChecked():
                    filters['contact_types'].append(FilterService.CONTACT_TYPE_MAPPING.get(contact_type_key, contact_type_key))
        else:
            # Fallback to old format
            for contact_type_key, contact_type_value in FilterService.CONTACT_TYPE_MAPPING.items():
                checkbox_name = f'checkBox_{contact_type_key}_A'
                if hasattr(ui_widgets, checkbox_name):
                    checkbox = getattr(ui_widgets, checkbox_name)
                    if checkbox.isChecked():
                        filters['contact_types'].append(contact_type_value)
        
        # Parse outcomes
        # Try new format first (outcome_checkboxes dict)
        if hasattr(ui_widgets, 'outcome_checkboxes') and ui_widgets.outcome_checkboxes:
            for outcome_key, checkbox in ui_widgets.outcome_checkboxes.items():
                if checkbox.isChecked():
                    filters['outcomes'].append(FilterService.OUTCOME_MAPPING.get(outcome_key, outcome_key))
        else:
            # Fallback to old format
            for outcome_key, outcome_value in FilterService.OUTCOME_MAPPING.items():
                checkbox_name = f'checkBox_outcome_{outcome_key}'
                if hasattr(ui_widgets, checkbox_name):
                    checkbox = getattr(ui_widgets, checkbox_name)
                    if checkbox.isChecked():
                        filters['outcomes'].append(outcome_value)
        
        # Parse ratings (only applies when Receive is selected)
        receive_selected = 'receive' in filters['contact_types']
        if hasattr(ui_widgets, 'rating_checkboxes') and ui_widgets.rating_checkboxes:
            for rating, checkbox in ui_widgets.rating_checkboxes.items():
                if checkbox.isChecked():
                    filters['ratings'].append(rating)
        
        filters['use_rating_filter'] = receive_selected and len(filters['ratings']) > 0
        
        # If no ratings selected, don't apply rating filter
        if not filters['ratings']:
            filters['use_rating_filter'] = False
        
        # If no filters selected, show all
        if not filters['contact_types']:
            filters['contact_types'] = list(FilterService.CONTACT_TYPE_MAPPING.values())
        if not filters['outcomes']:
            filters['outcomes'] = list(FilterService.OUTCOME_MAPPING.values())
        
        return filters
    
    @staticmethod
    def validate_filters(filters: Dict) -> Dict:
        """
        Validate and normalize filter dictionary (for API use).
        
        Args:
            filters: Dictionary with filter criteria
            
        Returns:
            Validated and normalized filter dictionary
        """
        validated = {
            'player_ids': filters.get('player_ids', []),
            'all_players_selected': filters.get('all_players_selected', False),
            'team_ids': filters.get('team_ids', []),
            'contact_types': filters.get('contact_types', []),
            'outcomes': filters.get('outcomes', []),
            'ratings': filters.get('ratings', []),
            'use_rating_filter': filters.get('use_rating_filter', False)
        }
        
        # Validate contact types
        validated['contact_types'] = [
            ct for ct in validated['contact_types']
            if ct in FilterService.CONTACT_TYPE_MAPPING.values()
        ]
        if not validated['contact_types']:
            validated['contact_types'] = list(FilterService.CONTACT_TYPE_MAPPING.values())
        
        # Validate outcomes
        validated['outcomes'] = [
            oc for oc in validated['outcomes']
            if oc in FilterService.OUTCOME_MAPPING.values()
        ]
        if not validated['outcomes']:
            validated['outcomes'] = list(FilterService.OUTCOME_MAPPING.values())
        
        # Validate ratings
        validated['ratings'] = [
            r for r in validated['ratings']
            if isinstance(r, int) and 0 <= r <= 3
        ]
        
        # Validate player_ids
        validated['player_ids'] = [
            pid for pid in validated['player_ids']
            if isinstance(pid, int) and pid > 0
        ]
        
        # Validate team_ids
        validated['team_ids'] = [
            tid for tid in validated['team_ids']
            if isinstance(tid, int) and tid > 0
        ]
        
        return validated

