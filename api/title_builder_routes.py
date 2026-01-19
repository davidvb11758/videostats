"""API routes for title builder functionality."""
from flask import Blueprint, request, jsonify, send_file
from io import BytesIO
import base64
import json
import tempfile
from pathlib import Path
from services.image_service import generate_image
from services.font_service import get_available_fonts, WINDOWS_FONTS
from models.config import VideoSettings
from services.video_service import VideoService

title_builder_api = Blueprint('title_builder', __name__, url_prefix='/api/title-builder')


@title_builder_api.route('/fonts', methods=['GET'])
def get_fonts():
    """Get list of available fonts."""
    fonts = get_available_fonts()
    return jsonify({"fonts": fonts})


@title_builder_api.route('/preview', methods=['POST'])
def preview():
    """Generate preview image and return as base64."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        # Validate settings
        settings = VideoSettings.from_dict(data)
        is_valid, error_msg = settings.validate()
        if not is_valid:
            return jsonify({"success": False, "error": error_msg}), 400
        
        # Generate image
        img = generate_image(settings.to_dict())
        
        # Convert to base64
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        img_bytes = buffer.getvalue()
        img_base64 = base64.b64encode(img_bytes).decode('utf-8')
        
        return jsonify({
            "success": True,
            "image": f"data:image/png;base64,{img_base64}"
        })
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": f"An error occurred: {str(e)}"}), 500


@title_builder_api.route('/export', methods=['POST'])
def export_settings():
    """Export settings as JSON file download."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        # Validate and convert to settings
        settings = VideoSettings.from_dict(data)
        
        # Convert to JSON string
        json_str = json.dumps(settings.to_dict(), indent=4, ensure_ascii=False)
        
        # Create file-like object
        json_bytes = json_str.encode('utf-8')
        json_file = BytesIO(json_bytes)
        
        return send_file(
            json_file,
            mimetype='application/json',
            as_attachment=True,
            download_name='settings.json'
        )
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to export settings: {str(e)}"}), 500


@title_builder_api.route('/import', methods=['POST'])
def import_settings():
    """Import settings from JSON file."""
    try:
        if 'file' not in request.files:
            return jsonify({"success": False, "error": "No file provided"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"success": False, "error": "No file selected"}), 400
        
        # Read JSON file
        file_content = file.read().decode('utf-8')
        data = json.loads(file_content)
        
        # Validate structure
        if "background_color" not in data or "lines" not in data:
            return jsonify({"success": False, "error": "Invalid JSON file format. Missing required fields."}), 400
        
        if len(data["lines"]) != 4:
            return jsonify({"success": False, "error": "JSON file must contain exactly 4 lines."}), 400
        
        # Handle backward compatibility with font names ending in " Bold"
        for line_data in data["lines"]:
            font_style = line_data.get("font_style", "Arial")
            if font_style.endswith(" Bold"):
                base_font = font_style[:-5]  # Remove " Bold" suffix
                if base_font in WINDOWS_FONTS:
                    line_data["font_style"] = base_font
                    # Set bold if not already set
                    if not line_data.get("font_bold", False):
                        line_data["font_bold"] = True
                else:
                    line_data["font_style"] = "Arial"
            elif font_style not in get_available_fonts():
                line_data["font_style"] = "Arial"
        
        # Validate font sizes
        for i, line_data in enumerate(data["lines"]):
            font_size = line_data.get("font_size", 30)
            if not (8 <= font_size <= 200):
                line_data["font_size"] = 30
        
        # Convert to settings and back to dict for response
        settings = VideoSettings.from_dict(data)
        
        return jsonify({
            "success": True,
            "settings": settings.to_dict()
        })
    except json.JSONDecodeError as e:
        return jsonify({"success": False, "error": f"Invalid JSON file: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to import settings: {str(e)}"}), 500


@title_builder_api.route('/generate-video', methods=['POST'])
def generate_video():
    """Generate title video from settings and save as video_clips/title.mp4."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        # Validate settings
        settings = VideoSettings.from_dict(data)
        is_valid, error_msg = settings.validate()
        if not is_valid:
            return jsonify({"success": False, "error": error_msg}), 400
        
        # Generate image
        img = generate_image(settings.to_dict())
        
        # Create temporary file for the image
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_img:
            img.save(temp_img.name, format='PNG')
            temp_image_path = temp_img.name
        
        try:
            # Ensure video_clips directory exists
            video_clips_dir = Path("video_clips")
            video_clips_dir.mkdir(exist_ok=True)
            
            # Output path for title video
            output_path = video_clips_dir / "title.mp4"
            
            # Convert image to video
            # Default: 5 seconds duration, 30 fps
            duration = data.get('duration', 5.0)
            fps = data.get('fps', 30)
            
            success = VideoService.create_title_video(
                temp_image_path,
                str(output_path),
                duration=duration,
                fps=fps
            )
            
            if success:
                return jsonify({
                    "success": True,
                    "message": "Title video generated successfully",
                    "path": str(output_path)
                })
            else:
                return jsonify({
                    "success": False,
                    "error": "Failed to generate title video"
                }), 500
                
        finally:
            # Clean up temporary image file
            try:
                Path(temp_image_path).unlink()
            except Exception:
                pass  # Ignore cleanup errors
                
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": f"An error occurred: {str(e)}"}), 500

