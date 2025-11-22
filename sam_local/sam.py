from threading import Lock
from typing import Any, Tuple
from pathlib import Path

import asyncio
import torch
from PIL import Image
from fastapi import FastAPI
from pydantic import BaseModel

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
    image_path: str,
    prompt: str,
    *,
    do_plot: bool = False,
) -> Tuple[Any, Any, Any, str | None]:
    """
    Async wrapper around SAM3 image model.

    - Keeps the model and processor loaded globally in memory.
    - Runs the heavy inference work in a background thread (asyncio.to_thread).
    - Uses the same logic as your sync example:
        * set_image
        * reset_all_prompts
        * set_text_prompt
        * optional plot_results that SAVES the image

    Returns:
        masks, boxes, scores, overlay_path
    """

    def _sync_infer():
        with _model_lock:
            # Load image
            image = Image.open(image_path).convert("RGB")

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

            # Optional visualization: save overlay image to disk
            if do_plot:
                out_path = Path(image_path).with_name(
                    Path(image_path).stem + "_masklet_overlay.png"
                )
                # plot_results should have signature: plot_results(img, results, out_path=None)
                plot_results(image, inference_state, out_path=str(out_path))
                overlay_path = str(out_path)

            # Assuming the inference_state carries these keys
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


@app.post("/infer", response_model=InferenceResponse)
async def infer(req: InferenceRequest):
    """
    Run SAM3 on a given image_path + prompt.

    The model is loaded once globally and reused across calls.
    """
    masks, boxes, scores, overlay_path = await sam3_infer_image(
        image_path=req.image_path,
        prompt=req.prompt,
        do_plot=req.do_plot,
    )

    # Convert tensors to plain Python lists for JSON
    boxes_list = boxes.detach().cpu().tolist()
    scores_list = scores.detach().cpu().tolist()

    return InferenceResponse(
        num_objects=len(scores_list),
        boxes=boxes_list,
        scores=scores_list,
        overlay_path=overlay_path,
    )
