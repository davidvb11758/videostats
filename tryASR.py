
from vosk import Model, KaldiRecognizer
import pyaudio
import json

# ---------------------------------------------------------
# 2. Define restricted vocabulary
# ---------------------------------------------------------

# Allowed numbers (as words)
number_words = [
    "zero", "one", "three", "eight", "nine",
    "ten", "thirteen", "fifteen", "sixteen", "nineteen"
]

# Or if you want *digits* instead of words:
digits = ["0", "1", "3", "8", "9", "10", "13", "15", "16", "19"]

# Allowed action words
actions = [
    "serve", "receive", "pass", "set", "attack",
    "free", "block", "down", "net", "fault"
]

# Control phrases
control_words = ["start", "play", "by", "erase", "stop", "recording"]

# Combine into a single grammar
grammar = digits + number_words + actions + control_words

# Load model
model = Model(r"C:\vosk-model-smEng")  # <-- change path to your folder

# Audio setup with restricted vocabulary
rec = KaldiRecognizer(model, 16000)
rec.SetGrammar(json.dumps(grammar))

p = pyaudio.PyAudio()
stream = p.open(format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=8000)
stream.start_stream()

# State management
is_recording = False
all_words = []  # Master list of all words
last_pair_count = 0  # Track how many pairs we've displayed

print("Waiting for wake-up phrase: 'Start play by play'...")
print("Once activated, speak word pairs.")
print("Say 'Erase' to delete the last word. Say 'Stop recording' to finish.\n")

while True:
    data = stream.read(4000, exception_on_overflow=False)
    if rec.AcceptWaveform(data):
        result = json.loads(rec.Result())
        text = result.get("text", "").strip()
        
        if not text:
            continue
        
        # Check for wake-up phrase
        if not is_recording:
            if "start play by play" in text.lower():
                is_recording = True
                all_words = []
                last_pair_count = 0
                print("✓ Recording started! Speak word pairs now...")
                print("  (Say 'Erase' to undo last word)\n")
            continue
        
        # Check for erase command
        if "erase" in text.lower():
            if all_words:
                erased_word = all_words.pop()
                print(f"  ✗ ERASED word: '{erased_word}' (Words remaining: {len(all_words)})")
                # Recalculate and show current pairs
                last_pair_count = len(all_words) // 2
            else:
                print("  ⚠ Nothing to erase - no words recorded")
            continue
        
        # Check for stop phrase
        if "stop recording" in text.lower():
            is_recording = False
            print("\n✓ Recording stopped!\n")
            
            # Generate word pairs from all_words
            word_pairs = []
            for i in range(0, len(all_words) - 1, 2):
                word_pairs.append([all_words[i], all_words[i+1]])
            
            # Handle odd word at the end
            if len(all_words) % 2 == 1:
                print(f"  ⚠ Note: Last word '{all_words[-1]}' is unpaired\n")
            
            # Print the accumulated word pairs array
            print("=" * 50)
            print("WORD PAIRS ARRAY:")
            print("=" * 50)
            for i, pair in enumerate(word_pairs):
                print(f"Row {i}: {pair}")
            print("=" * 50)
            print(f"Total pairs captured: {len(word_pairs)}\n")
            
            # Write array to text file
            filename = "word_pairs_output.txt"
            with open(filename, "w") as f:
                f.write("WORD PAIRS ARRAY\n")
                f.write("=" * 50 + "\n")
                for i, pair in enumerate(word_pairs):
                    f.write(f"Row {i}: {pair}\n")
                f.write("=" * 50 + "\n")
                f.write(f"Total pairs captured: {len(word_pairs)}\n")
                if len(all_words) % 2 == 1:
                    f.write(f"\nNote: Last word '{all_words[-1]}' is unpaired\n")
            
            print(f"✓ Array written to file: {filename}\n")
            
            # Reset for next session
            all_words = []
            last_pair_count = 0
            print("Waiting for wake-up phrase: 'Start play by play'...")
            continue
        
        # Process text and display
        print(f"You said: {text}")
        
        # Split text into words and add to all_words
        words = text.split()
        all_words.extend(words)
        
        # Display newly formed pairs
        current_pair_count = len(all_words) // 2
        if current_pair_count > last_pair_count:
            # Show new pairs that were formed
            for i in range(last_pair_count, current_pair_count):
                pair = [all_words[i*2], all_words[i*2+1]]
                print(f"  → Pair added: {pair}")
            last_pair_count = current_pair_count
        
        # Show if there's an unpaired word waiting
        if len(all_words) % 2 == 1:
            print(f"  ... waiting for pair: '{all_words[-1]}' + ?")
