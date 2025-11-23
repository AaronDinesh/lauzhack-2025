from ultralytics import YOLO

def main():
    # 1. Load the model
    # Use ONLY ONE of the following methods. 
    # 'yolo11n.pt' is best for fine-tuning (training on your own data).
    model = YOLO("yolo11n.pt") 

    # 2. Train the model
    # Ensure the path to data.yaml is correct relative to where you run this script
    results = model.train(
        data="yolo_pc_part/training_dataset/data.yaml", 
        epochs=25, 
        imgsz=640
    )

if __name__ == "__main__":
    # This guard is strictly required for multiprocessing (DataLoaders)
    main()