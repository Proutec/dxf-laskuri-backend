# --------------------------------------------------
# HEADLESS MATPLOTLIB
# --------------------------------------------------
import matplotlib
matplotlib.use("Agg")

# --------------------------------------------------
# IMPORTIT
# --------------------------------------------------
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import ezdxf
import io
import math
import matplotlib.pyplot as plt
from ezdxf.math import Vec2

# --------------------------------------------------
# FASTAPI
# --------------------------------------------------
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------
# APUTOIMINNOT
# --------------------------------------------------

def dist(p1, p2):
    return math.dist(p1, p2)

def arc_length(radius, start, end):
    return math.radians(abs(end - start)) * radius

# --------------------------------------------------
# DXF LUKU (TEKSTI)
# --------------------------------------------------

def load_dxf(upload: UploadFile):
    content = upload.file.read()
    text = content.decode("utf-8", errors="ignore")
    return ezdxf.read(io.StringIO(text))

# --------------------------------------------------
# SPLINE → POLYLINE
# --------------------------------------------------

def spline_length(spline, segments=100):
    length = 0.0
    points = spline.flattening(distance=0.5)
    prev = None
    for p in points:
        if prev:
            length += dist((prev.x, prev.y), (p.x, p.y))
        prev = p
    return length

# --------------------------------------------------
# PITUUDEN LASKENTA (KAIKKI GEOMETRIAT)
# --------------------------------------------------

def calculate_total_length(doc):
    msp = doc.modelspace()
    total = 0.0

    def handle(e):
        nonlocal total
        t = e.dxftype()

        if t == "LINE":
            total += dist(e.dxf.start[:2], e.dxf.end[:2])

        elif t == "CIRCLE":
            total += 2 * math.pi * e.dxf.radius

        elif t == "ARC":
            total += arc_length(
                e.dxf.radius,
                e.dxf.start_angle,
                e.dxf.end_angle
            )

        elif t == "LWPOLYLINE":
            pts = [Vec2(p[0], p[1]) for p in e.get_points()]
            for i in range(len(pts) - 1):
                total += dist(pts[i], pts[i + 1])
            if e.closed:
                total += dist(pts[-1], pts[0])

        elif t == "POLYLINE":
            pts = [Vec2(v.dxf.location.x, v.dxf.location.y) for v in e.vertices]
            for i in range(len(pts) - 1):
                total += dist(pts[i], pts[i + 1])
            if e.is_closed:
                total += dist(pts[-1], pts[0])

        elif t == "SPLINE":
            total += spline_length(e)

    # modelspace + blockit (transformoidut)
    for e in msp:
        if e.dxftype() == "INSERT":
            block = doc.blocks.get(e.dxf.name)
            for be in block:
                try:
                    handle(be)
                except:
                    pass
        else:
            handle(e)

    return total

# --------------------------------------------------
# API: PITUUS
# --------------------------------------------------

@app.post("/parse-dxf")
async def parse_dxf(file: UploadFile = File(...)):
    try:
        doc = load_dxf(file)
        length = calculate_total_length(doc)

        return {"total_length_mm": round(length, 2)}

    except Exception as e:
        print("DXF ERROR:", e)
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

# --------------------------------------------------
# API: ESIKATSELU
# --------------------------------------------------

@app.post("/preview-dxf")
async def preview_dxf(file: UploadFile = File(...)):
    doc = load_dxf(file)
    msp = doc.modelspace()

    fig, ax = plt.subplots()
    ax.set_aspect("equal")
    ax.axis("off")

    for e in msp:
        t = e.dxftype()

        if t == "LINE":
            ax.plot(
                [e.dxf.start.x, e.dxf.end.x],
                [e.dxf.start.y, e.dxf.end.y],
                "k"
            )

        elif t == "LWPOLYLINE":
            pts = list(e.get_points())
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            if e.closed:
                xs.append(xs[0])
                ys.append(ys[0])
            ax.plot(xs, ys, "k")

        elif t == "SPLINE":
            pts = list(e.flattening(distance=0.5))
            xs = [p.x for p in pts]
            ys = [p.y for p in pts]
            ax.plot(xs, ys, "k")

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)

    return StreamingResponse(buf, media_type="image/png")
