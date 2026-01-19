from moviepy.editor import ColorClip, ImageClip, CompositeVideoClip
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                                QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                                QColorDialog, QMessageBox, QComboBox, QSpinBox,
                                QDialog, QScrollArea, QFileDialog, QCheckBox)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette, QPixmap, QImage
import sys
import os
import json
import subprocess
from pathlib import Path
from utils import get_ffmpeg_path

# ---------------------------
# Video settings
# ---------------------------
width, height = 1920, 1080
duration = 5  # seconds
fps = 30

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


class MovieMakerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Movie Maker - Text & Color Editor")
        self.setGeometry(100, 100, 1100, 700)
        
        # Default colors
        self.bg_color = QColor(40, 40, 40)  # dark gray
        self.text_colors = [
            QColor(255, 255, 255),  # white
            QColor(255, 255, 255),  # white
            QColor(255, 255, 255),  # white
            QColor(255, 255, 255)   # white
        ]
        
        # Default fonts and sizes for each line
        self.font_styles = ["Arial"] * 4
        self.font_sizes = [30] * 4
        self.font_bold = [False] * 4
        self.font_italic = [False] * 4
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("Movie Maker - Configure Your Video")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # Background color section
        bg_layout = QHBoxLayout()
        bg_label = QLabel("Background Color:")
        bg_label.setMinimumWidth(150)
        self.bg_color_btn = QPushButton()
        self.bg_color_btn.setMinimumSize(100, 40)
        self.bg_color_btn.setStyleSheet(f"background-color: rgb({self.bg_color.red()}, {self.bg_color.green()}, {self.bg_color.blue()});")
        self.bg_color_btn.clicked.connect(lambda: self.pick_color("bg"))
        bg_layout.addWidget(bg_label)
        bg_layout.addWidget(self.bg_color_btn)
        bg_layout.addStretch()
        layout.addLayout(bg_layout)
        
        # Text lines section
        self.text_inputs = []
        self.color_buttons = []
        self.font_combos = []
        self.font_size_spins = []
        self.bold_checkboxes = []
        self.italic_checkboxes = []
        
        for i in range(4):
            # Main line layout
            line_layout = QVBoxLayout()
            line_layout.setSpacing(5)
            
            # Horizontal layout for controls
            controls_layout = QHBoxLayout()
            
            # Line label
            line_label = QLabel(f"Line {i+1}:")
            line_label.setMinimumWidth(80)
            
            # Text input
            text_input = QLineEdit()
            text_input.setPlaceholderText(f"Enter text for line {i+1}")
            text_input.setMinimumHeight(35)
            
            # Font style combo
            font_combo = QComboBox()
            font_combo.addItems(list(WINDOWS_FONTS.keys()))
            font_combo.setCurrentText(self.font_styles[i])
            font_combo.setMinimumWidth(150)
            font_combo.currentTextChanged.connect(lambda text, idx=i: self.update_font_style(idx, text))
            
            # Font size spinbox
            font_size_label = QLabel("Size:")
            font_size_label.setMinimumWidth(35)
            font_size_spin = QSpinBox()
            font_size_spin.setMinimum(8)
            font_size_spin.setMaximum(200)
            font_size_spin.setValue(self.font_sizes[i])
            font_size_spin.setMinimumWidth(70)
            font_size_spin.valueChanged.connect(lambda value, idx=i: self.update_font_size(idx, value))
            
            # Bold checkbox
            bold_check = QCheckBox("Bold")
            bold_check.setChecked(self.font_bold[i])
            bold_check.stateChanged.connect(lambda state, idx=i: self.update_font_bold(idx, state == 2))
            
            # Italic checkbox
            italic_check = QCheckBox("Italic")
            italic_check.setChecked(self.font_italic[i])
            italic_check.stateChanged.connect(lambda state, idx=i: self.update_font_italic(idx, state == 2))
            
            # Color picker button
            color_btn = QPushButton("Color")
            color_btn.setMinimumSize(80, 35)
            color_btn.setStyleSheet(f"background-color: rgb({self.text_colors[i].red()}, {self.text_colors[i].green()}, {self.text_colors[i].blue()});")
            color_btn.clicked.connect(lambda checked, idx=i: self.pick_color(f"text_{idx}"))
            
            controls_layout.addWidget(line_label)
            controls_layout.addWidget(text_input)
            controls_layout.addWidget(font_combo)
            controls_layout.addWidget(font_size_label)
            controls_layout.addWidget(font_size_spin)
            controls_layout.addWidget(bold_check)
            controls_layout.addWidget(italic_check)
            controls_layout.addWidget(color_btn)
            
            line_layout.addLayout(controls_layout)
            
            self.text_inputs.append(text_input)
            self.color_buttons.append(color_btn)
            self.font_combos.append(font_combo)
            self.font_size_spins.append(font_size_spin)
            self.bold_checkboxes.append(bold_check)
            self.italic_checkboxes.append(italic_check)
            layout.addLayout(line_layout)
        
        # Export/Import buttons
        file_layout = QHBoxLayout()
        
        export_btn = QPushButton("Export to JSON")
        export_btn.setMinimumHeight(40)
        export_btn.setStyleSheet("font-size: 12px; font-weight: bold; background-color: #FF9800; color: white;")
        export_btn.clicked.connect(self.export_to_json)
        
        import_btn = QPushButton("Import from JSON")
        import_btn.setMinimumHeight(40)
        import_btn.setStyleSheet("font-size: 12px; font-weight: bold; background-color: #9C27B0; color: white;")
        import_btn.clicked.connect(self.import_from_json)
        
        file_layout.addWidget(export_btn)
        file_layout.addWidget(import_btn)
        layout.addLayout(file_layout)
        
        # Preview and Generate buttons
        button_layout = QHBoxLayout()
        
        preview_btn = QPushButton("Preview Image")
        preview_btn.setMinimumHeight(50)
        preview_btn.setStyleSheet("font-size: 14px; font-weight: bold; background-color: #2196F3; color: white;")
        preview_btn.clicked.connect(self.preview_image)
        
        generate_btn = QPushButton("Generate Video")
        generate_btn.setMinimumHeight(50)
        generate_btn.setStyleSheet("font-size: 14px; font-weight: bold; background-color: #4CAF50; color: white;")
        generate_btn.clicked.connect(self.generate_video)
        
        button_layout.addWidget(preview_btn)
        button_layout.addWidget(generate_btn)
        layout.addLayout(button_layout)
        
        layout.addStretch()
    
    def update_font_style(self, idx, font_name):
        """Update font style for a specific line"""
        self.font_styles[idx] = font_name
    
    def update_font_size(self, idx, size):
        """Update font size for a specific line"""
        self.font_sizes[idx] = size
    
    def update_font_bold(self, idx, is_bold):
        """Update bold setting for a specific line"""
        self.font_bold[idx] = is_bold
    
    def update_font_italic(self, idx, is_italic):
        """Update italic setting for a specific line"""
        self.font_italic[idx] = is_italic
    
    def pick_color(self, color_type):
        """Open color picker dialog and update the appropriate color"""
        if color_type == "bg":
            color = QColorDialog.getColor(self.bg_color, self, "Select Background Color")
            if color.isValid():
                self.bg_color = color
                self.bg_color_btn.setStyleSheet(
                    f"background-color: rgb({color.red()}, {color.green()}, {color.blue()});"
                )
        else:
            # Extract index from color_type (e.g., "text_0" -> 0)
            idx = int(color_type.split("_")[1])
            color = QColorDialog.getColor(self.text_colors[idx], self, f"Select Color for Line {idx+1}")
            if color.isValid():
                self.text_colors[idx] = color
                self.color_buttons[idx].setStyleSheet(
                    f"background-color: rgb({color.red()}, {color.green()}, {color.blue()});"
                )
    
    def create_image(self):
        """Create the image based on current settings. Returns PIL Image or None if error."""
        # Get text lines
        lines = [text_input.text().strip() for text_input in self.text_inputs]
        
        # Check if at least one line has text
        if not any(lines):
            QMessageBox.warning(self, "Warning", "Please enter at least one line of text.")
            return None
        
        # Convert QColor to RGB tuple
        bg_color_rgb = (self.bg_color.red(), self.bg_color.green(), self.bg_color.blue())
        text_colors_rgb = [
            (color.red(), color.green(), color.blue()) 
            for color in self.text_colors
        ]
        
        try:
            # Create text image using Pillow
            img = Image.new("RGB", (width, height), color=bg_color_rgb)
            draw = ImageDraw.Draw(img)
            
            # First pass: calculate all text heights and positions for vertical centering
            text_heights = []
            fonts = []
            valid_lines = []
            
            for i, line in enumerate(lines):
                if not line:  # Skip empty lines
                    continue
                
                # Get font path for this line with bold/italic support
                font_name = self.font_styles[i]
                is_bold = self.font_bold[i]
                is_italic = self.font_italic[i]
                
                # Determine which font variant to use
                if font_name in FONT_VARIANTS:
                    variants = FONT_VARIANTS[font_name]
                    if is_bold and is_italic:
                        font_filename = variants.get("bold_italic") or variants.get("bold") or variants.get("italic") or WINDOWS_FONTS[font_name]
                    elif is_bold:
                        font_filename = variants.get("bold") or WINDOWS_FONTS[font_name]
                    elif is_italic:
                        font_filename = variants.get("italic") or WINDOWS_FONTS[font_name]
                    else:
                        font_filename = WINDOWS_FONTS[font_name]
                else:
                    font_filename = WINDOWS_FONTS.get(font_name, "arial.ttf")
                
                font_path = os.path.join("C:\\Windows\\Fonts", font_filename)
                
                # Try to load font, fallback to Arial if not found
                try:
                    font = ImageFont.truetype(font_path, self.font_sizes[i])
                except:
                    # Fallback to Arial if font not found
                    try:
                        font = ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", self.font_sizes[i])
                    except:
                        # Ultimate fallback to default font
                        font = ImageFont.load_default()
                
                bbox = draw.textbbox((0, 0), line, font=font)
                text_height = bbox[3] - bbox[1]
                
                text_heights.append(text_height)
                fonts.append(font)
                valid_lines.append((i, line))
            
            # Calculate total height and spacing for vertical centering
            if not valid_lines:
                return img
            
            total_text_height = sum(text_heights)
            spacing = 40  # spacing between lines
            total_spacing = spacing * (len(valid_lines) - 1)
            total_block_height = total_text_height + total_spacing
            
            # Calculate starting Y position to center the block vertically
            start_y = (height - total_block_height) / 2
            
            # Second pass: draw each line centered horizontally and vertically
            current_y = start_y
            for idx, (i, line) in enumerate(valid_lines):
                font = fonts[idx]
                text_height = text_heights[idx]
                
                bbox = draw.textbbox((0, 0), line, font=font)
                text_width = bbox[2] - bbox[0]
                
                x = (width - text_width) / 2
                y = current_y
                draw.text((x, y), line, font=font, fill=text_colors_rgb[i])
                
                # Update y position for next line
                current_y += text_height + spacing
            
            return img
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred while creating image:\n{str(e)}")
            return None
    
    def preview_image(self):
        """Show a preview of how the video will look"""
        img = self.create_image()
        if img is None:
            return
        
        try:
            # Convert PIL Image to QPixmap
            img_rgb = img.convert("RGB")
            img_bytes = img_rgb.tobytes("raw", "RGB")
            q_image = QImage(img_bytes, width, height, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(q_image)
            
            # Create preview dialog
            preview_dialog = QDialog(self)
            preview_dialog.setWindowTitle("Preview - How Your Video Will Look")
            preview_dialog.setMinimumSize(800, 600)
            
            # Create scroll area for large images
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # Create label to display image
            label = QLabel()
            label.setPixmap(pixmap)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setScaledContents(False)
            
            scroll.setWidget(label)
            
            # Layout
            layout = QVBoxLayout(preview_dialog)
            layout.addWidget(scroll)
            
            # Add info label
            info_label = QLabel(f"Preview size: {width}x{height} (scaled to fit window)")
            info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            info_label.setStyleSheet("padding: 10px;")
            layout.addWidget(info_label)
            
            # Add close button
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(preview_dialog.close)
            layout.addWidget(close_btn)
            
            preview_dialog.exec()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred while showing preview:\n{str(e)}")
    
    def generate_video(self):
        """Generate the video with current settings"""
        img = self.create_image()
        if img is None:
            return
        
        try:
            # Convert QColor to RGB tuple for background
            bg_color_rgb = (self.bg_color.red(), self.bg_color.green(), self.bg_color.blue())
            
            # Convert Pillow image to NumPy array
            img_array = np.array(img)
            
            # Create MoviePy clips
            txt_clip = ImageClip(img_array).set_duration(duration)
            bg_clip = ColorClip(size=(width, height), color=bg_color_rgb, duration=duration)
            
            # Composite final video
            final_video = CompositeVideoClip([bg_clip, txt_clip])
            
            # Export MP4 (temporarily to a temp file)
            temp_output = "output_temp.mp4"
            QMessageBox.information(self, "Generating", "Generating video... This may take a moment.")
            final_video.write_videofile(temp_output, fps=fps, audio=False)  # Generate without audio first
            
            # Add audio channel using ffmpeg with anullsrc filter
            ffmpeg_exe = get_ffmpeg_path()
            output_file = "output.mp4"
            cmd = [
                str(ffmpeg_exe),
                '-i', temp_output,  # Input video
                '-f', 'lavfi',  # Use libavfilter input
                '-i', 'anullsrc=channel_layout=stereo:sample_rate=48000',  # Generate silent audio
                '-c:v', 'copy',  # Copy video codec
                '-c:a', 'aac',  # Encode audio as AAC
                '-shortest',  # Finish encoding when shortest input ends
                '-y',  # Overwrite output file
                output_file
            ]
            
            print(f"DEBUG: Adding audio channel with command: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            # Clean up temp file
            try:
                if Path(temp_output).exists():
                    os.remove(temp_output)
            except Exception as e:
                print(f"DEBUG: Failed to remove temp file: {e}")
            
            if result.returncode != 0:
                error_msg = result.stderr if result.stderr else "Unknown error"
                QMessageBox.critical(self, "Error", f"Failed to add audio channel:\n{error_msg}")
                return
            
            QMessageBox.information(self, "Success", f"Video generated successfully as 'output.mp4'!\nResolution: {width}x{height} @ {fps} FPS\nAudio: Stereo @ 48kHz")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred:\n{str(e)}")
    
    def export_to_json(self):
        """Export current settings to a JSON file"""
        try:
            # Get file path from user
            file_path, _ = QFileDialog.getSaveFileName(
                self, 
                "Export Settings to JSON", 
                "", 
                "JSON Files (*.json);;All Files (*)"
            )
            
            if not file_path:
                return  # User cancelled
            
            # Ensure .json extension
            if not file_path.endswith('.json'):
                file_path += '.json'
            
            # Collect all settings
            settings = {
                "background_color": {
                    "r": self.bg_color.red(),
                    "g": self.bg_color.green(),
                    "b": self.bg_color.blue()
                },
                "lines": []
            }
            
            # Add each line's settings
            for i in range(4):
                line_data = {
                    "text": self.text_inputs[i].text(),
                    "color": {
                        "r": self.text_colors[i].red(),
                        "g": self.text_colors[i].green(),
                        "b": self.text_colors[i].blue()
                    },
                    "font_style": self.font_styles[i],
                    "font_size": self.font_sizes[i],
                    "font_bold": self.font_bold[i],
                    "font_italic": self.font_italic[i]
                }
                settings["lines"].append(line_data)
            
            # Write to JSON file
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=4, ensure_ascii=False)
            
            QMessageBox.information(self, "Success", f"Settings exported successfully to:\n{file_path}")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export settings:\n{str(e)}")
    
    def import_from_json(self):
        """Import settings from a JSON file"""
        try:
            # Get file path from user
            file_path, _ = QFileDialog.getOpenFileName(
                self, 
                "Import Settings from JSON", 
                "", 
                "JSON Files (*.json);;All Files (*)"
            )
            
            if not file_path:
                return  # User cancelled
            
            # Read JSON file
            with open(file_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            
            # Validate structure
            if "background_color" not in settings or "lines" not in settings:
                QMessageBox.warning(self, "Error", "Invalid JSON file format. Missing required fields.")
                return
            
            if len(settings["lines"]) != 4:
                QMessageBox.warning(self, "Error", "JSON file must contain exactly 4 lines.")
                return
            
            # Restore background color
            bg = settings["background_color"]
            self.bg_color = QColor(bg["r"], bg["g"], bg["b"])
            self.bg_color_btn.setStyleSheet(
                f"background-color: rgb({bg['r']}, {bg['g']}, {bg['b']});"
            )
            
            # Restore each line's settings
            for i, line_data in enumerate(settings["lines"]):
                # Text
                self.text_inputs[i].setText(line_data.get("text", ""))
                
                # Color
                color = line_data.get("color", {"r": 255, "g": 255, "b": 255})
                self.text_colors[i] = QColor(color["r"], color["g"], color["b"])
                self.color_buttons[i].setStyleSheet(
                    f"background-color: rgb({color['r']}, {color['g']}, {color['b']});"
                )
                
                # Font style (handle backward compatibility with "Arial Bold" style names)
                font_style = line_data.get("font_style", "Arial")
                # Check if it's an old format with " Bold" suffix
                if font_style.endswith(" Bold"):
                    base_font = font_style[:-5]  # Remove " Bold" suffix
                    if base_font in WINDOWS_FONTS:
                        self.font_styles[i] = base_font
                        self.font_combos[i].setCurrentText(base_font)
                        # Set bold if not already set
                        if not line_data.get("font_bold", False):
                            self.font_bold[i] = True
                            self.bold_checkboxes[i].setChecked(True)
                    else:
                        self.font_styles[i] = "Arial"
                        self.font_combos[i].setCurrentText("Arial")
                elif font_style in WINDOWS_FONTS:
                    self.font_styles[i] = font_style
                    self.font_combos[i].setCurrentText(font_style)
                else:
                    QMessageBox.warning(self, "Warning", f"Font '{font_style}' not found for line {i+1}. Using Arial.")
                    self.font_styles[i] = "Arial"
                    self.font_combos[i].setCurrentText("Arial")
                
                # Font size
                font_size = line_data.get("font_size", 30)
                if 8 <= font_size <= 200:
                    self.font_sizes[i] = font_size
                    self.font_size_spins[i].setValue(font_size)
                else:
                    QMessageBox.warning(self, "Warning", f"Invalid font size {font_size} for line {i+1}. Using 30.")
                    self.font_sizes[i] = 30
                    self.font_size_spins[i].setValue(30)
                
                # Font bold
                font_bold = line_data.get("font_bold", False)
                self.font_bold[i] = font_bold
                self.bold_checkboxes[i].setChecked(font_bold)
                
                # Font italic
                font_italic = line_data.get("font_italic", False)
                self.font_italic[i] = font_italic
                self.italic_checkboxes[i].setChecked(font_italic)
            
            QMessageBox.information(self, "Success", f"Settings imported successfully from:\n{file_path}")
            
        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "Error", f"Invalid JSON file:\n{str(e)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to import settings:\n{str(e)}")


def main():
    app = QApplication(sys.argv)
    window = MovieMakerGUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

