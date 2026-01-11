// Application State
const state = {
    games: [],
    selectedGames: [],
    currentClips: [],
    collections: [],
    currentCollection: null,
    filters: {
        player_ids: [],
        all_players_selected: true,
        team_ids: [],
        contact_types: [],
        outcomes: [],
        ratings: [],
        use_rating_filter: false
    },
    currentVideoClip: null,
    isCollectionMode: false,
    players: [],
    teamUsId: null,
    teamThemId: null
};

// API Functions
async function apiGet(endpoint) {
    const response = await fetch(endpoint);
    if (!response.ok) {
        throw new Error(`API error: ${response.statusText}`);
    }
    return await response.json();
}

async function apiPost(endpoint, data) {
    const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
    if (!response.ok) {
        throw new Error(`API error: ${response.statusText}`);
    }
    return await response.json();
}

async function apiPut(endpoint, data) {
    const response = await fetch(endpoint, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
    if (!response.ok) {
        throw new Error(`API error: ${response.statusText}`);
    }
    return await response.json();
}

async function apiDelete(endpoint) {
    const response = await fetch(endpoint, {
        method: 'DELETE'
    });
    if (!response.ok) {
        throw new Error(`API error: ${response.statusText}`);
    }
    return await response.json();
}

// Load Games
async function loadGames() {
    try {
        state.games = await apiGet('/api/games');
        renderGames();
    } catch (error) {
        console.error('Error loading games:', error);
        alert('Failed to load games: ' + error.message);
    }
}

function renderGames() {
    const gameList = document.getElementById('game-list');
    gameList.innerHTML = '';
    
    const searchTerm = document.getElementById('game-search').value.toLowerCase();
    const filteredGames = state.games.filter(game => 
        game.game_alias.toLowerCase().includes(searchTerm) ||
        (game.game_date && game.game_date.toLowerCase().includes(searchTerm))
    );
    
    filteredGames.forEach(game => {
        const gameItem = document.createElement('div');
        gameItem.className = 'game-item';
        if (state.selectedGames.includes(game.game_id)) {
            gameItem.classList.add('selected');
        }
        
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.checked = state.selectedGames.includes(game.game_id);
        checkbox.addEventListener('change', () => {
            if (checkbox.checked) {
                state.selectedGames.push(game.game_id);
                gameItem.classList.add('selected');
            } else {
                state.selectedGames = state.selectedGames.filter(id => id !== game.game_id);
                gameItem.classList.remove('selected');
            }
            // Exit collection mode when games change
            state.isCollectionMode = false;
            // Load players when game selection changes
            loadPlayers();
            // Load clips if not in collection mode
            if (!state.isCollectionMode) {
                loadClips();
            }
        });
        
        const label = document.createElement('label');
        label.appendChild(checkbox);
        label.appendChild(document.createTextNode(`${game.game_alias} (${game.game_date || ''})`));
        
        gameItem.appendChild(label);
        gameList.appendChild(gameItem);
    });
}

// Load Players for Selected Games
async function loadPlayers() {
    if (state.selectedGames.length === 0) {
        state.players = [];
        renderPlayers();
        return;
    }
    
    try {
        // Load players from first selected game
        const gameId = state.selectedGames[0];
        const playersData = await apiGet(`/api/games/${gameId}/players`);
        
        // Combine players from both teams
        const allPlayers = [...playersData.team_us, ...playersData.team_them];
        state.players = allPlayers;
        state.teamUsId = playersData.team_us[0]?.team_id || null;
        state.teamThemId = playersData.team_them[0]?.team_id || null;
        
        // Update team labels
        if (state.teamUsId) {
            document.getElementById('team-us-label').textContent = 'Team Us';
        }
        if (state.teamThemId) {
            document.getElementById('team-them-label').textContent = 'Team Them';
        }
        
        renderPlayers();
    } catch (error) {
        console.error('Error loading players:', error);
    }
}

function renderPlayers() {
    const playerList = document.getElementById('player-list');
    
    // Clear existing players (keep "All Players" checkbox)
    const allPlayersCheckbox = document.getElementById('all-players-checkbox');
    playerList.innerHTML = '';
    playerList.appendChild(document.createElement('label')).className = 'checkbox-label';
    const allLabel = playerList.querySelector('label:last-child');
    allLabel.appendChild(allPlayersCheckbox.cloneNode(true));
    allLabel.appendChild(document.createTextNode('All Players'));
    
    // Update checkbox state
    const newAllCheckbox = playerList.querySelector('input[type="checkbox"]');
    newAllCheckbox.checked = state.filters.all_players_selected;
    newAllCheckbox.addEventListener('change', () => {
        state.filters.all_players_selected = newAllCheckbox.checked;
        if (newAllCheckbox.checked) {
            state.filters.player_ids = [];
        }
        renderPlayers();
    });
    
    // Add players
    state.players.forEach(player => {
        const label = document.createElement('label');
        label.className = 'checkbox-label';
        
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.value = player.player_id;
        checkbox.checked = state.filters.player_ids.includes(player.player_id);
        checkbox.disabled = state.filters.all_players_selected;
        checkbox.addEventListener('change', () => {
            if (checkbox.checked) {
                state.filters.player_ids.push(player.player_id);
            } else {
                state.filters.player_ids = state.filters.player_ids.filter(id => id !== player.player_id);
            }
            state.filters.all_players_selected = false;
            newAllCheckbox.checked = false;
        });
        
        label.appendChild(checkbox);
        label.appendChild(document.createTextNode(
            `${player.player_number || ''} ${player.name || ''}`.trim()
        ));
        
        playerList.appendChild(label);
    });
}

// Load Clips
async function loadClips() {
    // Don't reload if we're in collection mode
    if (state.isCollectionMode) {
        return;
    }
    
    if (state.selectedGames.length === 0) {
        state.currentClips = [];
        renderClips();
        return;
    }
    
    try {
        const filters = buildFilters();
        const clipsData = await apiPost('/api/clips', {
            game_ids: state.selectedGames,
            filters: filters
        });
        
        state.currentClips = clipsData.map(c => ({
            ...c,
            order_index: c.order_index || 0
        }));
        
        renderClips();
    } catch (error) {
        console.error('Error loading clips:', error);
        alert('Failed to load clips: ' + error.message);
    }
}

function buildFilters() {
    const filters = {
        player_ids: state.filters.player_ids,
        all_players_selected: state.filters.all_players_selected,
        team_ids: [],
        contact_types: [],
        outcomes: [],
        ratings: [],
        use_rating_filter: false
    };
    
    // Get selected contact types
    document.querySelectorAll('#contact-types-grid input[type="checkbox"]:checked').forEach(cb => {
        filters.contact_types.push(cb.value);
    });
    
    // Get selected outcomes
    document.querySelectorAll('#outcomes-grid input[type="checkbox"]:checked').forEach(cb => {
        filters.outcomes.push(cb.value);
    });
    
    // Get selected ratings (only if Receive is selected)
    const receiveSelected = filters.contact_types.includes('receive');
    if (receiveSelected) {
        document.querySelectorAll('#ratings-row input[type="checkbox"]:checked').forEach(cb => {
            filters.ratings.push(parseInt(cb.value));
        });
        filters.use_rating_filter = filters.ratings.length > 0;
    }
    
    // Get team filters
    if (document.getElementById('team-us-checkbox').checked && state.teamUsId) {
        filters.team_ids.push(state.teamUsId);
    }
    if (document.getElementById('team-them-checkbox').checked && state.teamThemId) {
        filters.team_ids.push(state.teamThemId);
    }
    
    return filters;
}

function renderClips() {
    const tbody = document.getElementById('clip-table-body');
    tbody.innerHTML = '';
    
    // Sort clips by order_index
    const sortedClips = [...state.currentClips].sort((a, b) => a.order_index - b.order_index);
    
    sortedClips.forEach((clip, index) => {
        const row = document.createElement('tr');
        row.dataset.contactId = clip.contact_id;
        row.dataset.gameId = clip.game_id;
        row.draggable = true;
        
        // Drag handle
        const dragCell = document.createElement('td');
        dragCell.className = 'drag-handle-col';
        dragCell.innerHTML = '<span class="drag-handle">⋮⋮</span>';
        row.appendChild(dragCell);
        
        // Checkbox
        const checkboxCell = document.createElement('td');
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.dataset.contactId = clip.contact_id;
        checkbox.dataset.gameId = clip.game_id;
        // Restore checkbox state if clip has is_selected property (from saved collection)
        // Handle both boolean true and integer 1 (SQLite stores booleans as integers)
        checkbox.checked = clip.is_selected === true || clip.is_selected === 1 || clip.is_selected === '1';
        checkboxCell.appendChild(checkbox);
        row.appendChild(checkboxCell);
        
        // Game
        const gameCell = document.createElement('td');
        gameCell.textContent = clip.game_alias || '';
        row.appendChild(gameCell);
        
        // Stars
        const starsCell = document.createElement('td');
        starsCell.appendChild(createStarRating(clip.contact_id, clip.game_id, clip.star_rating || 0));
        row.appendChild(starsCell);
        
        // Rally
        const rallyCell = document.createElement('td');
        rallyCell.textContent = clip.rally_number || '';
        row.appendChild(rallyCell);
        
        // Seq
        const seqCell = document.createElement('td');
        seqCell.textContent = clip.sequence_number || '';
        row.appendChild(seqCell);
        
        // Player
        const playerCell = document.createElement('td');
        playerCell.textContent = clip.player_name || clip.player_number || '';
        row.appendChild(playerCell);
        
        // Type
        const typeCell = document.createElement('td');
        typeCell.textContent = clip.contact_type || '';
        row.appendChild(typeCell);
        
        // Rating (only show for receive contacts)
        const ratingCell = document.createElement('td');
        if (clip.contact_type === 'receive') {
            ratingCell.textContent = clip.rating !== null && clip.rating !== undefined ? clip.rating : '';
        } else {
            ratingCell.textContent = '-';
        }
        row.appendChild(ratingCell);
        
        // Outcome
        const outcomeCell = document.createElement('td');
        outcomeCell.textContent = clip.outcome || '';
        row.appendChild(outcomeCell);
        
        // View
        const viewCell = document.createElement('td');
        const viewBtn = document.createElement('button');
        viewBtn.className = 'btn btn-secondary';
        viewBtn.textContent = 'View';
        viewBtn.addEventListener('click', () => viewClip(clip));
        viewCell.appendChild(viewBtn);
        row.appendChild(viewCell);
        
        // Drag and drop handlers
        row.addEventListener('dragstart', (e) => {
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/html', row.innerHTML);
            row.classList.add('dragging');
        });
        
        row.addEventListener('dragend', () => {
            row.classList.remove('dragging');
        });
        
        row.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
        });
        
        row.addEventListener('drop', (e) => {
            e.preventDefault();
            const draggedRow = document.querySelector('.dragging');
            if (draggedRow && draggedRow !== row) {
                const rows = Array.from(tbody.children);
                const draggedIndex = rows.indexOf(draggedRow);
                const targetIndex = rows.indexOf(row);
                
                if (draggedIndex < targetIndex) {
                    tbody.insertBefore(draggedRow, row.nextSibling);
                } else {
                    tbody.insertBefore(draggedRow, row);
                }
                
                updateClipOrder();
            }
        });
        
        tbody.appendChild(row);
    });
}

