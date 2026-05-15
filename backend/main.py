def vision_micro_scratch_detector(image_path: str):
    img = cv2.imread(image_path)
    if img is None:
        return None
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    lap_var = laplacian.var()

    if lap_var > 35:
        return {
            "status": "DEFECTIVE",
            "confidence": min(0.95, lap_var / 50),
            "reason": f"Abnormal micro-surface variation detected"
        }

    return None
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from datetime import datetime
import os
from dotenv import load_dotenv
import google.generativeai as genai
import cv2
import numpy as np
import json
from itertools import product
from ultralytics import YOLO

# Load YOLO model
model_yolo = YOLO("best.pt")

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI()

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

latest_result = None

def preprocess_for_micro_defects(image_path: str):
    img = cv2.imread(image_path)
    if img is None:
        return image_path

    img = cv2.resize(img, (0, 0), fx=0.7, fy=0.7)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(6, 6))
    contrast = clahe.apply(gray)

    grad_x = cv2.Sobel(contrast, cv2.CV_64F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(contrast, cv2.CV_64F, 0, 1, ksize=3)
    gradient = cv2.magnitude(grad_x, grad_y)

    gradient = cv2.normalize(gradient, None, 0, 255, cv2.NORM_MINMAX)
    gradient = gradient.astype("uint8")

    enhanced_rgb = cv2.cvtColor(gradient, cv2.COLOR_GRAY2BGR)

    base, ext = os.path.splitext(image_path)
    enhanced_path = f"{base}_enhanced{ext}"
    cv2.imwrite(enhanced_path, enhanced_rgb)

    return enhanced_path

def split_into_tiles(image_path, rows=3, cols=3):
    img = cv2.imread(image_path)
    if img is None:
        return []
    h, w, _ = img.shape

    tiles = []
    tile_h, tile_w = h // rows, w // cols

    for r, c in product(range(rows), range(cols)):
        tile = img[
            r * tile_h : (r + 1) * tile_h,
            c * tile_w : (c + 1) * tile_w
        ]
        base, ext = os.path.splitext(image_path)
        tile_path = f"{base}_tile_{r}_{c}{ext}"
        cv2.imwrite(tile_path, tile)
        tiles.append(tile_path)

    return tiles

def analyze_image_with_yolo(image_path: str):
    try:
        results = model_yolo(image_path)
        
        # Save the annotated image
        base, ext = os.path.splitext(image_path)
        annotated_path = f"{base}_annotated{ext}"
        results[0].save(filename=annotated_path)
        annotated_filename = os.path.basename(annotated_path)
        
        detections = results[0].boxes
        
        has_defect = False
        max_defect_conf = 0.0
        defect_count = 0
        
        if len(detections) > 0:
            for box in detections:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                if cls_id == 0:  # 0 is 'damaged', 1 is 'intact'
                    has_defect = True
                    defect_count += 1
                    if conf > max_defect_conf:
                        max_defect_conf = conf

        if has_defect:
            return {
                "status": "DEFECTIVE",
                "confidence": round(max_defect_conf, 2),
                "reason": f"Detected {defect_count} defect(s) using YOLO model.",
                "annotated_image": annotated_filename
            }
        else:
            # Maybe detected intact, or nothing
            return {
                "status": "INTACT",
                "confidence": 0.95,
                "reason": "No defects detected by YOLO model.",
                "annotated_image": annotated_filename
            }
    except Exception as e:
        print("YOLO Inference error:", e)
        return {
            "status": "INTACT",
            "confidence": 0.4,
            "reason": f"YOLO Inference error: {str(e)}",
            "annotated_image": None
        }

def analyze_image_with_llm(image_path: str):
    try:
        vision_hit = vision_micro_scratch_detector(image_path)
        if vision_hit:
            return vision_hit

        model = genai.GenerativeModel("gemini-1.5-flash")

        enhanced_path = preprocess_for_micro_defects(image_path)

        original_tiles = split_into_tiles(image_path)
        enhanced_tiles = split_into_tiles(enhanced_path)

        def run_llm(path):
            with open(path, "rb") as img:
                image_bytes = img.read()

            prompt = (
                "You are a precision micro-defect inspection AI for mobile glass screens.\n"
                "- Ignore normal lighting reflections and glare.\n"
                "- Only classify as DEFECTIVE if there is a clear, continuous scratch, crack, deep scuff, or physical damage.\n"
                "- Minor noise, dust, or light reflection lines are NOT defects.\n"
                "- If uncertain, classify as INTACT.\n\n"
                "Respond ONLY in strict JSON:\n"
                "{ \"status\": \"DEFECTIVE or INTACT\", "
                "\"confidence\": number between 0.5 and 1.0, "
                "\"reason\": short technical explanation }\n"
            )

            response = model.generate_content(
                [
                    prompt,
                    {
                        "mime_type": "image/jpeg",
                        "data": image_bytes
                    }
                ]
            )

            text = response.text.strip()

            # Remove markdown code fences if present
            if text.startswith("```"):
                text = text.split("```")[1]

            return json.loads(text)

        results = []

        for tile in original_tiles + enhanced_tiles:
            try:
                results.append(run_llm(tile))
            except Exception:
                continue

        # ---- VOTING LOGIC (reduce false positives) ----
        defective_results = [
            r for r in results
            if r.get("status") == "DEFECTIVE" and r.get("confidence", 0) >= 0.7
        ]

        # Require at least 3 strong defective tiles
        if len(defective_results) >= 3:
            avg_conf = sum(r.get("confidence", 0.8) for r in defective_results) / len(defective_results)
            return {
                "status": "DEFECTIVE",
                "confidence": round(avg_conf, 2),
                "reason": "Multiple tiles confirmed physical surface damage"
            }

        return {
            "status": "INTACT",
            "confidence": 0.85,
            "reason": "No consistent multi-tile physical defects detected"
        }

    except Exception as e:
        return {
            "status": "INTACT",
            "confidence": 0.4,
            "reason": f"Inspection fallback (LLM error): {str(e)}"
        }

@app.post("/upload/")
async def upload(file: UploadFile = File(...)):
    global latest_result

    filename = f"{int(datetime.now().timestamp())}_{file.filename}"
    path = os.path.join(UPLOAD_DIR, filename)

    with open(path, "wb") as f:
        f.write(await file.read())

    try:
        # Priority: YOLO model
        analysis = analyze_image_with_yolo(path)
        
        # Fallback to LLM only if YOLO is unsure or we want more details?
        # For now, let's stick to YOLO as requested.
    except Exception as e:
        analysis = {
            "status": "INTACT",
            "confidence": 0.3,
            "reason": f"Backend processing fallback: {str(e)}",
            "annotated_image": None
        }

    latest_result = {
        "image": filename,
        "status": analysis["status"],
        "confidence": analysis["confidence"],
        "reason": analysis["reason"],
        "annotated_image": analysis.get("annotated_image")
    }

    return {"message": "Uploaded"}

@app.get("/latest/")
def get_latest():
    return latest_result