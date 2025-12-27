from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import ezdxf
import math
import tempfile

app = FastAPI()

# Salli Webnode
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/parse-dxf")
async def parse_dxf(file: UploadFile = File(...)):
    # Tallenna DXF väliaikaisesti
    with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
        tmp.write(await file.read())
        path = tmp.name

    doc = ezdxf.readfile(path)
    msp = doc.modelspace()

    total_length = 0.0

    for e in msp:
        t = e.dxftype()

        if t == "LINE":
            dx = e.dxf.end.x - e.dxf.start.x
            dy = e.dxf.end.y - e.dxf.start.y
            total_length += math.hypot(dx, dy)

        elif t == "CIRCLE":
            total_length += 2 * math.pi * e.dxf.radius

        elif t == "ARC":
            angle = abs(e.dxf.end_angle - e.dxf.start_angle)
            total_length += math.radians(angle) * e.dxf.radius

    return {
        "total_length_mm": round(total_length, 2)
    }