function createStarRating(contactId, gameId, currentRating) {
    const container = document.createElement('div');
    container.className = 'star-rating';
    
    for (let i = 1; i <= 5; i++) {
        const star = document.createElement('span');
        star.className = 'star';
        star.textContent = '★';
        if (i <= currentRating) {
            star.classList.add('filled', 'active');
        }
        
        star.addEventListener('click', async () => {
            const newRating = i;
            try {
                await apiPut(`/api/clips/${contactId}/${gameId}/star-rating`, {
                    star_rating: newRating
                });
                
                // Update clip in state
                const clip = state.currentClips.find(c => 
                    c.contact_id === contactId && c.game_id === gameId
                );
                if (clip) {
                    clip.star_rating = newRating;
                }
                
                // Re-render star rating
                container.parentNode.replaceChild(
                    createStarRating(contactId, gameId, newRating),
                    container
                );
            } catch (error) {
                console.error('Error updating star rating:', error);
                alert('Failed to update star rating: ' + error.message);
            }
        });
        
        star.addEventListener('mouseenter', () => {
            const stars = container.querySelectorAll('.star');
            stars.forEach((s, idx) => {
                if (idx < i) {
                    s.classList.add('active');
                } else {
                    s.classList.remove('active');
                }
            });
        });
        
        container.addEventListener('mouseleave', () => {
            const stars = container.querySelectorAll('.star');
            stars.forEach((s, idx) => {
                if (idx < currentRating) {
                    s.classList.add('active');
                } else {
                    s.classList.remove('active');
                }
            });
        });
        
        container.appendChild(star);
    }
    
    return container;
}

