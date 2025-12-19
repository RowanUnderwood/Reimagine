# ReImagine: Local Batch Image Remixing Pipeline

**ReImagine** is a fully automated, local-first Python pipeline that "reimagines" your image library. It uses a Vision LLM (via LM Studio) to analyze local images and generate detailed prompts, then intelligently queues those prompts into a ComfyUI workflow using optimal resolutions based on the original aspect ratio.

## 🚀 Key Features

* **Vision-Powered Prompting:** Automatically generates detailed, descriptive prompts for existing images using local Vision LLMs (e.g., Qwen-VL, LLaVA) via LM Studio.
* **Smart Aspect Ratio Mapping:** Analyzes input image dimensions and maps them to the optimal SDXL/Pony resolution buckets. It automatically detects if an image is Portrait (`832x1216`), Landscape (`1152x896`), or Square (`1024x1024`) to prevent generation artifacts.
* **Batch Automation:** Processes entire folders of images in random order, allowing for "set and forget" remixing sessions.
* **Prompt Caching & Logging:** Saves all generated prompts, timestamps, and dimensions to `reimagine_log.csv`. You can resume interrupted sessions or reuse existing prompts without re-running the heavy Vision LLM analysis.
* **ComfyUI API Integration:** Directly interacts with the ComfyUI API using the `save_api` JSON format, bypassing the web interface for faster, headless operation.

## 🛠️ Prerequisites

* **Python 3.10+**
* **[LM Studio](https://lmstudio.ai/):** Running a local server with a Vision-compatible model (e.g., `qwen3-vl-8b-instruct`).
* **[ComfyUI](https://github.com/comfyanonymous/ComfyUI):** Running locally with the `--listen` argument (optional but recommended).
* **Python Dependencies:**
    ```bash
    pip install requests tqdm pillow
    ```

## ⚙️ Configuration

### 1. LM Studio Setup
1.  Load a vision-capable model (the script defaults to `qwen3-vl-8b-instruct-abliterated-v2.0`).
2.  Start the Local Server (default port: `1234`).
3.  Ensure the "Vision" adapter is enabled in the model settings.

### 2. ComfyUI Setup
1.  Open ComfyUI settings (gear icon) and enable **"Enable Dev mode Options"**.
2.  Load your desired workflow.
3.  Click **"Save (API Format)"** to export your `.json` file.
4.  *Crucial Step:* Ensure the Node IDs in `reimagine.py` match your specific workflow:
    * **Node 6:** Positive Prompt (`CLIPTextEncode`)
    * **Node 57:** Seed (`Seed (rgthree)` or generic `KSampler` seed widget)
    * **Node 61:** Empty Latent Image (For width/height injection)

### 3. Script Configuration
Edit the top of `reimagine.py` to match your environment:
```python
LM_STUDIO_URL = "[http://192.168.2.192:1234/v1/chat/completions](http://192.168.2.192:1234/v1/chat/completions)" # Your LM Studio IP
COMFY_URL = "[http://127.0.0.1:8188/prompt](http://127.0.0.1:8188/prompt)" 
MODEL_ID = "qwen3-vl-8b-instruct-abliterated-v2.0" # Exact ID from LM Studio
WORKFLOW_FILE = "ZImage_Poster_API.json" # Your exported API workflow
