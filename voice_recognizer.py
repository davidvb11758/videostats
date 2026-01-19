"""
Voice recognition module for player-action pairs.
Can be used by data_entry.py and coordinate_mapper.py.
"""

from PySide6.QtCore import QObject, Signal
from utils import resource_path
from logging_config import get_logger
import json
import threading

# Voice recognition imports - optional if vosk is not installed
try:
    from vosk import Model, KaldiRecognizer
    import pyaudio
    VOSK_AVAILABLE = True
except ImportError:
    VOSK_AVAILABLE = False


class VoiceRecognizer(QObject):
    """Voice recognition handler for player-action pairs."""
    
    # Signal emitted when a player-action pair is recognized
    pair_recognized = Signal(str, str)  # (player_word, action_word)
    # Signal for status updates
    status_update = Signal(str)
    # Signal when listening starts/stops
    listening_changed = Signal(bool)
    
    # Word-to-number mapping for spoken numbers
    WORD_TO_NUMBER = {
        "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
        "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
        "ten": "10", "eleven": "11", "twelve": "12", "thirteen": "13",
        "fourteen": "14", "fifteen": "15", "sixteen": "16", "seventeen": "17",
        "eighteen": "18", "nineteen": "19", "twenty": "20",
        # Also accept digit strings directly
        "0": "0", "1": "1", "2": "2", "3": "3", "4": "4",
        "5": "5", "6": "6", "7": "7", "8": "8", "9": "9",
        "10": "10", "11": "11", "12": "12", "13": "13", "14": "14",
        "15": "15", "16": "16", "17": "17", "18": "18", "19": "19", "20": "20",
    }
    
    # Valid action words
    VALID_ACTIONS = {
        "serve": "serve", "receive": "receive", "pass": "pass", "dig": "pass",
        "set": "set", "attack": "attack", "hit": "attack",
        "free": "freeball", "freeball": "freeball",
        "block": "block", "down": "down",
        "net": "net", "fault": "fault"
    }
    
    def __init__(self, model_path: str = None):
        super().__init__()
        self.logger = get_logger('voice_recognizer')
        if model_path is None:
            # Use resource_path to find model in project directory (works in dev and PyInstaller)
            model_path = str(resource_path("vosk-model-smEng"))
        self.model_path = model_path
        self.model = None
        self.recognizer = None
        self.audio_stream = None
        self.pyaudio_instance = None
        self._is_listening = False
        self._stop_requested = False
        self._listen_thread = None
        self._words_buffer = []  # Buffer to collect words for pairing
        
    def initialize(self) -> bool:
        """Initialize the voice recognition model and audio. Returns True if successful."""
        if not VOSK_AVAILABLE:
            self.status_update.emit("Voice recognition not available - vosk/pyaudio not installed")
            return False
        
        try:
            self.status_update.emit("Loading voice model...")
            self.model = Model(self.model_path)
            
            # Define grammar for restricted vocabulary
            number_words = [
                "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
                "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
                "seventeen", "eighteen", "nineteen", "twenty"
            ]
            digits = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", 
                     "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20"]
            actions = ["serve", "receive", "pass", "dig", "set", "attack", "hit",
                      "free", "freeball", "block", "down", "net", "fault"]
            
            grammar = digits + number_words + actions
            
            self.recognizer = KaldiRecognizer(self.model, 16000)
            self.recognizer.SetGrammar(json.dumps(grammar))
            
            # Initialize audio
            self.pyaudio_instance = pyaudio.PyAudio()
            
            self.status_update.emit("Voice model loaded successfully")
            return True
            
        except Exception as e:
            self.status_update.emit(f"Failed to initialize voice recognition: {str(e)}")
            return False
    
    def start_listening(self):
        """Start listening for voice input in background thread."""
        if not self.model or not self.recognizer:
            if not self.initialize():
                return
        
        if self._is_listening:
            return
        
        self._stop_requested = False
        self._words_buffer = []
        self._listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._listen_thread.start()
        self._is_listening = True
        self.listening_changed.emit(True)
        self.status_update.emit("Voice input active - speak player number and action")
    
    def stop_listening(self):
        """Stop listening for voice input."""
        self._stop_requested = True
        if self.audio_stream:
            try:
                self.audio_stream.stop_stream()
                self.audio_stream.close()
            except:
                pass
            self.audio_stream = None
        self._is_listening = False
        self.listening_changed.emit(False)
        self.status_update.emit("Voice input stopped")
    
    def _listen_loop(self):
        """Main listening loop - runs in background thread."""
        try:
            self.audio_stream = self.pyaudio_instance.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=8000
            )
            self.audio_stream.start_stream()
            
            while not self._stop_requested:
                try:
                    data = self.audio_stream.read(4000, exception_on_overflow=False)
                    if self.recognizer.AcceptWaveform(data):
                        result = json.loads(self.recognizer.Result())
                        text = result.get("text", "").strip()
                        
                        if text:
                            self._process_recognized_text(text)
                except Exception as e:
                    if not self._stop_requested:
                        print(f"Voice recognition error: {e}")
                        
        except Exception as e:
            self.status_update.emit(f"Audio stream error: {str(e)}")
        finally:
            self._is_listening = False
            self.listening_changed.emit(False)
    
    def _process_recognized_text(self, text: str):
        """Process recognized text and emit signals when a valid pair is found."""
        words = text.lower().split()
        self.logger.debug(f"VOICE: Heard raw text: '{text}'")
        self.logger.debug(f"VOICE: Split words: {words}")
        self._words_buffer.extend(words)
        self.logger.debug(f"VOICE: Buffer now: {self._words_buffer}")
        
        # Try to form a player-action pair from the buffer
        while len(self._words_buffer) >= 2:
            first_word = self._words_buffer[0]
            second_word = self._words_buffer[1]
            
            # Check if first word is a number
            player_number = self.WORD_TO_NUMBER.get(first_word)
            # Check if second word is an action
            action = self.VALID_ACTIONS.get(second_word)
            
            self.logger.debug(f"VOICE: Checking pair: '{first_word}' -> player={player_number}, '{second_word}' -> action={action}")
            
            if player_number and action:
                # Valid pair found
                self._words_buffer = self._words_buffer[2:]  # Remove used words
                self.logger.debug(f"VOICE: *** VALID PAIR FOUND: Player {player_number}, Action {action} ***")
                self.pair_recognized.emit(player_number, action)
                self.status_update.emit(f"Recognized: Player {player_number} - {action}")
                return
            else:
                # First word is not a valid number, skip it
                if not player_number:
                    self.logger.debug(f"VOICE: Skipping '{first_word}' - not a valid number")
                    self._words_buffer.pop(0)
                # Or second word is not a valid action, skip first word
                elif not action:
                    self.logger.debug(f"VOICE: Skipping '{first_word}' - '{second_word}' is not a valid action")
                    self._words_buffer.pop(0)
    
    def is_listening(self) -> bool:
        """Return whether voice recognition is currently listening."""
        return self._is_listening
    
    def cleanup(self):
        """Clean up resources."""
        self.stop_listening()
        if self.pyaudio_instance:
            self.pyaudio_instance.terminate()
            self.pyaudio_instance = None


