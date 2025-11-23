from ultralytics import YOLO

# 1. Load your custom trained model
# Replace 'path/to/best.pt' with the actual path to your trained model
model = YOLO("runs/detect/train/weights/best.pt")

# 2. Run inference on an image or video
# source can be an image path, video path, directory, or URL
results = model.predict(
    source="sam3/assets/images/computer_3.jpg",
    conf=0.25,      # Confidence threshold (0-1)
    save=True,      # Save the annotated image to 'runs/detect/predict'
    show=True       # Display the image immediately (useful for testing)
)