from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import ezdxf
import math
import tempfile
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def arc_length(radius, start_angle, end_angle):
    angle = abs(end_angle - start_angle)
    return math.radians(angle) * radius

@app.post("/calculate")
async def calculate_dxf(file: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    doc = ezdxf.readfile(tmp_path)
    msp = doc.modelspace()

    total_length = 0.0

    for e in msp:
        if e.dxftype() == "LINE":
            total_length += math.dist(e.dxf.start, e.dxf.end)

        elif e.dxftype() == "CIRCLE":
            total_length += 2 * math.pi * e.dxf.radius

        elif e.dxftype() == "ARC":
            total_length += arc_length(
                e.dxf.radius,
                e.dxf.start_angle,
                e.dxf.end_angle
            )

    os.remove(tmp_path)

    return {"total_length_mm": round(total_length, 2)}
