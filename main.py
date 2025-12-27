from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import ezdxf
import math
import tempfile

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/parse-dxf")
async def parse_dxf(file: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
        tmp.write(await file.read())
        path = tmp.name

    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    total_length = 0.0

    for e in msp:
        t = e.dxftype()

        # 1. Yksittäiset viivat
        if t == "LINE":
            dx = e.dxf.end.x - e.dxf.start.x
            dy = e.dxf.end.y - e.dxf.start.y
            total_length += math.hypot(dx, dy)

        # 2. Ympyrät
        elif t == "CIRCLE":
            total_length += 2 * math.pi * e.dxf.radius

        # 3. Kaaret
        elif t == "ARC":
            angle = abs(e.dxf.end_angle - e.dxf.start_angle)
            total_length += math.radians(angle) * e.dxf.radius

        # 4. LWPOLYLINE (tärkein puuttuva osa)
        elif t == "LWPOLYLINE":
            points = list(e.get_points("xyb"))

            for i in range(len(points) - 1):
                x1, y1, bulge = points[i]
                x2, y2, _ = points[i + 1]

                chord = math.hypot(x2 - x1, y2 - y1)

                if bulge == 0:
                    # suora segmentti
                    total_length += chord
                else:
                    # kaari segmentti
                    theta = 4 * math.atan(abs(bulge))
                    radius = chord / (2 * math.sin(theta / 2))
                    total_length += radius * theta

        # 5. Vanha POLYLINE
        elif t == "POLYLINE":
            vertices = e.vertices()
            prev = None
            for v in vertices:
                if prev:
                    dx = v.dxf.location.x - prev.dxf.location.x
                    dy = v.dxf.location.y - prev.dxf.location.y
                    total_length += math.hypot(dx, dy)
                prev = v

    return {"total_length_mm": round(total_length, 2)}
