from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .renderer import build_keyboard_scene_glb


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
MODEL_DIR = STATIC_DIR / "models"
DATA_DIR = BASE_DIR / "data"

MODEL_DIR.mkdir(parents=True, exist_ok=True)


app = FastAPI(title="DeskAd Keyboard Preview API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class KeyboardRenderRequest(BaseModel):
    layout: str = Field(default="65")
    case_color: str = Field(default="#c8c1b2")
    keycap_color: str = Field(default="#f4ead7")
    accent_keycap_color: str = Field(default="#6f8faf")
    deskmat_color: str = Field(default="#1f2937")
    desk_color: str = Field(default="#d8b892")
    mouse_color: str = Field(default="#f7f7f2")
    theme: str = Field(default="minimal")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/layouts")
def list_layouts():
    layouts = []
    for path in sorted((DATA_DIR / "layouts").glob("layout_*.json")):
        layout_id = path.stem.replace("layout_", "")
        layouts.append({"id": layout_id, "name": f"{layout_id.upper()} Layout"})
    return {"layouts": layouts}


@app.get("/viewer", response_class=HTMLResponse)
def model_viewer(model_url: str):
    return f"""
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8" />
        <script type="module" src="https://unpkg.com/@google/model-viewer/dist/model-viewer.min.js"></script>
        <style>
          html, body {{
            margin: 0;
            width: 100%;
            height: 100%;
            background: #f4f1eb;
          }}
          model-viewer {{
            width: 100%;
            height: 100vh;
            background: linear-gradient(180deg, #f7f4ee 0%, #e9edf0 100%);
          }}
        </style>
      </head>
      <body>
        <model-viewer
          src="{model_url}"
          camera-controls
          auto-rotate
          shadow-intensity="0.8"
          exposure="0.72"
          camera-orbit="32deg 58deg 20m"
          min-camera-orbit="auto auto 12m"
          max-camera-orbit="auto auto 36m">
        </model-viewer>
      </body>
    </html>
    """


@app.post("/render/keyboard-preview")
def render_keyboard_preview(request: KeyboardRenderRequest):
    layout_path = DATA_DIR / "layouts" / f"layout_{request.layout}.json"
    if not layout_path.exists():
        layout_path = DATA_DIR / "layouts" / "layout_65.json"

    model_name = f"keyboard_{request.layout}_{uuid4().hex[:8]}.glb"
    output_path = MODEL_DIR / model_name

    metadata = build_keyboard_scene_glb(
        layout_path=layout_path,
        output_path=output_path,
        case_color=request.case_color,
        keycap_color=request.keycap_color,
        accent_keycap_color=request.accent_keycap_color,
        deskmat_color=request.deskmat_color,
        desk_color=request.desk_color,
        mouse_color=request.mouse_color,
    )

    return {
        "model_url": f"http://127.0.0.1:8000/static/models/{model_name}",
        "layout": request.layout,
        "theme": request.theme,
        **metadata,
    }


@app.post("/ai/copy")
def generate_copy(request: KeyboardRenderRequest):
    # Placeholder for later OpenAI/local LLM integration.
    mood = {
        "minimal": "깔끔한 데스크 셋업에 어울리는",
        "gaming": "RGB 감성과 몰입감을 살린",
        "premium": "고급스러운 작업 공간을 완성하는",
        "pastel": "부드러운 컬러감이 돋보이는",
    }.get(request.theme, "개성 있는")

    return {
        "copies": [
            f"{mood} 커스텀 키보드 셋업을 지금 만나보세요.",
            "나만의 책상 분위기를 완성하는 키보드와 데스크테리어 조합.",
            "작은 공방의 감성을 담은 맞춤형 데스크 아이템을 소개합니다.",
        ],
        "hashtags": ["#커스텀키보드", "#데스크테리어", "#키캡", "#데스크셋업"],
    }
