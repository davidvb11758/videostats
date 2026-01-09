"""
Service for video extraction and concatenation operations.
"""

import sys
import subprocess
from pathlib import Path
from typing import List, Optional
from utils import get_ffmpeg_path


class VideoService:
    """Service for video operations."""
    
    @staticmethod
    def extract_clip(video_path: str, start_ms: int, duration_ms: int, output_path: str) -> bool:
        """
        Extract a video clip using ffmpeg.
        
        Args:
            video_path: Path to input video file
            start_ms: Start time in milliseconds
            duration_ms: Duration in milliseconds
            output_path: Path to output clip file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            ffmpeg_exe = get_ffmpeg_path()
            
            # Convert milliseconds to seconds
            start_seconds = start_ms / 1000.0
            duration_seconds = duration_ms / 1000.0
            
            # ffmpeg command to extract clip
            cmd = [
                str(ffmpeg_exe),
                '-ss', str(start_seconds),
                '-i', video_path,
                '-t', str(duration_seconds),
                '-c', 'copy',
                '-y',  # Overwrite output file if exists
                str(output_path)
            ]
            
            print(f"DEBUG: Running ffmpeg command: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            if result.returncode == 0:
                return True
            else:
                error_msg = result.stderr if result.stderr else "Unknown error"
                print(f"FFmpeg error: {error_msg}")
                return False
                
        except FileNotFoundError:
            print(f"FFmpeg not found at: {get_ffmpeg_path()}")
            return False
        except Exception as e:
            print(f"Error extracting clip: {str(e)}")
            return False
    
    @staticmethod
    def concatenate_clips(clip_paths: List[str], output_path: str, include_title: bool = False, 
                          title_path: Optional[str] = None) -> bool:
        """
        Concatenate multiple video clips into a single highlight video.
        
        Args:
            clip_paths: List of paths to clip files
            output_path: Path to output highlight video
            include_title: Whether to include title screen
            title_path: Path to title screen video (if include_title is True)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Build list of all input files (title first if included, then all clips)
            input_files = []
            if include_title and title_path:
                title_path_obj = Path(title_path)
                if not title_path_obj.exists():
                    print(f"Title screen not found: {title_path}")
                    return False
                input_files.append(str(title_path_obj.absolute()))
            
            # Add all video clips
            for clip_path in clip_paths:
                clip_path_obj = Path(clip_path)
                if not clip_path_obj.exists():
                    print(f"Clip file not found: {clip_path}")
                    continue
                input_files.append(str(clip_path_obj.absolute()))
            
            if not input_files:
                print("No valid input files found")
                return False
            
            total_inputs = len(input_files)
            print(f"DEBUG: Concatenating {total_inputs} files ({len(clip_paths)} clips" + 
                  (f" + 1 title screen" if include_title else "") + ") into highlight video")
            
            # Build ffmpeg command with filter_complex pattern
            ffmpeg_exe = get_ffmpeg_path()
            cmd = [str(ffmpeg_exe)]
            
            # Add -i for each input file
            for input_file in input_files:
                cmd.extend(['-i', input_file])
            
            # Build filter_complex string
            # For each input: [N:v]fps=30000/1001[vN] to normalize frame rate
            # Then concat all: [v0][0:a][v1][1:a]... concat=n=total:v=1:a=1[v][a]
            filter_parts = []
            concat_inputs = []
            
            for i in range(total_inputs):
                # Add fps filter for each video stream
                filter_parts.append(f"[{i}:v]fps=30000/1001[v{i}]")
                # Add to concat inputs: video and audio
                concat_inputs.append(f"[v{i}][{i}:a]")
            
            # Build the concat filter
            concat_filter = ''.join(concat_inputs) + f" concat=n={total_inputs}:v=1:a=1[v][a]"
            
            # Combine all filters
            filter_complex = ';'.join(filter_parts) + ';' + concat_filter
            
            # Add filter_complex and output options
            cmd.extend([
                '-filter_complex', filter_complex,
                '-map', '[v]',
                '-map', '[a]',
                '-c:v', 'libx264',
                '-pix_fmt', 'yuv420p',
                '-c:a', 'aac',
                '-y',
                str(output_path)
            ])
            
            # Print the ffmpeg command to terminal before executing
            print(f"DEBUG: Running ffmpeg command: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            if result.returncode == 0:
                return True
            else:
                error_msg = result.stderr if result.stderr else "Unknown error"
                print(f"Failed to create highlight video: {error_msg}")
                return False
        
        except FileNotFoundError:
            print(f"FFmpeg not found at: {get_ffmpeg_path()}")
            return False
        except Exception as e:
            print(f"Error creating highlight video: {str(e)}")
            return False
    
    @staticmethod
    def create_highlight_from_clips(clips: List, output_dir: Path, highlight_filename: str,
                                    include_title: bool = False, title_path: Optional[str] = None,
                                    progress_callback=None) -> Optional[Path]:
        """
        Create a highlight video from a list of clips.
        
        Args:
            clips: List of VideoClip objects or dicts with video_file_path, start_ms, duration_ms
            output_dir: Directory to save output
            highlight_filename: Output filename
            include_title: Whether to include title screen
            title_path: Path to title screen video
            progress_callback: Optional callback function(progress, total) for progress updates
            
        Returns:
            Path to created highlight video, or None if failed
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)
        highlight_path = output_dir / highlight_filename
        
        # Create temporary directory for individual clips
        import tempfile
        temp_dir = Path(tempfile.mkdtemp())
        
        try:
            # Extract individual clips
            clip_files = []
            total_clips = len(clips)
            
            for idx, clip in enumerate(clips):
                # Handle both VideoClip objects and dicts
                if hasattr(clip, 'video_file_path'):
                    video_path = clip.video_file_path
                    start_ms = clip.start_ms
                    duration_ms = clip.duration_ms
                else:
                    video_path = clip['video_file_path']
                    start_ms = clip['start_ms']
                    duration_ms = clip['duration_ms']
                
                if not video_path or not Path(video_path).exists():
                    print(f"DEBUG: Skipping clip {idx} - video file not found: {video_path}")
                    continue
                
                # Create temporary clip filename
                clip_filename = f"clip_{idx:03d}.mp4"
                clip_path = temp_dir / clip_filename
                
                # Extract clip
                if progress_callback:
                    progress_callback(idx, total_clips)
                
                if VideoService.extract_clip(video_path, start_ms, duration_ms, str(clip_path)):
                    clip_files.append(str(clip_path))
                else:
                    print(f"DEBUG: Failed to extract clip {idx}")
            
            if not clip_files:
                print("Failed to extract any clips!")
                return None
            
            # Concatenate clips
            if progress_callback:
                progress_callback(total_clips, total_clips + 1)
            
            if VideoService.concatenate_clips(clip_files, str(highlight_path), include_title, title_path):
                if progress_callback:
                    progress_callback(total_clips + 1, total_clips + 1)
                return highlight_path
            else:
                return None
        
        except Exception as e:
            print(f"Error creating highlight video: {str(e)}")
            return None
        finally:
            # Note: Not cleaning up temp files per user request (commented out in original)
            print(f"DEBUG: Temporary directory preserved: {temp_dir}")
