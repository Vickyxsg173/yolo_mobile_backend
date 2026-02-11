def vision_micro_scratch_detector(image_path: str):
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    lap_var = laplacian.var()

    if lap_var > 18:   
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

    enhanced_path = image_path.replace(".", "_enhanced.")
    cv2.imwrite(enhanced_path, enhanced_rgb)

    return enhanced_path

def split_into_tiles(image_path, rows=3, cols=3):
    img = cv2.imread(image_path)
    h, w, _ = img.shape

    tiles = []
    tile_h, tile_w = h // rows, w // cols

    for r, c in product(range(rows), range(cols)):
        tile = img[
            r * tile_h : (r + 1) * tile_h,
            c * tile_w : (c + 1) * tile_w
        ]
        tile_path = image_path.replace(
            ".", f"_tile_{r}_{c}."
        )
        cv2.imwrite(tile_path, tile)
        tiles.append(tile_path)

    return tiles

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
                "You are a MICRO-DEFECT inspection AI for glossy glass surfaces.\n"
                "- Assume strong lighting reflections.\n"
                "- Treat ANY scratch, hairline mark, scuff, swirl, or reflection break as DEFECTIVE.\n"
                "- If uncertain, mark DEFECTIVE.\n\n"
                "Respond ONLY in strict JSON:\n"
                "{ \"status\": \"DEFECTIVE or INTACT\", "
                "\"confidence\": number between 0.75 and 1.0, "
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

            return json.loads(response.text)

        results = []

        for tile in original_tiles + enhanced_tiles:
            try:
                results.append(run_llm(tile))
            except Exception:
                continue

        for r in results:
            if r.get("status") == "DEFECTIVE":
                return {
                    "status": "DEFECTIVE",
                    "confidence": r.get("confidence", 0.8),
                    "reason": r.get("reason", "Micro surface defect detected")
                }

        return {
            "status": "INTACT",
            "confidence": 0.75,
            "reason": "No visible surface defects after tiled inspection"
        }

    except Exception as e:
        return {
            "status": "DEFECTIVE",
            "confidence": 0.6,
            "reason": f"Inspection uncertainty fallback: {str(e)}"
        }

@app.post("/upload/")
async def upload(file: UploadFile = File(...)):
    global latest_result

    filename = f"{int(datetime.now().timestamp())}_{file.filename}"
    path = os.path.join(UPLOAD_DIR, filename)

    with open(path, "wb") as f:
        f.write(await file.read())

    analysis = analyze_image_with_llm(path)

    latest_result = {
        "image": filename,
        "status": analysis["status"],
        "confidence": analysis["confidence"],
        "reason": analysis["reason"]
    }

    return {"message": "Uploaded"}

@app.get("/latest/")
def get_latest():
    return latest_result