function updateClipOrder() {
    const rows = document.querySelectorAll('#clip-table-body tr');
    rows.forEach((row, index) => {
        const contactId = parseInt(row.dataset.contactId);
        const gameId = parseInt(row.dataset.gameId);
        const clip = state.currentClips.find(c => 
            c.contact_id === contactId && c.game_id === gameId
        );
        if (clip) {
            clip.order_index = index;
        }
    });
}

// View Clip Video
async function viewClip(clip) {
    const modal = document.getElementById('video-modal');
    const videoPlayer = document.getElementById('video-player');
    const videoInfo = document.getElementById('video-info');
    
    // Store current clip for replay
    state.currentVideoClip = clip;
    
    // Build video URL with timecode
    const videoPath = clip.video_file_path;
    if (!videoPath) {
        alert('Video file path not available');
        return;
    }
    
    // Check if video file exists first
    try {
        const checkResponse = await apiGet(`/api/check-video?path=${encodeURIComponent(videoPath)}`);
        
        if (!checkResponse.exists) {
            videoInfo.innerHTML = `
                <strong style="color: red;">Error: Video file not found</strong><br>
                <strong>Path:</strong> ${checkResponse.path}<br>
                <strong>Absolute Path:</strong> ${checkResponse.absolute_path}<br><br>
                <strong>Clip Info:</strong><br>
                Game: ${clip.game_alias}<br>
                Rally: ${clip.rally_number}, Sequence: ${clip.sequence_number}<br>
                Player: ${clip.player_name || clip.player_number || 'N/A'}<br>
                Type: ${clip.contact_type}<br>
                Outcome: ${clip.outcome}<br>
                Timecode: ${formatTimecode(clip.timecode_ms)}
            `;
            videoPlayer.src = '';
            modal.style.display = 'block';
            return;
        }
        
        // Build video URL with encoded path
        const videoUrl = `/api/source-video?path=${encodeURIComponent(videoPath)}`;
        
        // Set video info
        videoInfo.innerHTML = `
            <strong>Clip Info:</strong><br>
            Game: ${clip.game_alias}<br>
            Rally: ${clip.rally_number}, Sequence: ${clip.sequence_number}<br>
            Player: ${clip.player_name || clip.player_number || 'N/A'}<br>
            Type: ${clip.contact_type}<br>
            Outcome: ${clip.outcome}<br>
            Timecode: ${formatTimecode(clip.timecode_ms)}<br>
            <br>
            <strong>Video Path:</strong><br>
            ${checkResponse.absolute_path}<br>
            <small>Playing 6 seconds (3 seconds before and after timecode)</small>
        `;
        
        modal.style.display = 'block';
        
        // Set up playback for 6 seconds (3 seconds before to 3 seconds after timecode)
        const startTimeSeconds = clip.start_ms / 1000; // Should be timecode - 3 seconds
        const endTimeSeconds = (clip.start_ms + clip.duration_ms) / 1000; // Should be timecode + 3 seconds
        
        // Remove old event listeners by cloning (clean slate)
        const oldVideoPlayer = videoPlayer;
        const newVideoPlayer = videoPlayer.cloneNode(true);
        oldVideoPlayer.parentNode.replaceChild(newVideoPlayer, oldVideoPlayer);
        const updatedVideoPlayer = document.getElementById('video-player');
        
        // Set source
        updatedVideoPlayer.src = videoUrl;
        
        // Seek to start time and play when video is loaded
        const setupVideo = () => {
            updatedVideoPlayer.currentTime = startTimeSeconds;
            updatedVideoPlayer.play().catch(e => {
                console.error('Autoplay prevented:', e);
                // User might need to click play manually
            });
        };
        
        // Set up event listeners
        updatedVideoPlayer.addEventListener('loadedmetadata', () => {
            setupVideo();
        }, { once: true });
        
        // Stop playback at end time (6 seconds total)
        let timeUpdateHandler = () => {
            if (updatedVideoPlayer.currentTime >= endTimeSeconds) {
                updatedVideoPlayer.pause();
                updatedVideoPlayer.currentTime = startTimeSeconds; // Reset to start for replay
            }
        };
        
        updatedVideoPlayer.addEventListener('timeupdate', timeUpdateHandler);
        
        // Store handler for cleanup if needed
        updatedVideoPlayer._timeUpdateHandler = timeUpdateHandler;
        
    } catch (error) {
        console.error('Error checking video:', error);
        videoInfo.innerHTML = `
            <strong style="color: red;">Error checking video file:</strong><br>
            ${error.message}<br><br>
            <strong>Clip Info:</strong><br>
            Game: ${clip.game_alias}<br>
            Rally: ${clip.rally_number}, Sequence: ${clip.sequence_number}<br>
            Player: ${clip.player_name || clip.player_number || 'N/A'}<br>
            Type: ${clip.contact_type}<br>
            Outcome: ${clip.outcome}<br>
            Timecode: ${formatTimecode(clip.timecode_ms)}<br>
            <br>
            <strong>Video Path:</strong> ${videoPath}
        `;
        videoPlayer.src = '';
        modal.style.display = 'block';
    }
}

