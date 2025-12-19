import os
import json
import base64
import requests
import random
import csv
import time
import io
from datetime import datetime
from tqdm import tqdm
from PIL import Image

# ================= CONFIGURATION =================
LM_STUDIO_URL = "http://192.168.2.192:1234/v1/chat/completions"
COMFY_URL = "http://127.0.0.1:8188/prompt" 
MODEL_ID = "qwen3-vl-8b-instruct-abliterated-v2.0"
# NOTE: Ensure this points to the API-FORMAT version of your JSON
WORKFLOW_FILE = "ZImage_Poster_API.json" 
LOG_FILE = "reimagine_log.csv"

# Reliability Settings
LM_TIMEOUT = 120  
MAX_RETRIES = 2   
# =================================================

stop_requested = False

def log_task(filename, ratio, prompt):
    file_exists = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Timestamp", "Filename", "Ratio", "Prompt"])
        writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), filename, ratio, prompt])

def load_existing_prompts(log_file):
    """Reads the CSV log and returns a dictionary of filename -> prompt."""
    prompts = {}
    if not os.path.exists(log_file):
        return prompts
        
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if "Filename" in row and "Prompt" in row:
                    prompts[row["Filename"]] = row["Prompt"]
    except Exception as e:
        print(f"[!] Error reading log file: {e}")
    
    return prompts

def process_and_encode_image(image_path, max_size=768):
    """Resizes image for faster LLM processing and encodes to base64."""
    with Image.open(image_path) as img:
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        if max(img.size) > max_size:
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        
        buffered = io.BytesIO()
        img.save(buffered, format="JPEG", quality=85)
        return base64.b64encode(buffered.getvalue()).decode('utf-8')

def get_image_description(image_path):
    """Ask LM Studio for description with optimized image size."""
    try:
        base64_image = process_and_encode_image(image_path)
    except Exception as e:
        print(f"Error processing image {image_path}: {e}")
        return None

    payload = {
        "model": MODEL_ID,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": "If you think the image is a poster or magazine cover, mention this first! Describe this image in extreme detail for an image generation prompt. Provide the details and organized image description ONLY as your response, no additional information."},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
        ]}],
        "temperature": 0.7
    }

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = requests.post(LM_STUDIO_URL, json=payload, timeout=LM_TIMEOUT)
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content'].strip()
        except requests.exceptions.Timeout:
            print(f"\n[!] Timeout on {image_path} (Attempt {attempt+1})")
            if attempt < MAX_RETRIES:
                time.sleep(1)
                continue
        except Exception as e:
            print(f"\n[!] LM Studio Error: {e}")
            break
    return None

def get_smart_dimensions(image_path):
    """
    Calculates SDXL/Pony friendly dimensions based on input aspect ratio.
    Returns: (width, height, description_string)
    """
    with Image.open(image_path) as img:
        w, h = img.size
        ratio = w / h
        
        # SDXL Preferred Dimensions
        if ratio > 1.3: 
            return 1152, 896, "landscape" # ~4:3 Landscape
        elif ratio < 0.8: 
            return 832, 1216, "portrait"  # ~2:3 Portrait
        elif ratio < 0.9:
            return 896, 1152, "portrait"  # ~3:4 Portrait
        else:
            return 1024, 1024, "square"   # 1:1 Square

def send_to_comfy(prompt_text, width, height):
    try:
        with open(WORKFLOW_FILE, 'r') as f:
            workflow = json.load(f)

        # Safety Check: Ensure this is API format (Keys are IDs), not Graph format (List of nodes)
        if isinstance(workflow, list) or "nodes" in workflow:
            print(f"[!] FATAL: {WORKFLOW_FILE} is in 'Saved' format.")
            print("    Please open ComfyUI -> Enable Dev Options -> Save (API Format).")
            return False

        # --- NODE MAPPING FOR NEW JSON ---
        
        # Node 6: Positive Prompt (CLIPTextEncode)
        if "6" in workflow: 
            workflow["6"]["inputs"]["text"] = str(prompt_text)
        else:
            print("[!] Warning: Node 6 (Positive Prompt) not found.")

        # Node 57: Global Seed (RGThree Seed)
        # Note: RGThree nodes handle seeds uniquely, but usually accept 'seed' in API.
        if "57" in workflow:
            workflow["57"]["inputs"]["seed"] = random.randint(1, 10**15)
        else:
            print("[!] Warning: Node 57 (Seed) not found.")
            
        # Node 61: Empty Latent Image
        # We bypass the custom resolution node (60) and set W/H directly on the Latent
        if "61" in workflow:
            workflow["61"]["inputs"]["width"] = width
            workflow["61"]["inputs"]["height"] = height
        else:
            print("[!] Warning: Node 61 (Empty Latent) not found.")

        response = requests.post(COMFY_URL, json={"prompt": workflow}, timeout=15)
        return response.status_code == 200
    except Exception as e:
        print(f"[!] ComfyUI Error: {e}")
        return False

def main():
    global stop_requested
    valid_exts = ('.jpg', '.jpeg', '.png', '.webp')
    files = [f for f in os.listdir('.') if f.lower().endswith(valid_exts)]
    
    # --- ADDED: Shuffle files for random processing order ---
    random.shuffle(files)
    
    print(f"--- PRESS CTRL+C TO CANCEL ---")
    print(f"Targeting Primary Instance: {COMFY_URL}")
    print(f"Workflow File: {WORKFLOW_FILE}")
    print(f"Processing {len(files)} files in random order.")

    cached_prompts = {}
    use_cache = False
    
    if os.path.exists(LOG_FILE):
        print(f"\nFound existing log file: {LOG_FILE}")
        user_input = input("Would you like to reuse prompts from the log? (y/n): ").strip().lower()
        if user_input == 'y':
            use_cache = True
            cached_prompts = load_existing_prompts(LOG_FILE)
            print(f"Loaded {len(cached_prompts)} prompts from log.")
    
    for filename in tqdm(files, unit="img"):
        if stop_requested:
            break
            
        try:
            description = None
            
            if use_cache and filename in cached_prompts:
                description = cached_prompts[filename]
            
            if not description:
                description = get_image_description(filename)
            
            if not description:
                print(f"\n[!] Could not get description for {filename}")
                continue
                
            # Get integer dimensions instead of strings
            w, h, ratio_desc = get_smart_dimensions(filename)
            
            if send_to_comfy(description, w, h):
                log_task(filename, f"{w}x{h} ({ratio_desc})", description)
            else:
                print(f"\n[!] Failed to queue {filename} to ComfyUI")

        except KeyboardInterrupt:
            print("\n[!] Stop signal received. Finishing current task...")
            stop_requested = True

    print(f"\nProcessing complete. Logs updated in {LOG_FILE}")

if __name__ == "__main__":
    main()