"""Image generation service for creating text images."""
import os
from PIL import Image, ImageDraw, ImageFont
from typing import Dict, Any, Optional
from services.font_service import get_font_path

# Video dimensions
WIDTH = 1920
HEIGHT = 1080
LINE_SPACING = 40


def generate_image(settings: Dict[str, Any]) -> Image.Image:
    """
    Generate a PIL Image based on the provided settings.
    
    Args:
        settings: Dictionary containing:
            - background_color: {"r": int, "g": int, "b": int}
            - lines: List of 4 line dictionaries, each with:
                - text: str
                - color: {"r": int, "g": int, "b": int}
                - font_style: str
                - font_size: int
                - font_bold: bool
                - font_italic: bool
    
    Returns:
        PIL Image object
        
    Raises:
        ValueError: If no valid text lines are provided
        Exception: If image generation fails
    """
    # Extract settings
    bg_color = settings.get("background_color", {"r": 40, "g": 40, "b": 40})
    bg_color_rgb = (bg_color["r"], bg_color["g"], bg_color["b"])
    
    lines_data = settings.get("lines", [])
    
    # Get text lines and filter empty ones
    valid_lines = []
    for i, line_data in enumerate(lines_data):
        text = line_data.get("text", "").strip()
        if text:
            valid_lines.append((i, line_data))
    
    # Check if at least one line has text
    if not valid_lines:
        raise ValueError("Please enter at least one line of text.")
    
    # Create image
    img = Image.new("RGB", (WIDTH, HEIGHT), color=bg_color_rgb)
    draw = ImageDraw.Draw(img)
    
    # First pass: calculate all text heights and positions for vertical centering
    text_heights = []
    fonts = []
    processed_lines = []
    
    for i, line_data in valid_lines:
        text = line_data.get("text", "").strip()
        
        # Get font path for this line with bold/italic support
        font_name = line_data.get("font_style", "Arial")
        is_bold = line_data.get("font_bold", False)
        is_italic = line_data.get("font_italic", False)
        font_size = line_data.get("font_size", 30)
        
        font_path = get_font_path(font_name, is_bold, is_italic)
        
        # Try to load font with multiple fallback strategies
        font = None
        fallback_paths = []
        
        # Primary path
        if os.path.exists(font_path):
            try:
                font = ImageFont.truetype(font_path, font_size)
            except Exception:
                pass
        
        # Fallback paths
        if font is None:
            import platform
            is_windows = platform.system() == "Windows"
            
            if is_windows:
                fallback_paths = [
                    os.path.join("C:\\Windows\\Fonts", "arial.ttf"),
                    os.path.join("C:\\Windows\\Fonts", "arialbd.ttf") if is_bold else None
                ]
            else:
                fallback_paths = [
                    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                    "/srv/title_builder/fonts/LiberationSans-Regular.ttf"
                ]
            
            for fallback_path in fallback_paths:
                if fallback_path and os.path.exists(fallback_path):
                    try:
                        font = ImageFont.truetype(fallback_path, font_size)
                        break
                    except Exception:
                        continue
        
        # Ultimate fallback to default font
        if font is None:
            font = ImageFont.load_default()
        
        bbox = draw.textbbox((0, 0), text, font=font)
        text_height = bbox[3] - bbox[1]
        
        text_heights.append(text_height)
        fonts.append(font)
        processed_lines.append((i, line_data, text))
    
    # Calculate total height and spacing for vertical centering
    total_text_height = sum(text_heights)
    total_spacing = LINE_SPACING * (len(processed_lines) - 1)
    total_block_height = total_text_height + total_spacing
    
    # Calculate starting Y position to center the block vertically
    start_y = (HEIGHT - total_block_height) / 2
    
    # Second pass: draw each line centered horizontally and vertically
    current_y = start_y
    for idx, (i, line_data, text) in enumerate(processed_lines):
        font = fonts[idx]
        text_height = text_heights[idx]
        
        # Get text color
        text_color = line_data.get("color", {"r": 255, "g": 255, "b": 255})
        text_color_rgb = (text_color["r"], text_color["g"], text_color["b"])
        
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        
        x = (WIDTH - text_width) / 2
        y = current_y
        draw.text((x, y), text, font=font, fill=text_color_rgb)
        
        # Update y position for next line
        current_y += text_height + LINE_SPACING
    
    return img
