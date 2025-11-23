import cv2
import matplotlib.pyplot as plt

# 1. Define the file path
image_path = 'sam3/assets/images/computer_6.jpg' 

# 2. Read the image
image = cv2.imread(image_path)

# 3. Define Bounding Box Coordinates (Normalized, between 0 and 1)
# Example: These normalized values correspond to the original pixel values (190, 235) and (325, 425)
# on an image resized to 930x523.
x1_norm, y1_norm = 0.25, 0.36   # Normalized top-left x, y
x2_norm, y2_norm = 0.46, 0.62  # Normalized bottom-right x, y

# Get image dimensions
h, w = image.shape[:2]

# Convert normalized coordinates to pixel coordinates
x1_px = int(x1_norm * w)
y1_px = int(y1_norm * h)
x2_px = int(x2_norm * w)
y2_px = int(y2_norm * h)

padding = 50  # Define padding value
x1_raw, y1_raw = x1_px - padding, y1_px - padding
x2_raw, y2_raw = x2_px + padding, y2_px + padding

# Ensure coordinates are within image bounds (0 to width/height - 1)
x1 = max(0, x1_raw)
y1 = max(0, y1_raw)
x2 = min(w, x2_raw)
y2 = min(h, y2_raw)

start_point = (x1, y1)
end_point = (x2, y2)
# 4. Draw the box (Green color, thickness 3)
image_with_box = cv2.rectangle(image, start_point, end_point, (0, 255, 0), 3)

# 5. Display
plt.imshow(cv2.cvtColor(image_with_box, cv2.COLOR_BGR2RGB))
plt.axis("off")
plt.show()