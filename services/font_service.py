"""Font service for resolving Windows font paths and variants."""
import os
import platform
from typing import Optional, List

# Common Windows fonts (base names only, bold/italic handled separately)
WINDOWS_FONTS = {
    "Arial": "arial.ttf",
    "Times New Roman": "times.ttf",
    "Courier New": "cour.ttf",
    "Comic Sans MS": "comic.ttf",
    "Verdana": "verdana.ttf",
    "Georgia": "georgia.ttf",
    "Impact": "impact.ttf",
    "Trebuchet MS": "trebuc.ttf"
}

# Font file mappings for bold and italic variants
FONT_VARIANTS = {
    "Arial": {
        "bold": "arialbd.ttf",
        "italic": "ariali.ttf",
        "bold_italic": "arialbi.ttf"
    },
    "Times New Roman": {
        "bold": "timesbd.ttf",
        "italic": "timesi.ttf",
        "bold_italic": "timesbi.ttf"
    },
    "Courier New": {
        "bold": "courbd.ttf",
        "italic": "couri.ttf",
        "bold_italic": "courbi.ttf"
    },
    "Comic Sans MS": {
        "bold": "comicbd.ttf",
        "italic": "comici.ttf",
        "bold_italic": "comicbi.ttf"
    },
    "Verdana": {
        "bold": "verdanab.ttf",
        "italic": "verdanai.ttf",
        "bold_italic": "verdanaz.ttf"
    },
    "Georgia": {
        "bold": "georgiab.ttf",
        "italic": "georgiai.ttf",
        "bold_italic": "georgiaz.ttf"
    },
    "Trebuchet MS": {
        "bold": "trebucbd.ttf",
        "italic": "trebucit.ttf",
        "bold_italic": "trebucbi.ttf"
    },
    "Impact": {
        "bold": "impact.ttf",  # Impact doesn't have separate bold
        "italic": "impact.ttf",
        "bold_italic": "impact.ttf"
    }
}


# Font mapping for Linux equivalents
LINUX_FONT_MAP = {
    "Arial": "LiberationSans-Regular.ttf",
    "Times New Roman": "LiberationSerif-Regular.ttf",
    "Courier New": "LiberationMono-Regular.ttf",
    "Comic Sans MS": "LiberationSans-Regular.ttf",
    "Verdana": "DejaVuSans.ttf",
    "Georgia": "LiberationSerif-Regular.ttf",
    "Impact": "LiberationSans-Bold.ttf",
    "Trebuchet MS": "LiberationSans-Regular.ttf"
}

LINUX_FONT_VARIANTS = {
    "Arial": {
        "bold": "LiberationSans-Bold.ttf",
        "italic": "LiberationSans-Italic.ttf",
        "bold_italic": "LiberationSans-BoldItalic.ttf"
    },
    "Times New Roman": {
        "bold": "LiberationSerif-Bold.ttf",
        "italic": "LiberationSerif-Italic.ttf",
        "bold_italic": "LiberationSerif-BoldItalic.ttf"
    },
    "Courier New": {
        "bold": "LiberationMono-Bold.ttf",
        "italic": "LiberationMono-Italic.ttf",
        "bold_italic": "LiberationMono-BoldItalic.ttf"
    },
    "Comic Sans MS": {
        "bold": "LiberationSans-Bold.ttf",
        "italic": "LiberationSans-Italic.ttf",
        "bold_italic": "LiberationSans-BoldItalic.ttf"
    },
    "Verdana": {
        "bold": "DejaVuSans-Bold.ttf",
        "italic": "DejaVuSans-Oblique.ttf",
        "bold_italic": "DejaVuSans-BoldOblique.ttf"
    },
    "Georgia": {
        "bold": "LiberationSerif-Bold.ttf",
        "italic": "LiberationSerif-Italic.ttf",
        "bold_italic": "LiberationSerif-BoldItalic.ttf"
    },
    "Impact": {
        "bold": "LiberationSans-Bold.ttf",
        "italic": "LiberationSans-Bold.ttf",
        "bold_italic": "LiberationSans-Bold.ttf"
    },
    "Trebuchet MS": {
        "bold": "LiberationSans-Bold.ttf",
        "italic": "LiberationSans-Italic.ttf",
        "bold_italic": "LiberationSans-BoldItalic.ttf"
    }
}


def _get_linux_font_paths():
    """Get possible Linux font directory paths."""
    return [
        "/usr/share/fonts/truetype/liberation",
        "/usr/share/fonts/truetype/dejavu",
        "/usr/share/fonts/TTF",
        "/srv/title_builder/fonts",
        "/usr/share/fonts"
    ]


def get_font_path(font_name: str, bold: bool = False, italic: bool = False) -> str:
    """
    Get the full path to a font file based on font name and style (cross-platform).
    
    Args:
        font_name: Name of the font (e.g., "Arial", "Times New Roman")
        bold: Whether to use bold variant
        italic: Whether to use italic variant
        
    Returns:
        Full path to the font file
    """
    is_windows = platform.system() == "Windows"
    
    # Determine which font variant to use
    if is_windows:
        # Windows font paths
        if font_name in FONT_VARIANTS:
            variants = FONT_VARIANTS[font_name]
            if bold and italic:
                font_filename = variants.get("bold_italic") or variants.get("bold") or variants.get("italic") or WINDOWS_FONTS[font_name]
            elif bold:
                font_filename = variants.get("bold") or WINDOWS_FONTS[font_name]
            elif italic:
                font_filename = variants.get("italic") or WINDOWS_FONTS[font_name]
            else:
                font_filename = WINDOWS_FONTS[font_name]
        else:
            font_filename = WINDOWS_FONTS.get(font_name, "arial.ttf")
        
        font_path = os.path.join("C:\\Windows\\Fonts", font_filename)
    else:
        # Linux font paths
        if font_name in LINUX_FONT_VARIANTS:
            variants = LINUX_FONT_VARIANTS[font_name]
            if bold and italic:
                font_filename = variants.get("bold_italic") or variants.get("bold") or variants.get("italic") or LINUX_FONT_MAP[font_name]
            elif bold:
                font_filename = variants.get("bold") or LINUX_FONT_MAP[font_name]
            elif italic:
                font_filename = variants.get("italic") or LINUX_FONT_MAP[font_name]
            else:
                font_filename = LINUX_FONT_MAP[font_name]
        else:
            font_filename = LINUX_FONT_MAP.get(font_name, "LiberationSans-Regular.ttf")
        
        # Try to find font in common Linux locations
        font_dirs = _get_linux_font_paths()
        font_path = None
        
        for font_dir in font_dirs:
            potential_path = os.path.join(font_dir, font_filename)
            if os.path.exists(potential_path):
                font_path = potential_path
                break
        
        # If not found, use first directory as fallback
        if font_path is None:
            font_path = os.path.join(font_dirs[0], font_filename)
    
    return font_path


def get_available_fonts() -> List[str]:
    """
    Get list of available font names.
    
    Returns:
        List of font names
    """
    return list(WINDOWS_FONTS.keys())
