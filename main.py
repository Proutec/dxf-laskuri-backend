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

def polygon_area(points):
    """Shoelace formula"""
    area = 0.0
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2

@app.post("/parse-dxf")
async def parse_dxf(file: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
        tmp.write(await file.read())
        path = tmp.name

    doc = ezdxf.readfile(path)
    msp = doc.modelspace()

    total_length = 0.0
    closed_polygons = []

    for e in msp:
        t = e.dxftype()

        # -------------------------
        # LEIKKAUSPITUUS (KAIKKI)
        # -------------------------

        if t == "LINE":
            dx = e.dxf.end.x - e.dxf.start.x
            dy = e.dxf.end.y - e.dxf.start.y
            total_length += math.hypot(dx, dy)

        elif t == "CIRCLE":
            total_length += 2 * math.pi * e.dxf.radius

        elif t == "ARC":
            angle = abs(e.dxf.end_angle - e.dxf.start_angle)
            total_length += math.radians(angle) * e.dxf.radius

        elif t == "LWPOLYLINE":
            pts = list(e.get_points("xyb"))

            # pituus
            for i in range(len(pts) - 1):
                x1, y1, bulge = pts[i]
                x2, y2, _ = pts[i + 1]
                chord = math.hypot(x2 - x1, y2 - y1)

                if bulge == 0:
                    total_length += chord
                else:
                    theta = 4 * math.atan(abs(bulge))
                    radius = chord / (2 * math.sin(theta / 2))
                    total_length += radius * theta

            # pinta-ala (vain jos suljettu)
            if e.closed:
                area_pts = [(x, y) for x, y, _ in pts]
                closed_polygons.append(polygon_area(area_pts))

        elif t == "POLYLINE":
            if e.is_closed:
                pts = [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices()]
                closed_polygons.append(polygon_area(pts))

            prev = None
            for v in e.vertices():
                if prev:
                    dx = v.dxf.location.x - prev.dxf.location.x
                    dy = v.dxf.location.y - prev.dxf.location.y
                    total_length += math.hypot(dx, dy)
                prev = v

    # --------------------------------
    # ULKOKEHA = SUURIN PINTA-ALA
    # --------------------------------
    outer_area = max(closed_polygons) if closed_polygons else 0.0

    return {
        "total_length_mm": round(total_length, 2),
        "outer_area_mm2": round(outer_area, 2)
    }
