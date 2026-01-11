"""
Flask API routes for highlight collection manager.
"""

import threading
import uuid
import re
import urllib.parse
from pathlib import Path
from datetime import datetime
from flask import Blueprint, request, jsonify, g, send_file, Response, current_app
from typing import Dict, List

from database import VideoStatsDB
from services.clip_service import ClipService
from services.collection_service import CollectionService
from services.filter_service import FilterService
from services.video_service import VideoService
from models.clip_models import VideoClip, ClipCollection
from utils import get_database_path

api = Blueprint('highlight_manager', __name__)

# Video generation job storage (in-memory for now)
video_jobs = {}
video_jobs_lock = threading.Lock()


def get_db():
    """Get database connection for current request."""
    if 'db' not in g:
        g.db = VideoStatsDB(str(get_database_path()))
        g.db.initialize_database()
        g.db.connect()
        g.db.create_collection_tables()
        # Ensure is_selected column exists (migration)
        try:
            cursor = g.db.conn.cursor()
            cursor.execute("PRAGMA table_info(collection_clips)")
            columns = [row[1] for row in cursor.fetchall()]
            if 'is_selected' not in columns:
                cursor.execute("ALTER TABLE collection_clips ADD COLUMN is_selected INTEGER DEFAULT 0")
                g.db.conn.commit()
        except Exception as e:
            # Column might already exist, ignore error
            g.db.conn.rollback()
    return g.db


def get_services():
    """Get service instances for current request."""
    db = get_db()
    return {
        'clip_service': ClipService(db),
        'collection_service': CollectionService(db),
        'filter_service': FilterService()
    }


