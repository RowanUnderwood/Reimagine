import os
# Set environment variables BEFORE importing other heavy libraries if possible
os.environ["OPENCV_LOG_LEVEL"] = "OFF"
os.environ["OPENCV_FFMPEG_DEBUG"] = "0"
os.environ["OPENCV_VIDEOIO_DEBUG"] = "0"

import cv2
import random
import shutil
import base64
import requests
import signal
import sys
from tqdm import tqdm

# ================= CONFIGURATION =================
LM_STUDIO_URL = "http://192.168.2.192:1234/v1/chat/completions"
MODEL_ID = "qwen/qwen3-vl-8b"
VIDEO_EXTS = ('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv')

DIRS = {
    "Adult Male": "Adult_Male",
    "Adult Female": "Adult_Female",
    "Child": "Child",
    "Animal": "Animal",
    "None": "No_Prominent_Character"
}

# Global flag for clean exit
exit_requested = False

# Force OpenCV internal logging to silent (requires OpenCV 4.x+)
try:
    cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_SILENT)
except AttributeError:
    pass # Older OpenCV versions might not have this function

def signal_handler(sig, frame):
    global exit_requested
    print("\n[!] Exit requested. Finishing current frame and closing...")
    exit_requested = True

# Register Ctrl+C as a clean exit hotkey
signal.signal(signal.SIGINT, signal_handler)

# ================= CORE FUNCTIONS =================

def encode_image(image_bytes):
    """Encodes raw image bytes to base64 for the API."""
    return base64.b64encode(image_bytes).decode('utf-8')

def classify_frame(image_bytes):
    """Sends the extracted frame to LM Studio for classification."""
    base64_image = encode_image(image_bytes)
    
    prompt_text = (
        "Analyze the single most prominent character in this image. "
        "Classify them into exactly ONE of these categories: "
        "'Adult Male', 'Adult Female', 'Child', 'Animal', or 'None'. "
        "Rules: "
        "1. If the character is human and under ~13 years old, choose 'Child'. "
        "2. If the character is a non-human creature, choose 'Animal'. "
        "3. If there is an ensemble cast or no clear focal point, choose 'None'. "
        "Respond with the category name only."
    )

    payload = {
        "model": MODEL_ID,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt_text},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
        ]}],
        "temperature": 0.1, 
        "max_tokens": 15
    }

    try:
        response = requests.post(LM_STUDIO_URL, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content'].strip().strip(".").strip()
    except Exception as e:
        return f"Error: {e}"

def get_valid_frame_index(cap, fps, total_frames):
    """Calculates valid frame range based on video duration rules."""
    duration_mins = (total_frames / fps) / 60

    if duration_mins <= 15:
        start_f, end_f = 0, total_frames
    elif duration_mins <= 40:
        start_f = int(2 * 60 * fps)
        end_f = int(total_frames - (4 * 60 * fps))
    else:
        start_f = int(4 * 60 * fps)
        end_f = int(total_frames - (8 * 60 * fps))

    # Safety check for very short videos that might fail the math
    if start_f >= end_f:
        return random.randint(0, int(total_frames - 1))
        
    return random.randint(start_f, end_f)

def main():
    # 1. Setup Directories
    for folder in DIRS.values():
        os.makedirs(folder, exist_ok=True)

    # 2. Map Directories Recursively
    video_files = []
    print("Scanning directories for videos...")
    
    # Using tqdm here. Since we don't know the total folders, it will show a spinner/counter.
    with tqdm(desc="Scanning Dirs", unit="dir") as pbar:
        for root, _, files in os.walk('.'):
            for f in files:
                if f.lower().endswith(VIDEO_EXTS):
                    video_files.append(os.path.join(root, f))
            pbar.update(1)

    if not video_files:
        print("No video files found.")
        return

    print(f"Found {len(video_files)} videos.")
    
    try:
        num_to_extract = int(input("How many total frames would you like to extract? "))
    except ValueError:
        print("Invalid number.")
        return

    # 3. Processing Loop
    pool = []
    with tqdm(total=num_to_extract, unit="frame", desc="Overall Progress") as pbar:
        for i in range(num_to_extract):
            if exit_requested: break

            # Refill pool if empty to ensure every video is picked before repeating
            if not pool:
                pool = video_files.copy()
                random.shuffle(pool)

            video_path = pool.pop()
            filename_slug = os.path.splitext(os.path.basename(video_path))[0]

            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                tqdm.write(f"Failed to open {video_path}")
                continue

            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            if total_frames <= 0:
                cap.release()
                continue

            # Random frame selection based on rules
            frame_idx = get_valid_frame_index(cap, fps, total_frames)
            timestamp_sec = int(frame_idx / fps)
            
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            success, frame = cap.read()
            cap.release()

            if success:
                # Convert frame to jpg in memory
                _, buffer = cv2.imencode('.jpg', frame)
                img_bytes = buffer.tobytes()

                # Classification
                raw_result = classify_frame(img_bytes)
                classification = raw_result.lower()

                # Sorting Logic
                target_folder = DIRS["None"]
                if "adult male" in classification: target_folder = DIRS["Adult Male"]
                elif "adult female" in classification: target_folder = DIRS["Adult Female"]
                elif "child" in classification: target_folder = DIRS["Child"]
                elif "animal" in classification: target_folder = DIRS["Animal"]

                # File Naming: [Original]_[Timestamp]_[FrameID].jpg
                out_name = f"{filename_slug}_T{timestamp_sec}s_F{frame_idx}.jpg"
                out_path = os.path.join(target_folder, out_name)

                with open(out_path, "wb") as f:
                    f.write(img_bytes)

                tqdm.write(f"Processed: {out_name} -> {raw_result}")
            
            pbar.update(1)

    print("\nDone! All files sorted.")

if __name__ == "__main__":
    main()