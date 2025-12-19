# Reimagine
Python automation linking LM Studio and ComfyUI for batch image reimagining. Uses Vision LLMs to describe local images, calculates optimal aspect ratios, and queues generations via API. Includes logging, prompt caching, and smart resolution handling for efficient workflows.
ReImagine: Local Batch Image Remixing Pipeline
ReImagine is a fully automated, local-first Python pipeline that "reimagines" your image library. It uses a Vision LLM (via LM Studio) to analyze local images and generate detailed prompts, then intelligently queues those prompts into a ComfyUI workflow using optimal SDXL/Pony resolutions based on the original aspect ratio.

🚀 Key Features
Vision-Powered Prompting: Automatically generates detailed, descriptive prompts for existing images using local Vision LLMs (e.g., Qwen-VL, LLaVA).

Smart Aspect Ratio Mapping: Analyzes input image dimensions and maps them to the optimal SDXL/Pony resolution buckets (e.g., converting a vertical phone photo to 832x1216 and a wallpaper to 1152x896) to prevent generation artifacts.

Batch Automation: Processes entire folders of images in random order, allowing for "set and forget" remixing sessions.

Prompt Caching & Logging: Saves all generated prompts and dimensions to reimagine_log.csv. You can resume interrupted sessions or reuse existing prompts without re-running the heavy Vision LLM analysis.

ComfyUI API Integration: Directly interacts with the ComfyUI API, bypassing the web interface for faster, headless operation.

🛠️ Prerequisites
Python 3.10+

LM Studio: Running a local server with a Vision-compatible model (e.g., qwen3-vl-8b-instruct).

ComfyUI: Running locally with the --listen argument (optional but recommended).

Python Dependencies:

Bash

pip install requests tqdm pillow
⚙️ Configuration
1. LM Studio Setup
Load a vision-capable model (e.g., Qwen2-VL or LLaVA).

Start the Local Server (default port: 1234).

Ensure the "Vision" adapter is enabled in the model settings.

2. ComfyUI Setup
Open ComfyUI settings (gear icon) and enable "Enable Dev mode Options".

Load your desired workflow.

Click "Save (API Format)" to export your .json file.

Crucial Step: Ensure the Node IDs in reimagine.py match your specific workflow:

Node 6: Positive Prompt (CLIPTextEncode)

Node 57: Seed (Seed (rgthree) or generic KSampler seed widget)

Node 61: Empty Latent Image (For width/height injection)

3. Script Configuration
Edit the top of reimagine.py to match your environment:

Python

LM_STUDIO_URL = "http://192.168.1.X:1234/v1/chat/completions" # Your LM Studio IP
COMFY_URL = "http://127.0.0.1:8188/prompt" 
MODEL_ID = "qwen3-vl-8b-instruct..." # Exact ID from LM Studio
WORKFLOW_FILE = "ZImage_Poster_API.json" # Your exported API workflow
🖥️ Usage
Place your source images (.jpg, .png, .webp) in the same folder as the script.

Run the script:

Bash

python reimagine.py
The script will:

Pick a random image.

Ask the Vision LLM for a detailed description.

Calculate the best output resolution.

Send the job to ComfyUI.

Log the result to reimagine_log.csv.

Restoring from Cache: If you restart the script, it will ask if you want to reuse prompts from the log file. Type y to skip the Vision LLM step for previously processed files.
