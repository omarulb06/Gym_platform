#!/usr/bin/env python3
"""
Food Detection Module using YOLOv5
Integrates with existing FastAPI backend for food item detection and classification.
"""

import os
import sys
import cv2
import torch
import numpy as np
from PIL import Image
import io
import base64
from typing import List, Dict, Optional, Tuple
import json
from pathlib import Path

# Add the current directory to Python path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    print("Warning: Ultralytics YOLO not available. Install with: pip install ultralytics")

class FoodDetector:
    """
    Food detection class using YOLOv5/YOLO models
    """
    
    def __init__(self, model_path: str = "yolov8n.pt", confidence_threshold: float = 0.25):
        """
        Initialize the food detector
        
        Args:
            model_path: Path to YOLO model or model name
            confidence_threshold: Minimum confidence for detections
        """
        self.confidence_threshold = confidence_threshold
        self.model = None
        self.model_path = model_path
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.mock_model_loaded = False
        
        # Food-related classes from COCO dataset (common food items)
        self.food_classes = {
            0: "person",  # Not food but common in food images
            16: "dog",  # Not food
            17: "horse",  # Not food
            18: "sheep",  # Not food
            19: "cow",  # Not food
            20: "elephant",  # Not food
            21: "bear",  # Not food
            22: "zebra",  # Not food
            23: "giraffe",  # Not food
            24: "backpack",  # Not food
            25: "umbrella",  # Not food
            26: "handbag",  # Not food
            27: "tie",  # Not food
            28: "suitcase",  # Not food
            29: "frisbee",  # Not food
            30: "skis",  # Not food
            31: "snowboard",  # Not food
            32: "sports ball",  # Not food
            33: "kite",  # Not food
            34: "baseball bat",  # Not food
            35: "baseball glove",  # Not food
            36: "skateboard",  # Not food
            37: "surfboard",  # Not food
            38: "tennis racket",  # Not food
            39: "bottle",  # Food-related
            40: "wine glass",  # Food-related
            41: "cup",  # Food-related
            42: "fork",  # Food-related
            43: "knife",  # Food-related
            44: "spoon",  # Food-related
            45: "bowl",  # Food-related
            46: "banana",  # Food
            47: "apple",  # Food
            48: "sandwich",  # Food
            49: "orange",  # Food
            50: "broccoli",  # Food
            51: "carrot",  # Food
            52: "hot dog",  # Food
            53: "pizza",  # Food
            54: "donut",  # Food
            55: "cake",  # Food
            56: "chair",  # Not food
            57: "couch",  # Not food
            58: "potted plant",  # Not food
            59: "bed",  # Not food
            60: "dining table",  # Food-related
            61: "toilet",  # Not food
            62: "tv",  # Not food
            63: "laptop",  # Not food
            64: "mouse",  # Not food
            65: "remote",  # Not food
            66: "keyboard",  # Not food
            67: "cell phone",  # Not food
            68: "microwave",  # Food-related
            69: "oven",  # Food-related
            70: "toaster",  # Food-related
            71: "sink",  # Food-related
            72: "refrigerator",  # Food-related
            73: "book",  # Not food
            74: "clock",  # Not food
            75: "vase",  # Not food
            76: "scissors",  # Not food
            77: "teddy bear",  # Not food
            78: "hair drier",  # Not food
            79: "toothbrush"  # Not food
        }
        
        # Define food-related classes
        self.food_related_classes = {
            39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 60, 68, 69, 70, 71, 72
        }
        
        self.load_model()
    
    def load_model(self):
        """Load the YOLO model"""
        try:
            if not YOLO_AVAILABLE:
                raise ImportError("Ultralytics YOLO not available")
            
            print(f"Loading YOLO model: {self.model_path}")
            print(f"Current working directory: {os.getcwd()}")
            print(f"Model file exists: {os.path.exists(self.model_path)}")
            
            # Load the actual YOLO model
            self.model = YOLO(self.model_path)
            print(f"✅ YOLO model loaded successfully on device: {self.device}")
            
        except Exception as e:
            print(f"Error loading YOLO model: {e}")
            import traceback
            traceback.print_exc()
            print("Falling back to PyTorch Hub YOLOv5")
            self.load_pytorch_hub_model()
    

    
    def load_pytorch_hub_model(self):
        """Fallback to PyTorch Hub YOLOv5"""
        try:
            import torch
            # Try simple loading first
            self.model = torch.hub.load('ultralytics/yolov5', 'yolov5s', pretrained=True)
            self.model.eval()
            if torch.cuda.is_available():
                self.model.cuda()
            print("PyTorch Hub YOLOv5 model loaded successfully")
        except Exception as e:
            print(f"Error loading PyTorch Hub model: {e}")
            # Try with trust_repo parameter
            try:
                self.model = torch.hub.load('ultralytics/yolov5', 'yolov5s', pretrained=True, trust_repo=True)
                self.model.eval()
                if torch.cuda.is_available():
                    self.model.cuda()
                print("PyTorch Hub YOLOv5 model loaded successfully (with trust_repo)")
            except Exception as e2:
                print(f"Error loading PyTorch Hub model (with trust_repo): {e2}")
                # Try force reload
                try:
                    self.model = torch.hub.load('ultralytics/yolov5', 'yolov5s', pretrained=True, force_reload=True)
                    self.model.eval()
                    if torch.cuda.is_available():
                        self.model.cuda()
                    print("PyTorch Hub YOLOv5 model loaded successfully (force reload)")
                except Exception as e3:
                    print(f"Error loading PyTorch Hub model (force reload): {e3}")
                    self.model = None
    
    def is_food_item(self, class_id: int, class_name: str) -> bool:
        """
        Check if detected item is food-related
        
        Args:
            class_id: Class ID from model
            class_name: Class name from model
            
        Returns:
            bool: True if food-related
        """
        # Check if class_id is in food-related classes
        if class_id in self.food_related_classes:
            return True
        
        # Additional food-related keywords
        food_keywords = [
            'food', 'meal', 'dish', 'plate', 'bowl', 'cup', 'glass', 'bottle',
            'fork', 'knife', 'spoon', 'utensil', 'table', 'kitchen',
            'fruit', 'vegetable', 'meat', 'bread', 'rice', 'pasta',
            'soup', 'salad', 'dessert', 'drink', 'beverage'
        ]
        
        class_name_lower = class_name.lower()
        return any(keyword in class_name_lower for keyword in food_keywords)
    
    def detect_food(self, image_data: bytes) -> Dict:
        """
        Detect food items in image
        
        Args:
            image_data: Image bytes
            
        Returns:
            Dict with detection results
        """
        if self.model is None:
            return {
                "error": "Model not loaded",
                "detections": []
            }
        
        try:
            # Convert bytes to PIL Image
            image = Image.open(io.BytesIO(image_data))
            
            # Run inference
            if hasattr(self.model, 'predict'):
                # Ultralytics YOLO
                results = self.model.predict(image, conf=self.confidence_threshold)
                detections = self._process_ultralytics_results(results)
            elif hasattr(self.model, '__call__'):
                # PyTorch Hub YOLOv5
                results = self.model(image)
                detections = self._process_pytorch_hub_results(image)
            else:
                detections = []
            
            return {
                "success": True,
                "detections": detections,
                "total_food_items": len([d for d in detections if d.get('is_food', False)]),
                "model_used": self.model_path
            }
            
        except Exception as e:
            return {
                "error": f"Detection failed: {str(e)}",
                "detections": []
            }
    
    def _process_ultralytics_results(self, results) -> List[Dict]:
        """Process Ultralytics YOLO results"""
        detections = []
        
        for result in results:
            if hasattr(result, 'boxes') and result.boxes is not None:
                boxes = result.boxes
                if hasattr(boxes, 'xyxy') and boxes.xyxy is not None:
                    for i, (box, conf, cls) in enumerate(zip(boxes.xyxy, boxes.conf, boxes.cls)):
                        if conf >= self.confidence_threshold:
                            class_id = int(cls.item())
                            class_name = self.food_classes.get(class_id, f"class_{class_id}")
                            is_food = self.is_food_item(class_id, class_name)
                            
                            detection = {
                                "name": class_name,
                                "confidence": float(conf.item()),
                                "box": {
                                    "x1": float(box[0].item()),
                                    "y1": float(box[1].item()),
                                    "x2": float(box[2].item()),
                                    "y2": float(box[3].item())
                                },
                                "is_food": is_food,
                                "class_id": class_id
                            }
                            detections.append(detection)
        
        return detections
    

    
    def _process_pytorch_hub_results(self, image) -> List[Dict]:
        """Process PyTorch Hub YOLOv5 results"""
        detections = []
        
        try:
            results = self.model(image)
            predictions = results.pred[0]
            
            for pred in predictions:
                x1, y1, x2, y2, conf, cls = pred
                if conf >= self.confidence_threshold:
                    class_id = int(cls.item())
                    class_name = self.food_classes.get(class_id, f"class_{class_id}")
                    is_food = self.is_food_item(class_id, class_name)
                    
                    detection = {
                        "name": class_name,
                        "confidence": float(conf.item()),
                        "box": {
                            "x1": float(x1.item()),
                            "y1": float(y1.item()),
                            "x2": float(x2.item()),
                            "y2": float(y2.item())
                        },
                        "is_food": is_food,
                        "class_id": class_id
                    }
                    detections.append(detection)
        
        except Exception as e:
            print(f"Error processing PyTorch Hub results: {e}")
        
        return detections
    
    def save_annotated_image(self, image_data: bytes, detections: List[Dict], output_path: str) -> str:
        """
        Save image with bounding boxes drawn
        
        Args:
            image_data: Original image bytes
            detections: List of detections
            output_path: Path to save annotated image
            
        Returns:
            str: Path to saved image
        """
        try:
            # Convert bytes to OpenCV image
            nparr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            # Draw bounding boxes
            for detection in detections:
                if detection.get('is_food', False):
                    box = detection['box']
                    x1, y1, x2, y2 = int(box['x1']), int(box['y1']), int(box['x2']), int(box['y2'])
                    
                    # Draw rectangle
                    cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    
                    # Add label
                    label = f"{detection['name']} {detection['confidence']:.2f}"
                    cv2.putText(img, label, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            # Save image
            cv2.imwrite(output_path, img)
            return output_path
            
        except Exception as e:
            print(f"Error saving annotated image: {e}")
            return ""

def main():
    """Test the food detector"""
    detector = FoodDetector()
    
    # Test with a sample image
    test_image_path = "test_image.jpg"
    if os.path.exists(test_image_path):
        with open(test_image_path, "rb") as f:
            image_data = f.read()
        
        results = detector.detect_food(image_data)
        print(json.dumps(results, indent=2))
        
        # Save annotated image
        if results.get("success"):
            output_path = "static/results/annotated_test.jpg"
            detector.save_annotated_image(image_data, results["detections"], output_path)
            print(f"Annotated image saved to: {output_path}")
    else:
        print(f"Test image not found: {test_image_path}")
        print("Please provide a test image to test the detector")

if __name__ == "__main__":
    main() 