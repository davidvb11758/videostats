CREATE DATABASE videstats;

-- PostgreSQL Database Schema for VideoStats
-- Converted from SQLite schema

-- clip_collections definition

CREATE TABLE clip_collections (
    collection_id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- clip_star_ratings definition

CREATE TABLE clip_star_ratings (
    contact_id INTEGER NOT NULL,
    game_id INTEGER NOT NULL,
    star_rating INTEGER CHECK(star_rating >= 1 AND star_rating <= 5),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (contact_id, game_id)
);


-- positions definition

CREATE TABLE positions (
    number INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    abbrev TEXT NOT NULL,
    row TEXT NOT NULL CHECK(row IN ('Front', 'Back')),
    side TEXT NOT NULL CHECK(side IN ('Left', 'Middle', 'Right')),
    x INTEGER NOT NULL,
    y INTEGER NOT NULL
);


-- teams definition

CREATE TABLE teams (
    team_id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- collection_clips definition

CREATE TABLE collection_clips (
    collection_id INTEGER,
    contact_id INTEGER,
    game_id INTEGER,
    order_index INTEGER NOT NULL,
    is_selected INTEGER DEFAULT 0,
    FOREIGN KEY (collection_id) REFERENCES clip_collections(collection_id) ON DELETE CASCADE,
    PRIMARY KEY (collection_id, contact_id, game_id)
);


-- games definition

CREATE TABLE games (
    game_id SERIAL PRIMARY KEY,
    game_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    team_us_id INTEGER NOT NULL,
    team_them_id INTEGER NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    video_file_path TEXT,
    court_corner_tl_x REAL,
    court_corner_tl_y REAL,
    court_corner_tr_x REAL,
    court_corner_tr_y REAL,
    court_corner_bl_x REAL,
    court_corner_bl_y REAL,
    court_corner_br_x REAL,
    court_corner_br_y REAL,
    court_centerline_top_x REAL,
    court_centerline_top_y REAL,
    court_centerline_bottom_x REAL,
    court_centerline_bottom_y REAL,
    still_image_path TEXT,
    court_y200_left_x REAL,
    court_y200_left_y REAL,
    court_y200_right_x REAL,
    court_y200_right_y REAL,
    court_y400_left_x REAL,
    court_y400_left_y REAL,
    court_y400_right_x REAL,
    court_y400_right_y REAL,
    homography_matrix TEXT,
    scroll_offset_x INTEGER DEFAULT 0,
    scroll_offset_y INTEGER DEFAULT 0,
    video_offset_x INTEGER DEFAULT 0,
    video_offset_y INTEGER DEFAULT 0,
    video_width REAL DEFAULT 0,
    video_height REAL DEFAULT 0,
    scene_width REAL DEFAULT 0,
    scene_height REAL DEFAULT 0,
    is_ended BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (team_us_id) REFERENCES teams(team_id),
    FOREIGN KEY (team_them_id) REFERENCES teams(team_id)
);


-- players definition

CREATE TABLE players (
    player_id SERIAL PRIMARY KEY,
    team_id INTEGER NOT NULL,
    player_number TEXT NOT NULL,
    name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    role_code TEXT NOT NULL,
    is_active BOOLEAN DEFAULT FALSE,
    jersey TEXT NOT NULL,
    FOREIGN KEY (team_id) REFERENCES teams(team_id),
    FOREIGN KEY (role_code) REFERENCES player_roles(role_code),
    UNIQUE(team_id, player_number)
);

CREATE INDEX idx_players_team ON players(team_id);


-- rallies definition

CREATE TABLE rallies (
    rally_id SERIAL PRIMARY KEY,
    game_id INTEGER NOT NULL,
    rally_number INTEGER NOT NULL,
    serving_team_id INTEGER NOT NULL,
    point_winner_id INTEGER,
    rally_start_time TIMESTAMP,
    rally_end_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (game_id) REFERENCES games(game_id),
    FOREIGN KEY (serving_team_id) REFERENCES teams(team_id),
    FOREIGN KEY (point_winner_id) REFERENCES teams(team_id),
    UNIQUE(game_id, rally_number)
);

CREATE INDEX idx_rallies_game ON rallies(game_id);


-- rotation_state definition

CREATE TABLE rotation_state (
    team_id INTEGER PRIMARY KEY REFERENCES teams(team_id),
    rotation_order TEXT NOT NULL, -- JSON array e.g. [1,6,5,4,3,2]
    rotation_index INTEGER NOT NULL DEFAULT 0,
    serving BOOLEAN DEFAULT FALSE,
    term_of_service_start TIMESTAMP NULL,
    game_id INTEGER REFERENCES games(game_id)
);

CREATE INDEX idx_rotation_state_game ON rotation_state(game_id);
CREATE INDEX idx_rotation_state_team ON rotation_state(team_id);


-- substitutions definition

CREATE TABLE substitutions (
    id SERIAL PRIMARY KEY,
    team_id INTEGER NOT NULL REFERENCES teams(team_id),
    out_player_id INTEGER NOT NULL REFERENCES players(player_id),
    in_player_id INTEGER NOT NULL REFERENCES players(player_id),
    out_position INTEGER NULL,
    in_position INTEGER NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    game_id INTEGER REFERENCES games(game_id)
);

CREATE INDEX idx_substitutions_team ON substitutions(team_id);
CREATE INDEX idx_substitutions_game ON substitutions(game_id);


-- active_lineup definition

CREATE TABLE active_lineup (
    id SERIAL PRIMARY KEY,
    game_id INTEGER NOT NULL REFERENCES games(game_id) ON DELETE CASCADE,
    team_id INTEGER NOT NULL REFERENCES teams(team_id),
    position_number INTEGER NOT NULL REFERENCES positions(number),
    player_id INTEGER NOT NULL REFERENCES players(player_id),
    role_code TEXT NOT NULL,
    is_server BOOLEAN DEFAULT FALSE,
    placed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(game_id, team_id, position_number)
);

CREATE INDEX idx_active_lineup_game ON active_lineup(game_id);
CREATE INDEX idx_active_lineup_team ON active_lineup(team_id);
CREATE INDEX idx_active_lineup_player ON active_lineup(player_id);


-- contacts definition

CREATE TABLE contacts (
    contact_id SERIAL PRIMARY KEY,
    rally_id INTEGER NOT NULL,
    sequence_number INTEGER NOT NULL,
    player_id INTEGER,
    contact_type TEXT NOT NULL CHECK(contact_type IN ('serve', 'pass', 'set', 'attack', 'block', 'receive', 'freeball', 'down', 'net')),
    team_id INTEGER NOT NULL,
    x INTEGER,
    y INTEGER,
    timecode INTEGER,
    outcome TEXT DEFAULT 'continue' CHECK(outcome IN ('continue', 'ace', 'kill', 'error', 'down', 'stuff', 'assist', 'fault')),
    rating INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    outcome_manual INTEGER DEFAULT 0,
    rating_manual INTEGER DEFAULT 0,
    FOREIGN KEY (rally_id) REFERENCES rallies(rally_id),
    FOREIGN KEY (player_id) REFERENCES players(player_id),
    FOREIGN KEY (team_id) REFERENCES teams(team_id)
);

CREATE INDEX idx_contacts_rally ON contacts(rally_id);
CREATE INDEX idx_contacts_player ON contacts(player_id);
CREATE INDEX idx_contacts_type ON contacts(contact_type);


-- events definition

CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    game_id INTEGER NOT NULL REFERENCES games(game_id),
    team_id INTEGER NOT NULL REFERENCES teams(team_id),
    event_type TEXT NOT NULL CHECK(event_type IN ('rotation', 'substitution', 'libero', 'server_change', 'initial_setup', 'contact', 'point_awarded')),
    payload TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_events_game ON events(game_id);
CREATE INDEX idx_events_team ON events(team_id);
CREATE INDEX idx_events_type ON events(event_type);


-- game_players definition

CREATE TABLE game_players (
    game_player_id SERIAL PRIMARY KEY,
    game_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    game_role_code TEXT NOT NULL,
    FOREIGN KEY (game_id) REFERENCES games(game_id) ON DELETE CASCADE,
    FOREIGN KEY (team_id) REFERENCES teams(team_id),
    FOREIGN KEY (player_id) REFERENCES players(player_id),
    UNIQUE(game_id, team_id, player_id)
);

CREATE INDEX idx_game_players_game ON game_players(game_id);
CREATE INDEX idx_game_players_team ON game_players(team_id);
CREATE INDEX idx_game_players_player ON game_players(player_id);


-- libero_actions definition

CREATE TABLE libero_actions (
    id SERIAL PRIMARY KEY,
    team_id INTEGER NOT NULL REFERENCES teams(team_id),
    libero_id INTEGER NOT NULL REFERENCES players(player_id),
    replaced_player_id INTEGER NOT NULL REFERENCES players(player_id),
    replaced_position INTEGER NOT NULL,
    action TEXT NOT NULL CHECK(action IN ('enter', 'exit')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    game_id INTEGER REFERENCES games(game_id)
);

CREATE INDEX idx_libero_actions_team ON libero_actions(team_id);
CREATE INDEX idx_libero_actions_game ON libero_actions(game_id);


-- player_stats definition

CREATE TABLE player_stats (
    stat_id SERIAL PRIMARY KEY,
    game_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    -- Receive statistics
    receive_attempts INTEGER DEFAULT 0,
    receive_0 INTEGER DEFAULT 0,
    receive_1 INTEGER DEFAULT 0,
    receive_2 INTEGER DEFAULT 0,
    receive_3 INTEGER DEFAULT 0,
    receive_avg_rating REAL DEFAULT 0.0,
    -- Attack statistics
    attack_attempts INTEGER DEFAULT 0,
    attack_kills INTEGER DEFAULT 0,
    attack_errors INTEGER DEFAULT 0,
    attack_kill_pct REAL DEFAULT 0.0,
    attack_hitting_pct REAL DEFAULT 0.0,
    attack_efficiency REAL DEFAULT 0.0,
    -- Set statistics
    set_attempts INTEGER DEFAULT 0,
    set_assists INTEGER DEFAULT 0,
    -- Serve statistics
    serve_attempts INTEGER DEFAULT 0,
    serve_aces INTEGER DEFAULT 0,
    serve_errors INTEGER DEFAULT 0,
    serve_ace_pct REAL DEFAULT 0.0,
    serve_in_pct REAL DEFAULT 0.0,
    -- Dig statistics
    dig_attempts INTEGER DEFAULT 0,
    dig_successful INTEGER DEFAULT 0,
    -- Block statistics
    block_solo INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (game_id) REFERENCES games(game_id) ON DELETE CASCADE,
    FOREIGN KEY (player_id) REFERENCES players(player_id),
    UNIQUE(game_id, player_id)
);

CREATE INDEX idx_player_stats_game ON player_stats(game_id);
CREATE INDEX idx_player_stats_player ON player_stats(player_id);


CREATE TABLE player_roles (
    role_id SERIAL PRIMARY KEY,
    role_code TEXT NOT NULL,
    role_description TEXT NOT NULL
);

INSERT INTO player_roles(role_code, role_description) values ('S', 'Setter');
INSERT INTO player_roles(role_code, role_description) values ('OH', 'Outside Hitter');
INSERT INTO player_roles(role_code, role_description) values ('Lib', 'Libero');
INSERT INTO player_roles(role_code, role_description) values ('MH', 'Middle Hitter');
INSERT INTO player_roles(role_code, role_description) values ('RS', 'Rightside Hitter');
INSERT INTO player_roles(role_code, role_description) values ('OTH', 'Other');