// Replay video clip
function replayClip() {
    if (state.currentVideoClip) {
        const videoPlayer = document.getElementById('video-player');
        const clip = state.currentVideoClip;
        
        const startTimeSeconds = clip.start_ms / 1000;
        videoPlayer.currentTime = startTimeSeconds;
        videoPlayer.play().catch(e => {
            console.error('Play prevented:', e);
            alert('Please click the play button manually to start playback');
        });
    }
}

function formatTimecode(ms) {
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
}

// Collection Management
async function loadCollections() {
    try {
        state.collections = await apiGet('/api/collections');
        renderCollections();
    } catch (error) {
        console.error('Error loading collections:', error);
    }
}

function renderCollections() {
    const select = document.getElementById('collection-select');
    select.innerHTML = '<option value="">-- Select Collection --</option>';
    
    state.collections.forEach(collection => {
        const option = document.createElement('option');
        option.value = collection.collection_id;
        option.textContent = collection.name;
        select.appendChild(option);
    });
}

async function loadCollection(collectionId) {
    try {
        const data = await apiGet(`/api/collections/${collectionId}`);
        state.currentCollection = data.collection;
        
        // First, capture current checkbox states for all displayed clips
        // This preserves selection state for clips that aren't in the loaded collection
        const currentCheckboxStates = new Map();
        document.querySelectorAll('#clip-table-body tr').forEach(row => {
            const checkbox = row.querySelector('input[type="checkbox"]');
            if (checkbox) {
                const contactId = parseInt(checkbox.dataset.contactId);
                const gameId = parseInt(checkbox.dataset.gameId);
                const key = `${gameId}-${contactId}`;
                currentCheckboxStates.set(key, checkbox.checked);
            }
        });
        
        // Also update state.currentClips to reflect current checkbox states
        state.currentClips.forEach(clip => {
            const key = `${clip.game_id}-${clip.contact_id}`;
            if (currentCheckboxStates.has(key)) {
                clip.is_selected = currentCheckboxStates.get(key);
            }
        });
        
        // Find the maximum order_index in current clips to continue numbering
        const maxOrderIndex = state.currentClips.length > 0 
            ? Math.max(...state.currentClips.map(c => c.order_index || 0))
            : -1;
        
        // Create a map of existing clips by (game_id, rally_number, sequence_number) for duplicate detection
        const existingClipsMap = new Map();
        state.currentClips.forEach(clip => {
            const key = `${clip.game_id}-${clip.rally_number}-${clip.sequence_number}`;
            existingClipsMap.set(key, clip);
        });
        
        // Create a set of clips that are in the loaded collection (for selection state updates)
        const loadedCollectionKeys = new Set();
        
        // Process loaded clips - check for duplicates and update selection state
        let newClipsCount = 0;
        data.clips.forEach((c) => {
            const key = `${c.game_id}-${c.rally_number}-${c.sequence_number}`;
            const existingClip = existingClipsMap.get(key);
            
            // Determine selection state from loaded collection
            const loadedSelectionState = c.is_selected === true || c.is_selected === 1 || c.is_selected === '1';
            
            // Mark this clip as being in the loaded collection
            loadedCollectionKeys.add(key);
            
            if (existingClip) {
                // Duplicate found - update the existing clip's selection state
                // The loaded collection's is_selected value supersedes the current checkbox state
                existingClip.is_selected = loadedSelectionState;
            } else {
                // New clip - add it to the list
                const newClip = {
                    ...c, 
                    order_index: (maxOrderIndex + 1) + newClipsCount, // Append after existing clips
                    is_selected: loadedSelectionState // Preserve selection state from collection
                };
                state.currentClips.push(newClip);
                existingClipsMap.set(key, newClip); // Add to map to prevent future duplicates in this batch
                newClipsCount++;
            }
        });
        
        // For clips that are NOT in the loaded collection, preserve their current selection state
        state.currentClips.forEach(clip => {
            const key = `${clip.game_id}-${clip.rally_number}-${clip.sequence_number}`;
            if (!loadedCollectionKeys.has(key)) {
                // This clip is not in the loaded collection, preserve its current selection state
                const checkboxKey = `${clip.game_id}-${clip.contact_id}`;
                if (currentCheckboxStates.has(checkboxKey)) {
                    clip.is_selected = currentCheckboxStates.get(checkboxKey);
                }
                // If no checkbox state was captured, keep the existing is_selected value
            }
        });
        
        // Set collection mode so filters don't overwrite collection clips
        state.isCollectionMode = true;
        
        document.getElementById('collection-name').value = data.collection.name;
        document.getElementById('collection-description').value = data.collection.description || '';
        
        renderClips();
    } catch (error) {
        console.error('Error loading collection:', error);
        alert('Failed to load collection: ' + error.message);
    }
}

