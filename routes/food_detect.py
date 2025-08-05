"""
Food Detection API Routes
Integrates YOLOv5 food detection with existing FastAPI backend
"""

import os
import sys
import time
import uuid
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Form
from fastapi.responses import JSONResponse
import json

# Import the food detector
from food_detect import FoodDetector

# Create router
router = APIRouter(prefix="/api/food-detect", tags=["Food Detection"])

# Global detector instance
detector = None

def get_detector():
    """Get or create the food detector instance"""
    global detector
    # Force fresh creation for debugging
    print("🔧 Creating new FoodDetector instance for API...")
    detector = FoodDetector()
    print(f"🔧 Detector created - Model loaded: {detector.model is not None}")
    if detector.model is None:
        print("❌ Model failed to load in API context")
    else:
        print("✅ Model loaded successfully in API context")
    return detector

@router.post("/detect")
async def detect_food_items(
    file: UploadFile = File(...),
    save_annotated: bool = Form(False),
    confidence_threshold: float = Form(0.25)
):
    """
    Detect food items in uploaded image
    
    Args:
        file: Image file to analyze
        save_annotated: Whether to save annotated image
        confidence_threshold: Minimum confidence for detections
        
    Returns:
        JSON response with detection results
    """
    try:
        # Validate file type
        if not file.content_type or not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        # Read image data
        image_data = await file.read()
        
        # Get detector
        detector = get_detector()
        
        # Update confidence threshold if different
        if confidence_threshold != detector.confidence_threshold:
            detector.confidence_threshold = confidence_threshold
        
        # Perform detection
        start_time = time.time()
        results = detector.detect_food(image_data)
        inference_time = time.time() - start_time
        
        # Add metadata
        results["metadata"] = {
            "inference_time": inference_time,
            "image_size": len(image_data),
            "filename": file.filename,
            "timestamp": datetime.now().isoformat()
        }
        
        # Save annotated image if requested
        if save_annotated and results.get("success"):
            # Create results directory if it doesn't exist
            results_dir = Path("static/results")
            results_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid.uuid4())[:8]
            filename = f"annotated_{timestamp}_{unique_id}.jpg"
            output_path = results_dir / filename
            
            # Save annotated image
            saved_path = detector.save_annotated_image(image_data, results["detections"], str(output_path))
            if saved_path:
                results["annotated_image_path"] = f"/static/results/{filename}"
        
        return JSONResponse(content=results)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Detection failed: {str(e)}")

@router.post("/detect-simple")
async def detect_food_simple(file: UploadFile = File(...)):
    """
    Simple food detection endpoint
    
    Args:
        file: Image file to analyze
        
    Returns:
        Simplified JSON response with food detections
    """
    try:
        # Validate file type
        if not file.content_type or not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        # Read image data
        image_data = await file.read()
        
        # Get detector
        detector = get_detector()
        

        
        # Perform detection
        results = detector.detect_food(image_data)
        
        if not results.get("success"):
            return JSONResponse(content={
                "error": results.get("error", "Detection failed"),
                "detections": []
            })
        
        # Filter only food items and simplify response
        food_detections = []
        for detection in results["detections"]:
            if detection.get("is_food", False):
                food_detections.append({
                    "name": detection["name"],
                    "confidence": detection["confidence"],
                    "box": detection["box"]
                })
        
        return JSONResponse(content={
            "success": True,
            "detections": food_detections,
            "total_food_items": len(food_detections)
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Detection failed: {str(e)}")

@router.get("/status")
async def get_detector_status():
    """
    Get detector status and model information
    
    Returns:
        JSON response with detector status
    """
    print("🔍 Status endpoint called!")
    try:
        detector = get_detector()
        print(f"🔍 Detector obtained: {detector}")
        print(f"🔍 Model loaded: {detector.model is not None}")
        
        # Import YOLO_AVAILABLE from food_detect module
        from food_detect import YOLO_AVAILABLE
        
        status = {
            "model_loaded": detector.model is not None,
            "model_path": detector.model_path,
            "device": detector.device,
            "confidence_threshold": detector.confidence_threshold,
            "yolo_available": YOLO_AVAILABLE,
            "model_type": "yolo",
            "mock_model": False,
            "model_status": "real"
        }
        
        print(f"🔍 Returning status: {status}")
        return JSONResponse(content=status)
        
    except Exception as e:
        print(f"❌ Status check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")

@router.post("/test")
async def test_detection():
    """
    Test endpoint to verify detector is working
    
    Returns:
        JSON response with test results
    """
    try:
        detector = get_detector()
        
        if detector.model is None:
            return JSONResponse(content={
                "success": False,
                "error": "Model not loaded",
                "message": "Please check model installation and try again"
            })
        
        return JSONResponse(content={
            "success": True,
            "message": "Detector is ready",
            "model_info": {
                "path": detector.model_path,
                "device": detector.device,
                "confidence_threshold": detector.confidence_threshold
            }
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Test failed: {str(e)}")

@router.get("/models")
async def get_available_models():
    """
    Get list of available YOLO models
    
    Returns:
        JSON response with available models
    """
    models = [
        {
            "name": "yolov8n",
            "description": "YOLOv8 Nano - Fastest, smallest model",
            "size": "6.7MB",
            "speed": "Fast",
            "accuracy": "Good"
        },
        {
            "name": "yolov8s", 
            "description": "YOLOv8 Small - Balanced speed and accuracy",
            "size": "22.6MB",
            "speed": "Medium",
            "accuracy": "Better"
        },
        {
            "name": "yolov8m",
            "description": "YOLOv8 Medium - Higher accuracy",
            "size": "52.2MB", 
            "speed": "Slower",
            "accuracy": "High"
        },
        {
            "name": "yolov8l",
            "description": "YOLOv8 Large - Highest accuracy",
            "size": "87.7MB",
            "speed": "Slow",
            "accuracy": "Highest"
        },
        {
            "name": "yolov8x",
            "description": "YOLOv8 Extra Large - Maximum accuracy",
            "size": "136.2MB",
            "speed": "Slowest",
            "accuracy": "Maximum"
        }
    ]
    
    return JSONResponse(content={"models": models})

@router.post("/switch-model")
async def switch_model(model_name: str = Form(...)):
    """
    Switch to a different YOLO model
    
    Args:
        model_name: Name of the model to switch to
        
    Returns:
        JSON response with switch results
    """
    try:
        global detector
        
        # Validate model name
        valid_models = ["yolov8n", "yolov8s", "yolov8m", "yolov8l", "yolov8x"]
        if model_name not in valid_models:
            raise HTTPException(status_code=400, detail=f"Invalid model name. Valid options: {valid_models}")
        
        # Create new detector with specified model
        detector = FoodDetector(model_path=f"{model_name}.pt")
        
        return JSONResponse(content={
            "success": True,
            "message": f"Switched to {model_name}",
            "model_loaded": detector.model is not None
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Model switch failed: {str(e)}") 