import os
import json
import random
import time
import uuid
import glob
import sys
import base64
import io
import requests
import keyboard
import websocket
from PIL import Image
from tqdm import tqdm

# =================================================================================
#  CONFIGURATION SECTION
# =================================================================================

# --- ComfyUI Settings ---
COMFY_SERVER_ADDRESS = "127.0.0.1:8188"
WORKFLOW_FILE = "wan2.2_infinite_video_lightning edition-painter jakes version x.json"
HISTORY_FILE = "completed_files.json"

# --- LM Studio / Qwen Settings ---
# IP from your reimagine.py script
LM_STUDIO_URL = "http://192.168.2.192:1234/v1/chat/completions" 
MODEL_ID = "qwen3-vl-8b-instruct-abliterated-v2.0"
LM_TIMEOUT = 120

# The instruction for Qwen
VISION_SYSTEM_PROMPT = "Design a prompt for a video AI to animate this image in a believable way.  Describe a set of motions and emotions that fit into a 5 second shot.  Be sure to design the shot to include character motion  Examples: she is laughing, breathing heavily, talking excitedly, standing, sitting, dancing, bouncing, etc.  Make sure the motion you describe fits the scene in a plausible way.  Provide the details and animation description ONLY as your response, no additional text, titles, or notes."

# --- General Settings ---
CANCEL_HOTKEY = "end" 
IMAGE_EXTENSIONS = ['*.png', '*.jpg', '*.jpeg', '*.webp']

# =================================================================================
#  VISION / LLM FUNCTIONS
# =================================================================================

def process_and_encode_image(image_path, max_size=768):
    """Resizes and encodes image for the Vision model (borrowed from reimagine.py)"""
    try:
        with Image.open(image_path) as img:
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Resize if too large to save token context/speed
            if max(img.size) > max_size:
                img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG", quality=85)
            return base64.b64encode(buffered.getvalue()).decode('utf-8')
    except Exception as e:
        print(f"Error encoding image: {e}")
        return None

def get_animation_prompt(image_path):
    """Asks Qwen to generate an animation prompt for the image."""
    base64_image = process_and_encode_image(image_path)
    if not base64_image:
        return None

    messages = [
        {"role": "user", "content": [
            {"type": "text", "text": VISION_SYSTEM_PROMPT},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
        ]}
    ]

    payload = {
        "model": MODEL_ID,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 200 # Short, concise prompt
    }

    try:
        response = requests.post(LM_STUDIO_URL, json=payload, timeout=LM_TIMEOUT)
        response.raise_for_status()
        content = response.json()['choices'][0]['message']['content'].strip()
        # Clean up any quotes if the LLM adds them
        return content.replace('"', '').replace("'", "")
    except Exception as e:
        print(f"\n[!] LM Studio Error for {image_path}: {e}")
        return None

# =================================================================================
#  COMFYUI API FUNCTIONS
# =================================================================================

def get_unique_client_id():
    return str(uuid.uuid4())

def load_workflow(filename):
    if not os.path.exists(filename):
        print(f"Error: Workflow file '{filename}' not found.")
        sys.exit(1)
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                return json.load(f)
        except:
            return []
    return []

def save_history(processed_list):
    with open(HISTORY_FILE, 'w') as f:
        json.dump(processed_list, f, indent=4)

def upload_image(filepath):
    """Uploads image to ComfyUI."""
    url = f"http://{COMFY_SERVER_ADDRESS}/upload/image"
    try:
        with open(filepath, 'rb') as f:
            files = {'image': f}
            data = {'overwrite': 'true'} 
            response = requests.post(url, files=files, data=data)
        
        if response.status_code == 200:
            return response.json()['name']
    except Exception as e:
        print(f"\nFailed to upload image: {e}")
    return None

def queue_prompt(prompt_workflow, client_id):
    p = {"prompt": prompt_workflow, "client_id": client_id}
    try:
        response = requests.post(f"http://{COMFY_SERVER_ADDRESS}/prompt", json=p)
        return response.json()
    except Exception as e:
        print(f"Error queuing prompt: {e}")
        return None

def track_progress(prompt_id, ws):
    """Waits for the prompt to finish via Websocket."""
    while True:
        try:
            out = ws.recv()
            if isinstance(out, str):
                message = json.loads(out)
                if message['type'] == 'executing':
                    data = message['data']
                    if data['node'] is None and data['prompt_id'] == prompt_id:
                        return True # Execution finished
        except Exception:
            return False

# =================================================================================
#  MAIN LOGIC
# =================================================================================

def main():
    print("### ComfyUI + Qwen Vision Automation Started ###")
    print(f"Press '{CANCEL_HOTKEY}' to cancel after the current video finishes.\n")

    client_id = get_unique_client_id()
    ws = websocket.WebSocket()
    
    try:
        ws.connect(f"ws://{COMFY_SERVER_ADDRESS}/ws?clientId={client_id}")
    except Exception as e:
        print(f"Could not connect to ComfyUI at {COMFY_SERVER_ADDRESS}. Is it running?")
        return

    workflow = load_workflow(WORKFLOW_FILE)

    # Scan and Filter Files
    files = []
    for ext in IMAGE_EXTENSIONS:
        files.extend(glob.glob(ext))
    
    completed = load_history()
    files_to_process = [f for f in files if f not in completed and f != "completed_files.json" and not f.endswith('.json')]
    
    # --- RANDOMIZE LIST ---
    random.shuffle(files_to_process)
    # ----------------------

    if not files_to_process:
        print("No new images found to process.")
        return

    print(f"Found {len(files_to_process)} images to process.")

    pbar = tqdm(files_to_process, unit="video")
    
    for filename in pbar:
        if keyboard.is_pressed(CANCEL_HOTKEY):
            print("\nCancel requested. Stopping script...")
            break

        pbar.set_description(f"Analyzing: {filename}")
        
        # 1. Get Prompt from Qwen
        vision_prompt = get_animation_prompt(filename)
        
        if not vision_prompt:
            print(f"\nSkipping {filename}: Could not generate prompt from LM Studio.")
            continue
            
        # Optional: Print the prompt to console so you can see what Qwen thought
        # tqdm.write(f"Generated Prompt: {vision_prompt}")

        pbar.set_description(f"Rendering: {filename}")

        # 2. Upload Image to Comfy
        comfy_filename = upload_image(filename)
        if not comfy_filename:
            continue

        # 3. Update Workflow Nodes
        # Node 113: Load Image
        workflow['113']['inputs']['image'] = comfy_filename
        
        # Node 195: CLIP Text Encode (The Vision Prompt)
        workflow['195']['inputs']['text'] = vision_prompt
        
        # Node 206: Video Save Name
        base_name = os.path.splitext(filename)[0]
        workflow['206']['inputs']['filename_prefix'] = f"{base_name}_animation"
        
        # Node 117: Randomize Seed
        seed = random.randint(1, 1000000000000000)
        workflow['117']['inputs']['noise_seed'] = seed

        # 4. Execute
        try:
            prompt_response = queue_prompt(workflow, client_id)
            if prompt_response:
                prompt_id = prompt_response['prompt_id']
                track_progress(prompt_id, ws)
                
                # 5. Save History
                completed.append(filename)
                save_history(completed)
            else:
                print(f"Failed to trigger generation for {filename}")
            
        except Exception as e:
            print(f"\nError processing {filename}: {e}")
            time.sleep(2)

    ws.close()
    print("\nBatch processing finished.")

if __name__ == "__main__":
    main()