async function saveCollection() {
    const name = document.getElementById('collection-name').value;
    if (!name) {
        alert('Please enter a collection name');
        return;
    }
    
    try {
        // Only save clips that are selected (checked)
        const selectedClipIds = new Set();
        document.querySelectorAll('#clip-table-body input[type="checkbox"]:checked').forEach(checkbox => {
            const contactId = parseInt(checkbox.dataset.contactId);
            const gameId = parseInt(checkbox.dataset.gameId);
            selectedClipIds.add(`${contactId}-${gameId}`);
        });
        
        // Filter to only include selected clips
        const selectedClips = state.currentClips.filter(c => 
            selectedClipIds.has(`${c.contact_id}-${c.game_id}`)
        ).map(c => ({
            contact_id: c.contact_id,
            game_id: c.game_id,
            ...c,
            is_selected: true // All saved clips are selected
        }));
        
        const collectionData = {
            name: name,
            description: document.getElementById('collection-description').value,
            clips: selectedClips // Only save selected clips
        };
        
        let collectionId;
        if (state.currentCollection && state.currentCollection.collection_id) {
            await apiPut(`/api/collections/${state.currentCollection.collection_id}`, collectionData);
            collectionId = state.currentCollection.collection_id;
        } else {
            const result = await apiPost('/api/collections', collectionData);
            collectionId = result.collection_id;
        }
        
        await loadCollections();
        document.getElementById('collection-select').value = collectionId;
        alert('Collection saved successfully');
    } catch (error) {
        console.error('Error saving collection:', error);
        alert('Failed to save collection: ' + error.message);
    }
}

