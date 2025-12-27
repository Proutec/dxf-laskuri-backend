# --------------------------------------------------
# PAKOLLINEN RENDERIÄ VARTEN (matplotlib ilman GUI:ta)
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

# --------------------------------------------------
# FASTAPI-APP
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

def arc_length(radius, start_angle, end_angle):
    angle = abs(end_angle - start_angle)
    return math.radians(angle) * radius


def dist(p1, p2):
    return math.dist(p1, p2)

# --------------------------------------------------
# LEIKKUUPITUUDEN LASKENTA
# --------------------------------------------------

def calculate_total_length(doc):
    msp = doc.modelspace()
    total_length = 0.0

    def handle_entity(e):
        nonlocal total_length
        etype = e.dxftype()

        try:
            if etype == "LINE":
                total_length += dist(
                    (e.dxf.start.x, e.dxf.start.y),
                    (e.dxf.end.x, e.dxf.end.y)
                )

            elif etype == "CIRCLE":
                total_length += 2 * math.pi * e.dxf.radius

            elif etype == "ARC":
                total_length += arc_length(
                    e.dxf.radius,
                    e.dxf.start_angle,
                    e.dxf.end_angle
                )

            elif etype == "LWPOLYLINE":
                pts = list(e.get_points())
                for i in range(len(pts) - 1):
                    total_length += dist(
                        (pts[i][0], pts[i][1]),
                        (pts[i + 1][0], pts[i + 1][1])
                    )
                if e.closed and len(pts) > 2:
                    total_length += dist(
                        (pts[-1][0], pts[-1][1]),
                        (pts[0][0], pts[0][1])
                    )

            elif etype == "POLYLINE":
                pts = [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices]
                for i in range(len(pts) - 1):
                    total_length += dist(pts[i], pts[i + 1])
                if e.is_closed and len(pts) > 2:
                    total_length += dist(pts[-1], pts[0])

            else:
                # TEXT, HATCH, SPLINE, DIMENSION jne. ohitetaan turvallisesti
                pass

        except Exception:
            # Yksittäinen viallinen entity ei kaada koko laskentaa
            pass

    # --------------------------------------------------
    # MODELSPACE + BLOCKIT (INSERT)
    # --------------------------------------------------
    for ent in msp:
        if ent.dxftype() == "INSERT":
            try:
                block = doc.blocks.get(ent.dxf.name)
                for be in block:
                    handle_entity(be)
            except Exception:
                pass
        else:
            handle_entity(ent)

    return total_length

# --------------------------------------------------
# API: DXF → LEIKKUUPITUUS
# --------------------------------------------------

@app.post("/parse-dxf")
async def parse_dxf(file: UploadFile = File(...)):
    try:
        if not file.filename.lower().endswith(".dxf"):
            return JSONResponse(
                status_code=400,
                content={"error": "File is not a DXF"}
            )

        content = await file.read()
        stream = io.BytesIO(content)

        doc = ezdxf.read(stream)
        total_length = calculate_total_length(doc)

        return {
            "total_length_mm": round(total_length, 2)
        }

    except Exception as e:
        print("DXF PARSE ERROR:", e)
        return JSONResponse(
            status_code=500,
            content={
                "error": "DXF parsing failed",
                "details": str(e)
            }
        )

# --------------------------------------------------
# API: DXF → PNG-ESIKATSELU
# --------------------------------------------------

@app.post("/preview-dxf")
async def preview_dxf(file: UploadFile = File(...)):
    try:
        content = await file.read()
        stream = io.BytesIO(content)

        doc = ezdxf.read(stream)
        msp = doc.modelspace()

        fig, ax = plt.subplots()
        ax.set_aspect("equal")
        ax.axis("off")

        def draw_entity(e):
            etype = e.dxftype()

            try:
                if etype == "LINE":
                    ax.plot(
                        [e.dxf.start.x, e.dxf.end.x],
                        [e.dxf.start.y, e.dxf.end.y],
                        "k"
                    )

                elif etype == "CIRCLE":
                    ax.add_patch(
                        plt.Circle(
                            (e.dxf.center.x, e.dxf.center.y),
                            e.dxf.radius,
                            fill=False,
                            color="black"
                        )
                    )

                elif etype == "ARC":
                    ax.add_patch(
                        plt.Arc(
                            (e.dxf.center.x, e.dxf.center.y),
                            2 * e.dxf.radius,
                            2 * e.dxf.radius,
                            theta1=e.dxf.start_angle,
                            theta2=e.dxf.end_angle,
                            color="black"
                        )
                    )

                elif etype == "LWPOLYLINE":
                    pts = list(e.get_points())
                    xs = [p[0] for p in pts]
                    ys = [p[1] for p in pts]
                    if e.closed:
                        xs.append(xs[0])
                        ys.append(ys[0])
                    ax.plot(xs, ys, "k")

            except Exception:
                pass

        for ent in msp:
            if ent.dxftype() == "INSERT":
                try:
                    block = doc.blocks.get(ent.dxf.name)
                    for be in block:
                        draw_entity(be)
                except Exception:
                    pass
            else:
                draw_entity(ent)

        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=200, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)

        return StreamingResponse(buf, media_type="image/png")

    except Exception as e:
        print("DXF PREVIEW ERROR:", e)
        return JSONResponse(
            status_code=500,
            content={
                "error": "DXF preview failed",
                "details": str(e)
            }
        )
