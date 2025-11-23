from threading import Lock
from typing import Any, Tuple, List
from pathlib import Path
import os
import asyncio
import torch
import numpy as np
from PIL import Image
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import base64
import io
import uuid

# ----------------------------------------------------------------------
# Imports from your SAM3 package
# ----------------------------------------------------------------------
from sam3.model_builder import build_sam3_image_model
from sam3.model.sam3_image_processor import Sam3Processor
from sam3.visualization_utils import plot_results

# ----------------------------------------------------------------------
# 1. Model & Processor Setup
# ----------------------------------------------------------------------

sam3_root = Path(__file__).resolve().parents[1] / "sam3"
bpe_path = sam3_root / "assets" / "bpe_simple_vocab_16e6.txt.gz"

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

_model = build_sam3_image_model(bpe_path=str(bpe_path))
_model.to(DEVICE)
_model.eval()

# Standard Processor (assuming add_geometric_prompt is now implemented here)
_processor = Sam3Processor(_model, confidence_threshold=0.5)

_model_lock = Lock()


# ----------------------------------------------------------------------
# 2. Core Inference Logic
# ----------------------------------------------------------------------

async def sam3_infer_image(
    prompt: str | None = None,
    boxes: list[list[float]] | None = None, # Input: [[x1, y1, x2, y2], ...]
    image_path: str | None = None,
    base64_image: str | None = None,
    *,
    do_plot: bool = False,
    output_dir: str = "agent_output"
) -> Tuple[Any, Any, Any, str | None]:
    
    if do_plot:
        os.makedirs(output_dir, exist_ok=True)

    def _sync_infer():
        with _model_lock:
            # -------------------------------------------------
            # A. Load Image
            # -------------------------------------------------
            if base64_image:
                if "," in base64_image:
                    header, encoded = base64_image.split(",", 1)
                else:
                    encoded = base64_image
                image_data = base64.b64decode(encoded)
                image = Image.open(io.BytesIO(image_data)).convert("RGB")
                input_stem = f"upload_{uuid.uuid4().hex[:8]}"
                save_dir = Path(output_dir)
            elif image_path:
                image = Image.open(image_path).convert("RGB")
                input_stem = Path(image_path).stem
                save_dir = Path(image_path).parent
            else:
                raise ValueError("No image provided")

            # Get dimensions for Normalization
            img_w, img_h = image.size

            # -------------------------------------------------
            # B. Initialize State
            # -------------------------------------------------
            inference_state = _processor.set_image(image)
            _processor.reset_all_prompts(inference_state)

            # -------------------------------------------------
            # C. Apply Text Prompt
            # -------------------------------------------------
            if prompt:
                inference_state = _processor.set_text_prompt(
                    state=inference_state,
                    prompt=prompt,
                )

            # -------------------------------------------------
            # D. Apply Geometric Boxes
            # -------------------------------------------------
            if boxes and len(boxes) > 0:
                
                for box in boxes:
                    # INPUT: [x_min, y_min, x_max, y_max] in Pixels
                    x1, y1, x2, y2 = box

                    # 1. Calculate Width and Height (Pixels)
                    w_px = x2 - x1
                    h_px = y2 - y1

                    # 2. Calculate Center (Pixels)
                    cx_px = x1 + (w_px / 2)
                    cy_px = y1 + (h_px / 2)

                    # 3. Normalize to [0, 1] for the model
                    norm_cx = cx_px / img_w
                    norm_cy = cy_px / img_h
                    norm_w = w_px / img_w
                    norm_h = h_px / img_h
                    
                    # TARGET: [center_x, center_y, width, height] Normalized
                    geometric_box = [norm_cx, norm_cy, norm_w, norm_h]

                    # 4. Call method on the processor
                    inference_state = _processor.add_geometric_prompt(
                        box=geometric_box,
                        label=True,  # Assuming user wants to INCLUDE this area
                        state=inference_state
                    )

            # -------------------------------------------------
            # E. Visualization & Output
            # -------------------------------------------------
            overlay_path: str | None = None
            if do_plot:
                filename = f"{input_stem}_masklet_overlay.png"
                out_path = save_dir / filename
                out_path.parent.mkdir(parents=True, exist_ok=True)
                
                plot_results(image, inference_state, out_path=str(out_path))
                overlay_path = str(out_path)

            masks = inference_state["masks"]
            boxes_out = inference_state["boxes"]
            scores = inference_state["scores"]

            return masks, boxes_out, scores, overlay_path

    return await asyncio.to_thread(_sync_infer)


# ----------------------------------------------------------------------
# 3. FastAPI App
# ----------------------------------------------------------------------

app = FastAPI(title="SAM3 Image Inference API")

class InferenceRequest(BaseModel):
    prompt: str | None = None
    boxes: list[list[float]] | None = None  # Format: [[x1, y1, x2, y2], ...]
    image_path: str | None = None
    base64_image: str | None = None
    do_plot: bool = False

class InferenceResponse(BaseModel):
    num_objects: int
    boxes: list[list[float]]
    scores: list[float]
    overlay_path: str | None = None

@app.post("/infer", response_model=InferenceResponse)
async def infer(req: InferenceRequest):
    
    # 1. Validate Image Source
    if not req.image_path and not req.base64_image:
        raise HTTPException(status_code=400, detail="Provide either 'image_path' or 'base64_image'")

    # 2. Validate Prompt Strategy (Text OR Boxes)
    if not req.prompt and not req.boxes:
        raise HTTPException(status_code=400, detail="Provide either 'prompt' (text) or 'boxes'")

    try:
        masks, boxes, scores, overlay_path = await sam3_infer_image(
            prompt=req.prompt,
            boxes=req.boxes,
            image_path=req.image_path,
            base64_image=req.base64_image,
            do_plot=req.do_plot,
        )

        # Convert tensors to lists for JSON serialization
        boxes_list = boxes.detach().cpu().tolist()
        scores_list = scores.detach().cpu().tolist()

        return InferenceResponse(
            num_objects=len(scores_list),
            boxes=boxes_list,
            scores=scores_list,
            overlay_path=overlay_path,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))