async function deleteCollection() {
    const select = document.getElementById('collection-select');
    const collectionId = select.value;
    
    if (!collectionId) {
        alert('Please select a collection to delete');
        return;
    }
    
    if (!confirm('Are you sure you want to delete this collection?')) {
        return;
    }
    
    try {
        await apiDelete(`/api/collections/${collectionId}`);
        await loadCollections();
        state.currentCollection = null;
        document.getElementById('collection-name').value = '';
        document.getElementById('collection-description').value = '';
        select.value = '';
        alert('Collection deleted successfully');
    } catch (error) {
        console.error('Error deleting collection:', error);
        alert('Failed to delete collection: ' + error.message);
    }
}

// Create Highlight Video
async function createHighlightVideo() {
    const selectedClips = [];
    document.querySelectorAll('#clip-table-body input[type="checkbox"]:checked').forEach(checkbox => {
        const contactId = parseInt(checkbox.dataset.contactId);
        const gameId = parseInt(checkbox.dataset.gameId);
        const clip = state.currentClips.find(c => 
            c.contact_id === contactId && c.game_id === gameId
        );
        if (clip) {
            selectedClips.push(clip);
        }
    });
    
    if (selectedClips.length === 0) {
        alert('Please select at least one clip');
        return;
    }
    
    const includeTitle = document.getElementById('include-title-checkbox').checked;
    
    try {
        const result = await apiPost('/api/highlight-video', {
            clips: selectedClips,
            include_title: includeTitle
        });
        
        const jobId = result.job_id;
        const progressDiv = document.getElementById('video-progress');
        const resultDiv = document.getElementById('video-result');
        const progressFill = document.getElementById('progress-fill');
        const progressText = document.getElementById('progress-text');
        
        progressDiv.style.display = 'block';
        resultDiv.style.display = 'none';
        
        // Poll for status
        const pollInterval = setInterval(async () => {
            try {
                const status = await apiGet(`/api/highlight-video/${jobId}/status`);
                
                const progress = (status.progress / status.total) * 100;
                progressFill.style.width = `${progress}%`;
                progressText.textContent = `Processing: ${status.progress} / ${status.total}`;
                
                if (status.status === 'completed') {
                    clearInterval(pollInterval);
                    progressDiv.style.display = 'none';
                    resultDiv.style.display = 'block';
                    
                    const downloadLink = document.getElementById('video-download-link');
                    downloadLink.href = `/api/videos/${status.output_path}`;
                    downloadLink.download = status.output_path; // Force download instead of playing
                    downloadLink.textContent = `Download: ${status.output_path}`;
                } else if (status.status === 'failed') {
                    clearInterval(pollInterval);
                    progressDiv.style.display = 'none';
                    alert('Video generation failed: ' + (status.error || 'Unknown error'));
                }
            } catch (error) {
                console.error('Error polling video status:', error);
            }
        }, 1000);
    } catch (error) {
        console.error('Error creating highlight video:', error);
        alert('Failed to create highlight video: ' + error.message);
    }
}

