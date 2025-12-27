from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import ezdxf
import io
import math
import matplotlib.pyplot as plt

app = FastAPI()

# Salli Webnode / selain
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------
# APUTOIMINNOT
# --------------------------------------------------

def arc_length(radius, start_angle, end_angle):
    angle = abs(end_angle - start_angle)
    return math.radians(angle) * radius


def calculate_total_length(doc):
    msp = doc.modelspace()
    total_length = 0.0

    for e in msp:
        if e.dxftype() == "LINE":
            x1, y1 = e.dxf.start.x, e.dxf.start.y
            x2, y2 = e.dxf.end.x, e.dxf.end.y
            total_length += math.dist((x1, y1), (x2, y2))

        elif e.dxftype() == "CIRCLE":
            total_length += 2 * math.pi * e.dxf.radius

        elif e.dxftype() == "ARC":
            total_length += arc_length(
                e.dxf.radius,
                e.dxf.start_angle,
                e.dxf.end_angle
            )

    return total_length


# --------------------------------------------------
# DXF → LEIKKAUSPITUUS (LASKURIA VARTEN)
# --------------------------------------------------

@app.post("/parse-dxf")
async def parse_dxf(file: UploadFile = File(...)):
    try:
        content = await file.read()
        doc = ezdxf.read(io.BytesIO(content))
        total_length = calculate_total_length(doc)

        return {
            "total_length_mm": round(total_length, 2)
        }

    except Exception as e:
        return {
            "error": "DXF parsing failed",
            "details": str(e)
        }


# --------------------------------------------------
# DXF → PNG-ESIKATSELU
# --------------------------------------------------

@app.post("/preview-dxf")
async def preview_dxf(file: UploadFile = File(...)):
    content = await file.read()
    doc = ezdxf.read(io.BytesIO(content))
    msp = doc.modelspace()

    fig, ax = plt.subplots()
    ax.set_aspect("equal")
    ax.axis("off")

    for e in msp:
        if e.dxftype() == "LINE":
            ax.plot(
                [e.dxf.start.x, e.dxf.end.x],
                [e.dxf.start.y, e.dxf.end.y],
                "k"
            )

        elif e.dxftype() == "CIRCLE":
            circle = plt.Circle(
                (e.dxf.center.x, e.dxf.center.y),
                e.dxf.radius,
                fill=False
            )
            ax.add_patch(circle)

        elif e.dxftype() == "ARC":
            arc = plt.Arc(
                (e.dxf.center.x, e.dxf.center.y),
                2 * e.dxf.radius,
                2 * e.dxf.radius,
                angle=0,
                theta1=e.dxf.start_angle,
                theta2=e.dxf.end_angle
            )
            ax.add_patch(arc)

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)

    return StreamingResponse(buf, media_type="image/png")
