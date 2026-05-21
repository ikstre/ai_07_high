# DeskAd Keyboard Demo

Streamlit + FastAPI prototype for a step-by-step AI ad content workflow.

This demo focuses on the 3D preview line:

1. Streamlit collects keyboard and desk setup options.
2. Streamlit sends JSON to FastAPI.
3. FastAPI reads a keyboard layout JSON and exports a GLB model.
4. Streamlit displays the GLB through Google's `model-viewer` web component.

## Run

Open two terminals in this folder.

Backend:

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
python -m streamlit run streamlit_app.py --server.port 8501
```

Then open:

```text
http://localhost:8501
```