// Event Listeners
document.addEventListener('DOMContentLoaded', () => {
    // Game search
    document.getElementById('game-search').addEventListener('input', renderGames);
    
    // Apply filters button
    document.getElementById('apply-filters-btn').addEventListener('click', () => {
        // Exit collection mode when applying filters
        state.isCollectionMode = false;
        loadPlayers();
        loadClips();
    });
    
    // Contact types - show ratings filter when Receive is selected
    document.querySelectorAll('#contact-types-grid input[type="checkbox"]').forEach(cb => {
        cb.addEventListener('change', () => {
            const receiveSelected = document.querySelector('#contact-types-grid input[value="receive"]').checked;
            document.getElementById('ratings-filter-group').style.display = 
                receiveSelected ? 'block' : 'none';
        });
    });
    
    // Collection management
    document.getElementById('collection-select').addEventListener('change', (e) => {
        if (e.target.value) {
            loadCollection(parseInt(e.target.value));
            document.getElementById('collection-info').style.display = 'block';
        } else {
            document.getElementById('collection-info').style.display = 'none';
        }
    });
    
    document.getElementById('new-collection-btn').addEventListener('click', () => {
        state.currentCollection = null;
        state.isCollectionMode = false; // Exit collection mode for new collection
        document.getElementById('collection-name').value = '';
        document.getElementById('collection-description').value = '';
        document.getElementById('collection-select').value = '';
        document.getElementById('collection-info').style.display = 'block';
    });
    
    document.getElementById('save-collection-btn').addEventListener('click', saveCollection);
    
    document.getElementById('load-collection-btn').addEventListener('click', () => {
        const select = document.getElementById('collection-select');
        if (select.value) {
            loadCollection(parseInt(select.value));
            document.getElementById('collection-info').style.display = 'block';
        }
    });
    
    document.getElementById('delete-collection-btn').addEventListener('click', deleteCollection);
    
    // Highlight video
    document.getElementById('create-highlight-btn').addEventListener('click', createHighlightVideo);
    document.getElementById('configure-title-btn').addEventListener('click', () => {
        window.open('/title-builder', '_blank');
    });
    
    // Modal close - stop video and pause
    function closeVideoModal() {
        const modal = document.getElementById('video-modal');
        const videoPlayer = document.getElementById('video-player');
        
        // Stop video completely
        videoPlayer.pause();
        videoPlayer.currentTime = 0;
        videoPlayer.src = '';
        videoPlayer.load();
        
        // Remove event listeners if they exist
        if (videoPlayer._timeUpdateHandler) {
            videoPlayer.removeEventListener('timeupdate', videoPlayer._timeUpdateHandler);
            videoPlayer._timeUpdateHandler = null;
        }
        
        state.currentVideoClip = null;
        modal.style.display = 'none';
    }
    
    document.querySelector('.modal-close').addEventListener('click', closeVideoModal);
    
    window.addEventListener('click', (e) => {
        const modal = document.getElementById('video-modal');
        if (e.target === modal) {
            closeVideoModal();
        }
    });
    
    // Replay button
    document.getElementById('replay-btn').addEventListener('click', replayClip);
    
    // Select all checkbox
    document.getElementById('select-all-checkbox').addEventListener('change', (e) => {
        document.querySelectorAll('#clip-table-body input[type="checkbox"]').forEach(cb => {
            cb.checked = e.target.checked;
        });
    });
    
    // Initial load
    loadGames();
    loadCollections();
});
