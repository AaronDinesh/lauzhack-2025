import os
import json
import asyncio
import base64
import requests
from pathlib import Path
from typing import Any, Tuple, Optional
from threading import Lock
from functools import partial

import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

import shutil

# --- SAM 3 Imports ---
from sam3.model_builder import build_sam3_image_model
from sam3.model.sam3_image_processor import Sam3Processor
from sam3.agent.client_sam3 import call_sam_service as call_sam_service_orig
from sam3.agent.inference import run_single_image_inference

load_dotenv() 

# ----------------------------------------------------------------------
# 1. Global Setup (Same as before)
# ----------------------------------------------------------------------
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16

sam3_root = Path(__file__).resolve().parents[1] / "sam3"
bpe_path = sam3_root / "assets" / "bpe_simple_vocab_16e6.txt.gz"

print(f"Loading SAM 3 model on {DEVICE} with {DTYPE}...")

_model = build_sam3_image_model(bpe_path=str(bpe_path))
_model.to(DEVICE)
_model.eval()

_processor = Sam3Processor(_model, confidence_threshold=0.5)
_model_lock = Lock()

print("SAM 3 Model Loaded.")

# ----------------------------------------------------------------------
# 2. FIXED Custom OpenAI Adapter
# ----------------------------------------------------------------------
def encode_image(image_path):
    """Encodes local image to base64 for OpenAI API"""
    if not os.path.exists(image_path):
        return None
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def send_openai_request(
    prompt: str, 
    image: str = None, 
    server_url: str = None, 
    model: str = None, 
    api_key: str = None,
    **kwargs
) -> str:
    """
    Custom adapter that routes SAM 3's reasoning requests to ChatGPT.
    Includes debug printing and strict type handling.
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    # Safety: Ensure prompt is a string. SAM 3 sometimes passes complex objects.
    if not isinstance(prompt, str):
        prompt = str(prompt)

    messages = []
    
    # Logic: Only use vision payload if image path is provided AND valid
    base64_image = encode_image(image) if image else None

    if base64_image:
        # Vision Request
        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "text", 
                    "text": prompt
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    }
                }
            ]
        })
    else:
        # Text-only Request
        messages.append({
            "role": "user", 
            "content": prompt
        })

    payload = {
        "model": model or "gpt-4o",
        "messages": messages,
        "max_tokens": 1000,
        "temperature": 0.1
    }

    # --- DEBUG: Print payload if you hit errors ---
    # print(f"DEBUG PAYLOAD: {json.dumps(payload, indent=2)[:500]} ...") 

    response = requests.post(f"{server_url}/chat/completions", headers=headers, json=payload)
    
    if response.status_code != 200:
        # Log the full error for debugging
        error_msg = f"OpenAI API Error {response.status_code}: {response.text}"
        print(error_msg)
        raise Exception(error_msg)

    try:
        content = response.json()['choices'][0]['message']['content']
        return content
    except (KeyError, IndexError) as e:
        print(f"Unexpected API Response format: {response.text}")
        raise e

# ----------------------------------------------------------------------
# 3. Async Agent Helper
# ----------------------------------------------------------------------
import shutil

# ... (keep your existing imports)

async def sam3_agent_infer(
    image_path: str,
    prompt: str,
    openai_api_key,
    output_dir: str = "agent_output"
) -> str | None:

    def _sync_agent_run():
        # 1. Cleanup previous runs to avoid collisions
        if os.path.exists(output_dir):
            try:
                import shutil
                shutil.rmtree(output_dir)
            except Exception as e:
                print(f"Warning: Could not clear output directory: {e}")
        os.makedirs(output_dir, exist_ok=True)
        
        # 2. Path Setup
        # Absolute path is needed for the OpenAI adapter (to read the file)
        abs_image_path = os.path.abspath(image_path)
        
        # Relative path is REQUIRED for SAM 3 on Windows to avoid WinError 183
        # This prevents os.path.join from discarding the output directory prefix
        try:
            rel_image_path = os.path.relpath(abs_image_path)
        except ValueError:
            # Fallback for different drives, though this might crash again
            rel_image_path = abs_image_path

        # 3. Config
        llm_config = {
            "provider": "openai",
            "model": "gpt-4o",
            "base_url": "https://api.openai.com/v1",
            "api_key": openai_api_key,
            "name": "gpt-4o"
        }
        
        # 4. Partial Functions
        # Note: We pass abs_image_path to the adapter manually if needed, 
        # but the agent will pass the 'image' arg from its history. 
        # We bind the adapter to handle paths correctly.
        
        send_generate_request = partial(
            send_openai_request, 
            server_url=llm_config["base_url"], 
            model=llm_config["model"], 
            api_key=llm_config["api_key"]
        )

        call_sam_service = partial(
            call_sam_service_orig, 
            sam3_processor=_processor
        )

        # 5. Windows Monkey Patch (Safety Net)
        # Even with relative paths, os.rename can fail on Windows if files exist.
        original_rename = os.rename
        def safe_rename_windows(src, dst):
            try:
                if os.path.exists(dst):
                    os.remove(dst)
            except OSError:
                pass
            return original_rename(src, dst)

        if os.name == 'nt':
            os.rename = safe_rename_windows

        try:
            with _model_lock, torch.inference_mode(), torch.autocast(device_type="cuda", dtype=DTYPE):
                # --- KEY CHANGE HERE ---
                # We pass 'rel_image_path' instead of 'abs_image_path'
                output_image_path = run_single_image_inference(
                    rel_image_path,         # <--- CHANGED to Relative
                    prompt,
                    llm_config,
                    send_generate_request,
                    call_sam_service,
                    debug=True,
                    output_dir=output_dir
                )
                
                # The output path returned might be relative; assume it's correct orabspath it
                if output_image_path:
                    return os.path.abspath(output_image_path)
                return None
                
        except Exception as e:
            print(f"Error during agent inference: {e}")
            raise e
        finally:
            if os.name == 'nt':
                os.rename = original_rename

    return await asyncio.to_thread(_sync_agent_run)
# ----------------------------------------------------------------------
# 4. FastAPI App (Same as before)
# ----------------------------------------------------------------------
app = FastAPI(title="SAM 3 Agent (OpenAI Edition)")

class AgentRequest(BaseModel):
    image_path: str
    prompt: str
    output_dir: str = "agent_output"

class AgentResponse(BaseModel):
    status: str
    output_image_path: str | None
    message: str

@app.post("/agent/infer", response_model=AgentResponse)
async def infer_agent(req: AgentRequest):
    if not os.path.exists(req.image_path):
        raise HTTPException(status_code=404, detail=f"Image not found at {req.image_path}")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not set in .env file")
    
    try:
        result_path = await sam3_agent_infer(
            image_path=req.image_path,
            prompt=req.prompt,
            openai_api_key=api_key,
            output_dir=req.output_dir
        )
        
        if result_path:
             return AgentResponse(
                status="success", 
                output_image_path=str(result_path),
                message="Agent reasoning and segmentation complete."
            )
        else:
            return AgentResponse(
                status="no_result", 
                output_image_path=None,
                message="Agent completed but returned no visual output."
            )

    except Exception as e:
        # traceback helps identify if the error is inside SAM3 or our adapter
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)