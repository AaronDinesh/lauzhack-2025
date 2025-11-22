from threading import Lock
from typing import Any, Tuple
from pathlib import Path

import asyncio
import torch
from PIL import Image
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os

import base64
import io
import uuid
from pathlib import Path
from PIL import Image

from sam3.model_builder import build_sam3_image_model
from sam3.model.sam3_image_processor import Sam3Processor
from sam3.visualization_utils import plot_results  # must support out_path=...


# ----------------------------------------------------------------------
# Model & processor: load ONCE at import time
# ----------------------------------------------------------------------

# Root of your sam3 repo (adapt this if your layout is different)
sam3_root = Path(__file__).resolve().parents[1] / "sam3"
bpe_path = sam3_root / "assets" / "bpe_simple_vocab_16e6.txt.gz"

# Choose device
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# Build and move model to device once
_model = build_sam3_image_model(bpe_path=str(bpe_path))
_model.to(DEVICE)  # make sure model is on the right device
_model.eval()

# Create a single processor instance
_processor = Sam3Processor(_model, confidence_threshold=0.5)

# Optional: lock to avoid concurrent access to the same model/processor
_model_lock = Lock()


# ----------------------------------------------------------------------
# Core async inference helper (internal)
# ----------------------------------------------------------------------

async def sam3_infer_image(
    prompt: str,
    image_path: str | None = None,
    base64_image: str | None = None,
    *,
    do_plot: bool = False,
    output_dir: str = "agent_output" # Default folder for base64 outputs
) -> Tuple[Any, Any, Any, str | None]:
    
    # Create output directory if it doesn't exist
    if do_plot:
        os.makedirs(output_dir, exist_ok=True)

    def _sync_infer():
        with _model_lock:
            # -------------------------------------------------
            # 1. Load Image (Base64 OR File Path)
            # -------------------------------------------------
            if base64_image:
                # Remove header if present (e.g., "data:image/jpeg;base64,")
                if "," in base64_image:
                    header, encoded = base64_image.split(",", 1)
                else:
                    encoded = base64_image
                
                image_data = base64.b64decode(encoded)
                image = Image.open(io.BytesIO(image_data)).convert("RGB")
                
                # Generate a unique name for the output file since we don't have a path
                input_stem = f"upload_{uuid.uuid4().hex[:8]}"
                save_dir = Path(output_dir)
                
            elif image_path:
                image = Image.open(image_path).convert("RGB")
                input_stem = Path(image_path).stem
                # Save to same directory as input image, or use default
                save_dir = Path(image_path).parent
            else:
                raise ValueError("Either image_path or base64_image must be provided.")

            # -------------------------------------------------
            # 2. Standard SAM 3 Inference
            # -------------------------------------------------
            # Set the image in the processor
            inference_state = _processor.set_image(image)

            # Reset prompts before applying a new one
            _processor.reset_all_prompts(inference_state)

            # Apply text prompt
            inference_state = _processor.set_text_prompt(
                state=inference_state,
                prompt=prompt,
            )

            overlay_path: str | None = None

            # -------------------------------------------------
            # 3. Visualization / Saving
            # -------------------------------------------------
            if do_plot:
                # Construct output path
                filename = f"{input_stem}_masklet_overlay.png"
                out_path = save_dir / filename
                
                # Ensure the directory exists (in case of file path parent)
                out_path.parent.mkdir(parents=True, exist_ok=True)

                # plot_results(img, results, out_path=None)
                plot_results(image, inference_state, out_path=str(out_path))
                overlay_path = str(out_path)

            # Extract results
            masks = inference_state["masks"]
            boxes = inference_state["boxes"]
            scores = inference_state["scores"]

            return masks, boxes, scores, overlay_path

    return await asyncio.to_thread(_sync_infer)


# ----------------------------------------------------------------------
# FastAPI app
# ----------------------------------------------------------------------

app = FastAPI(title="SAM3 Image Inference API")


class InferenceRequest(BaseModel):
    image_path: str  # path on the server where the image is located
    prompt: str
    do_plot: bool = False


class InferenceResponse(BaseModel):
    num_objects: int
    boxes: list[list[float]]
    scores: list[float]
    overlay_path: str | None = None


class InferenceRequest(BaseModel):
    prompt: str
    image_path: str | None = None
    base64_image: str | None = None  # Add this field
    do_plot: bool = False

@app.post("/infer", response_model=InferenceResponse)
async def infer(req: InferenceRequest):
    
    # Validation: Ensure at least one source is provided
    if not req.image_path and not req.base64_image:
        raise HTTPException(status_code=400, detail="Provide either 'image_path' or 'base64_image'")

    try:
        masks, boxes, scores, overlay_path = await sam3_infer_image(
            prompt=req.prompt,
            image_path=req.image_path,
            base64_image=req.base64_image,
            do_plot=req.do_plot,
        )

        # Convert tensors to lists
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