import asyncio
from threading import Lock
from typing import Any, Tuple
from pathlib import Path

import torch
from PIL import Image

from sam3.model_builder import build_sam3_image_model
from sam3.model.sam3_image_processor import Sam3Processor
from sam3.visualization_utils import save_masklet_image, plot_results  # <-- use this


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
# Async inference function
# ----------------------------------------------------------------------
 
async def sam3_infer_image(
    image_path: str,
    prompt: str,
    *,
    do_plot: bool = False,
) -> Tuple[Any, Any, Any]:
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
        masks, boxes, scores
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

            # Optional visualization: save overlay image to disk
            if do_plot:
                # e.g. "test_image_masklet_overlay.png"
                out_path = Path(image_path).with_name(
                    Path(image_path).stem + "_masklet_overlay.png"
                )
                # plot_results should have signature: plot_results(img, results, out_path=None)
                plot_results(image, inference_state, out_path=str(out_path))
                print(f"Saved overlay to {out_path}")

            # Assuming the inference_state carries these keys
            masks = inference_state["masks"]
            boxes = inference_state["boxes"]
            scores = inference_state["scores"]

            return masks, boxes, scores

    return await asyncio.to_thread(_sync_infer)



# ----------------------------------------------------------------------
# Example usage
# ----------------------------------------------------------------------

async def main():
    test_image = sam3_root / "assets" / "images" / "computer.jpeg"
    masks, boxes, scores = await sam3_infer_image(
        image_path=str(test_image),
        prompt="the ram slots next to the cpu",
        do_plot=True,
    )
    print("Masks:", type(masks))
    print("Boxes:", boxes)
    print("Scores:", scores)


if __name__ == "__main__":
    asyncio.run(main())
