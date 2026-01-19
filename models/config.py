"""Data models for video settings configuration."""
from dataclasses import dataclass, field
from typing import Dict, List, Any, Tuple, Optional


@dataclass
class ColorRGB:
    """RGB color representation."""
    r: int
    g: int
    b: int
    
    def to_dict(self) -> Dict[str, int]:
        """Convert to dictionary format."""
        return {"r": self.r, "g": self.g, "b": self.b}
    
    def to_tuple(self) -> Tuple[int, int, int]:
        """Convert to RGB tuple for PIL."""
        return (self.r, self.g, self.b)
    
    @classmethod
    def from_dict(cls, data: Dict[str, int]) -> "ColorRGB":
        """Create from dictionary format."""
        return cls(r=data.get("r", 0), g=data.get("g", 0), b=data.get("b", 0))


@dataclass
class TextLine:
    """Configuration for a single text line."""
    text: str = ""
    color: ColorRGB = field(default_factory=lambda: ColorRGB(255, 255, 255))
    font_style: str = "Arial"
    font_size: int = 30
    font_bold: bool = False
    font_italic: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "text": self.text,
            "color": self.color.to_dict(),
            "font_style": self.font_style,
            "font_size": self.font_size,
            "font_bold": self.font_bold,
            "font_italic": self.font_italic
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TextLine":
        """Create from dictionary format."""
        return cls(
            text=data.get("text", ""),
            color=ColorRGB.from_dict(data.get("color", {"r": 255, "g": 255, "b": 255})),
            font_style=data.get("font_style", "Arial"),
            font_size=data.get("font_size", 30),
            font_bold=data.get("font_bold", False),
            font_italic=data.get("font_italic", False)
        )


@dataclass
class VideoSettings:
    """Complete video settings configuration."""
    background_color: ColorRGB = field(default_factory=lambda: ColorRGB(40, 40, 40))
    lines: List[TextLine] = field(default_factory=lambda: [TextLine() for _ in range(4)])
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format matching JSON export."""
        return {
            "background_color": self.background_color.to_dict(),
            "lines": [line.to_dict() for line in self.lines]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VideoSettings":
        """Create from dictionary format."""
        bg_color = ColorRGB.from_dict(data.get("background_color", {"r": 40, "g": 40, "b": 40}))
        
        lines_data = data.get("lines", [])
        # Ensure exactly 4 lines
        lines = []
        for i in range(4):
            if i < len(lines_data):
                lines.append(TextLine.from_dict(lines_data[i]))
            else:
                lines.append(TextLine())
        
        return cls(background_color=bg_color, lines=lines)
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """
        Validate settings.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check if at least one line has text
        if not any(line.text.strip() for line in self.lines):
            return False, "Please enter at least one line of text."
        
        # Validate font sizes
        for i, line in enumerate(self.lines):
            if not (8 <= line.font_size <= 200):
                return False, f"Font size for line {i+1} must be between 8 and 200."
        
        return True, None