@api.teardown_app_request
def close_db(error):
    """Close database connection after request."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


@api.route('/api/games', methods=['GET'])
def get_games():
    """Get list of all games."""
    try:
        clip_service = get_services()['clip_service']
        games = clip_service.get_games_list()
        return jsonify(games)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api.route('/api/clips', methods=['POST'])
def get_clips():
    """
    Get filtered clips from one or more games.
    Request body: {game_ids: [1, 2, 3], filters: {...}}
    """
    try:
        data = request.json or {}
        game_ids = data.get('game_ids', [])
        filters_dict = data.get('filters', {})
        
        if not game_ids:
            return jsonify([])
        
        services = get_services()
        filter_service = services['filter_service']
        clip_service = services['clip_service']
        
        # Validate filters
        validated_filters = filter_service.validate_filters(filters_dict)
        
        # Get clips
        clips = clip_service.get_filtered_clips(game_ids, validated_filters)
        
        # Convert to dictionaries
        return jsonify([clip.to_dict() for clip in clips])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api.route('/api/collections', methods=['GET', 'POST'])
def collections():
    """
    List or create collections.
    GET: Returns list of all collections
    POST: Creates a new collection
    """
    try:
        collection_service = get_services()['collection_service']
        
        if request.method == 'GET':
            collections = collection_service.list_collections()
            return jsonify([c.to_dict() for c in collections])
        else:
            # POST - Create new collection
            data = request.json or {}
            name = data.get('name', '')
            if not name:
                return jsonify({'error': 'Collection name is required'}), 400
            
            description = data.get('description')
            clips_data = data.get('clips', [])
            
            # Create collection
            collection = collection_service.create_collection(name, description)
            
            # Convert clip dictionaries to VideoClip objects, preserving is_selected
            clips = []
            for c in clips_data if clips_data else []:
                clip = VideoClip.from_dict(c)
                # Preserve is_selected from dict (not part of VideoClip model)
                if 'is_selected' in c:
                    clip.is_selected = c['is_selected']
                clips.append(clip)
            
            # Save collection
            collection_id = collection_service.save_collection(collection, clips)
            
            return jsonify({'collection_id': collection_id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api.route('/api/collections/<int:collection_id>', methods=['GET', 'PUT', 'DELETE'])
def collection(collection_id):
    """
    Get, update, or delete a collection.
    """
    try:
        collection_service = get_services()['collection_service']
        
        if request.method == 'GET':
            try:
                collection, clips = collection_service.load_collection(collection_id)
                # Include is_selected in clip dicts even though it's not part of VideoClip model
                clip_dicts = []
                for clip in clips:
                    clip_dict = clip.to_dict()
                    # Add is_selected if it exists as an attribute, default to True (all loaded clips should be selected)
                    if hasattr(clip, 'is_selected'):
                        clip_dict['is_selected'] = clip.is_selected
                    else:
                        clip_dict['is_selected'] = True  # Default to True - all loaded clips are selected
                    clip_dicts.append(clip_dict)
                return jsonify({
                    'collection': collection.to_dict(),
                    'clips': clip_dicts
                })
            except Exception as e:
                import traceback
                error_trace = traceback.format_exc()
                print(f"Error loading collection {collection_id}: {e}")
                print(error_trace)
                return jsonify({'error': f'Failed to load collection: {str(e)}', 'traceback': error_trace}), 500
        elif request.method == 'PUT':
            data = request.json or {}
            name = data.get('name', '')
            if not name:
                return jsonify({'error': 'Collection name is required'}), 400
            
            description = data.get('description')
            clips_data = data.get('clips', [])
            
            # Load existing collection to preserve created_at
            try:
                existing_collection, _ = collection_service.load_collection(collection_id)
                collection = ClipCollection(
                    collection_id=collection_id,
                    name=name,
                    description=description,
                    created_at=existing_collection.created_at,
                    clip_ids=[]
                )
            except ValueError:
                return jsonify({'error': 'Collection not found'}), 404
            
            # Convert clip dictionaries to VideoClip objects, preserving is_selected
            clips = []
            for c in clips_data if clips_data else []:
                clip = VideoClip.from_dict(c)
                # Preserve is_selected from dict (not part of VideoClip model)
                if 'is_selected' in c:
                    clip.is_selected = c['is_selected']
                clips.append(clip)
            
            # Save collection
            collection_service.save_collection(collection, clips)
            return jsonify({'success': True})
        else:
            # DELETE
            success = collection_service.delete_collection(collection_id)
            if success:
                return jsonify({'success': True})
            else:
                return jsonify({'error': 'Collection not found'}), 404
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api.route('/api/clips/<int:contact_id>/<int:game_id>/star-rating', methods=['PUT'])
def update_star_rating(contact_id, game_id):
    """
    Update star rating for a clip.
    Request body: {star_rating: 1-5}
    """
    try:
        data = request.json or {}
        star_rating = data.get('star_rating')
        
        if star_rating is None or not (1 <= star_rating <= 5):
            return jsonify({'error': 'star_rating must be between 1 and 5'}), 400
        
        clip_service = get_services()['clip_service']
        success = clip_service.update_clip_star_rating(contact_id, game_id, star_rating)
        
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Failed to update star rating'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api.route('/api/highlight-video', methods=['POST'])
def create_highlight_video():
    """
    Generate highlight video from selected clips (async).
    Request body: {clips: [...], include_title: bool, title_path: str}
    Returns job_id for status polling
    """
    try:
        data = request.json or {}
        clips_data = data.get('clips', [])
        include_title = data.get('include_title', False)
        
        if not clips_data:
            return jsonify({'error': 'No clips provided'}), 400
        
        # Handle title path - use fixed title.mp4 in video_clips folder
        title_path = None
        if include_title:
            title_path_obj = Path("video_clips") / "title.mp4"
            if not title_path_obj.exists():
                return jsonify({
                    'error': 'Title video not found. Please generate a title video first.',
                    'title_path': str(title_path_obj)
                }), 400
            title_path = str(title_path_obj)
        
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        # Create output directory
        output_dir = Path("video_clips")
        output_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        highlight_filename = f"highlight_{timestamp}.mp4"
        
        # Initialize job status
        with video_jobs_lock:
            video_jobs[job_id] = {
                'status': 'pending',
                'progress': 0,
                'total': len(clips_data) + (1 if include_title else 0) + 1,  # clips + title (if any) + concatenation
                'output_path': None,
                'error': None
            }
        
        # Start async video generation
        def generate_video():
            try:
                with video_jobs_lock:
                    video_jobs[job_id]['status'] = 'processing'
                
                # Convert clip dictionaries to VideoClip objects if needed
                clips = []
                for clip_data in clips_data:
                    if isinstance(clip_data, dict):
                        clips.append(VideoClip.from_dict(clip_data))
                    else:
                        clips.append(clip_data)
                
                # Progress callback
                def progress_callback(current, total):
                    with video_jobs_lock:
                        if job_id in video_jobs:
                            video_jobs[job_id]['progress'] = current
                            video_jobs[job_id]['total'] = total
                
                # Generate video
                result_path = VideoService.create_highlight_from_clips(
                    clips,
                    output_dir,
                    highlight_filename,
                    include_title,
                    title_path,
                    progress_callback
                )
                
                with video_jobs_lock:
                    if job_id in video_jobs:
                        if result_path:
                            video_jobs[job_id]['status'] = 'completed'
                            video_jobs[job_id]['output_path'] = str(result_path)
                            video_jobs[job_id]['progress'] = video_jobs[job_id]['total']
                        else:
                            video_jobs[job_id]['status'] = 'failed'
                            video_jobs[job_id]['error'] = 'Video generation failed'
            except Exception as e:
                with video_jobs_lock:
                    if job_id in video_jobs:
                        video_jobs[job_id]['status'] = 'failed'
                        video_jobs[job_id]['error'] = str(e)
        
        thread = threading.Thread(target=generate_video)
        thread.daemon = True
        thread.start()
        
        return jsonify({'job_id': job_id}), 202
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api.route('/api/highlight-video/<job_id>/status', methods=['GET'])
def get_video_status(job_id):
    """Get status of video generation job."""
    try:
        with video_jobs_lock:
            if job_id not in video_jobs:
                return jsonify({'error': 'Job not found'}), 404
            
            job = video_jobs[job_id].copy()
            
            # Return relative path for video
            if job.get('output_path'):
                job['output_path'] = Path(job['output_path']).name
            
            return jsonify(job)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api.route('/api/videos/<filename>', methods=['GET'])
def serve_video(filename):
    """Serve generated video files for download."""
    try:
        video_path = Path("video_clips") / filename
        if not video_path.exists():
            return jsonify({'error': 'Video not found'}), 404
        
        return send_file(str(video_path), mimetype='video/mp4', as_attachment=True, download_name=filename)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api.route('/api/source-video', methods=['GET'])
def serve_source_video():
    """Serve source video files with range request support for seeking."""
    try:
        # Get video path from query parameter
        video_path_encoded = request.args.get('path')
        if not video_path_encoded:
            return jsonify({'error': 'Video path is required'}), 400
        
        # Decode the path
        video_path = urllib.parse.unquote(video_path_encoded)
        video_path_obj = Path(video_path)
        
        # Check if file exists
        if not video_path_obj.exists():
            return jsonify({
                'error': 'Video file not found',
                'path': str(video_path_obj),
                'absolute_path': str(video_path_obj.absolute())
            }), 404
        
        # Check if it's a file (not a directory)
        if not video_path_obj.is_file():
            return jsonify({'error': 'Path is not a file'}), 400
        
        # Support range requests for video seeking
        range_header = request.headers.get('Range', None)
        if not range_header:
            return send_file(
                str(video_path_obj),
                mimetype='video/mp4',
                as_attachment=False
            )
        
        # Handle range requests
        file_size = video_path_obj.stat().st_size
        byte1 = 0
        byte2 = file_size - 1
        
        # Parse range header (e.g., "bytes=0-1023")
        match = re.search(r'(\d+)-(\d*)', range_header)
        if match:
            byte1 = int(match.group(1)) if match.group(1) else byte1
            byte2 = int(match.group(2)) if match.group(2) else byte2
        
        length = byte2 - byte1 + 1
        
        with open(video_path_obj, 'rb') as f:
            f.seek(byte1)
            data = f.read(length)
        
        response = Response(
            data,
            206,  # Partial Content
            mimetype='video/mp4',
            direct_passthrough=False
        )
        response.headers.add('Content-Range', f'bytes {byte1}-{byte2}/{file_size}')
        response.headers.add('Accept-Ranges', 'bytes')
        response.headers.add('Content-Length', str(length))
        
        return response
        
    except Exception as e:
        import traceback
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@api.route('/api/check-video', methods=['GET'])
def check_video_exists():
    """Check if a video file exists on the filesystem."""
    try:
        video_path_encoded = request.args.get('path')
        if not video_path_encoded:
            return jsonify({'error': 'Video path is required'}), 400
        
        video_path = urllib.parse.unquote(video_path_encoded)
        video_path_obj = Path(video_path)
        
        exists = video_path_obj.exists()
        is_file = video_path_obj.is_file() if exists else False
        
        return jsonify({
            'exists': exists,
            'is_file': is_file,
            'path': str(video_path_obj),
            'absolute_path': str(video_path_obj.absolute())
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api.route('/api/games/<int:game_id>/players', methods=['GET'])
def get_game_players(game_id):
    """Get players for a game (both teams)."""
    try:
        db = get_db()
        
        # Get team IDs for the game
        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT team_us_id, team_them_id
            FROM games
            WHERE game_id = ?
        """, (game_id,))
        
        result = cursor.fetchone()
        if not result:
            return jsonify({'error': 'Game not found'}), 404
        
        team_us_id = result['team_us_id']
        team_them_id = result['team_them_id']
        
        # Get players for both teams
        players_us = db.get_game_players(game_id, team_us_id)
        players_them = db.get_game_players(game_id, team_them_id)
        
        return jsonify({
            'team_us': [
                {
                    'player_id': p['player_id'],
                    'player_number': p['player_number'],
                    'name': p['name'],
                    'team_id': team_us_id
                }
                for p in players_us
            ],
            'team_them': [
                {
                    'player_id': p['player_id'],
                    'player_number': p['player_number'],
                    'name': p['name'],
                    'team_id': team_them_id
                }
                for p in players_them
            ]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
