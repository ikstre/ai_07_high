
from __future__ import annotations

import hashlib
import json
import math
import shlex
import shutil
import struct
import subprocess
from pathlib import Path

from .config import get_settings
from .filenames import unique_timestamped_model_path
from .renderer import build_uploaded_step_proxy_glb


ALLOWED_MODEL_EXTENSIONS = {".step", ".stp", ".glb"}

# ── GLB unit sanity check ───────────────────────────────────────────────────
# Renderer convention: 1 GLB unit = 1 cm. Models authored/converted in mm or m
# come out 10x/100x off. We estimate the world-space bounding box from the glTF
# JSON (POSITION accessors are required to carry min/max) and flag a likely unit
# mismatch so the operator can rescale. Advisory only — never blocks an upload.
_GLB_JSON_CHUNK = 0x4E4F534A  # ascii "JSON"
GLB_MIN_PLAUSIBLE_CM = 1.0  # below this max-extent → likely authored in meters
GLB_MAX_PLAUSIBLE_CM = 250.0  # above this max-extent → likely authored in millimeters


def _read_glb_json(data: bytes) -> dict | None:
    if len(data) < 12 or data[:4] != b"glTF":
        return None
    total = struct.unpack_from("<I", data, 8)[0]
    offset, limit = 12, min(total, len(data))
    while offset + 8 <= limit:
        chunk_len, chunk_type = struct.unpack_from("<II", data, offset)
        offset += 8
        if offset + chunk_len > len(data):
            break
        if chunk_type == _GLB_JSON_CHUNK:
            return json.loads(data[offset:offset + chunk_len].decode("utf-8"))
        offset += chunk_len
    return None


def _mat_identity() -> list[float]:
    return [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0]


def _mat_mul(a: list[float], b: list[float]) -> list[float]:
    # column-major 4x4: out[c*4+r] = sum_k a[k*4+r] * b[c*4+k]
    out = [0.0] * 16
    for c in range(4):
        for r in range(4):
            out[c * 4 + r] = sum(a[k * 4 + r] * b[c * 4 + k] for k in range(4))
    return out


def _node_matrix(node: dict) -> list[float]:
    m = node.get("matrix")
    if isinstance(m, list) and len(m) == 16:
        return [float(x) for x in m]
    t = node.get("translation") or [0.0, 0.0, 0.0]
    q = node.get("rotation") or [0.0, 0.0, 0.0, 1.0]
    s = node.get("scale") or [1.0, 1.0, 1.0]
    x, y, z, w = (float(v) for v in q)
    norm = math.sqrt(x * x + y * y + z * z + w * w) or 1.0
    x, y, z, w = x / norm, y / norm, z / norm, w / norm
    sx, sy, sz = (float(v) for v in s)
    r00, r01, r02 = 1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)
    r10, r11, r12 = 2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)
    r20, r21, r22 = 2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)
    return [
        r00 * sx, r10 * sx, r20 * sx, 0.0,
        r01 * sy, r11 * sy, r21 * sy, 0.0,
        r02 * sz, r12 * sz, r22 * sz, 0.0,
        float(t[0]), float(t[1]), float(t[2]), 1.0,
    ]


def _xform_point(m: list[float], x: float, y: float, z: float) -> tuple[float, float, float]:
    return (
        m[0] * x + m[4] * y + m[8] * z + m[12],
        m[1] * x + m[5] * y + m[9] * z + m[13],
        m[2] * x + m[6] * y + m[10] * z + m[14],
    )


def estimate_glb_dimensions(data: bytes) -> dict | None:
    """World-space bounding box (GLB units) of a GLB, or None on any parse failure.

    Walks the default scene's node hierarchy and applies each node transform to
    the POSITION accessor min/max corners. Never raises.
    """
    try:
        gltf = _read_glb_json(data)
        if not isinstance(gltf, dict):
            return None
        nodes = gltf.get("nodes") or []
        meshes = gltf.get("meshes") or []
        accessors = gltf.get("accessors") or []
        if not nodes or not meshes or not accessors:
            return None
        scenes = gltf.get("scenes") or []
        scene_idx = gltf.get("scene", 0) or 0
        roots = scenes[scene_idx].get("nodes") or [] if 0 <= scene_idx < len(scenes) else list(range(len(nodes)))

        lo = [math.inf, math.inf, math.inf]
        hi = [-math.inf, -math.inf, -math.inf]

        def walk(idx: int, parent: list[float]) -> None:
            if not isinstance(idx, int) or idx < 0 or idx >= len(nodes):
                return
            node = nodes[idx]
            world = _mat_mul(parent, _node_matrix(node))
            mesh_idx = node.get("mesh")
            if isinstance(mesh_idx, int) and 0 <= mesh_idx < len(meshes):
                for prim in meshes[mesh_idx].get("primitives", []):
                    pos = (prim.get("attributes") or {}).get("POSITION")
                    if not isinstance(pos, int) or pos < 0 or pos >= len(accessors):
                        continue
                    acc = accessors[pos]
                    mn, mx = acc.get("min"), acc.get("max")
                    if not (isinstance(mn, list) and isinstance(mx, list) and len(mn) >= 3 and len(mx) >= 3):
                        continue
                    for cx in (mn[0], mx[0]):
                        for cy in (mn[1], mx[1]):
                            for cz in (mn[2], mx[2]):
                                wx, wy, wz = _xform_point(world, float(cx), float(cy), float(cz))
                                lo[0], lo[1], lo[2] = min(lo[0], wx), min(lo[1], wy), min(lo[2], wz)
                                hi[0], hi[1], hi[2] = max(hi[0], wx), max(hi[1], wy), max(hi[2], wz)
            for child in node.get("children") or []:
                walk(child, world)

        for root in roots:
            walk(root, _mat_identity())

        if lo[0] > hi[0]:
            return None
        width, height, depth = hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]
        return {
            "width": round(width, 2),
            "height": round(height, 2),
            "depth": round(depth, 2),
            "max_extent": round(max(width, height, depth), 2),
        }
    except Exception:
        return None


def glb_unit_check(data: bytes) -> dict | None:
    """Advisory 1cm-unit sanity check for an uploaded/converted GLB."""
    dims = estimate_glb_dimensions(data)
    if not dims or dims["max_extent"] <= 0:
        return None
    extent = dims["max_extent"]
    scale_ok = True
    suggested_scale: float | None = None
    if extent < GLB_MIN_PLAUSIBLE_CM:
        scale_ok, suggested_scale = False, 100.0
        note = f"바운딩 박스 최대 변 {extent} units — 매우 작음. m 단위로 보이며 ×100 보정 권장."
    elif extent > GLB_MAX_PLAUSIBLE_CM:
        scale_ok, suggested_scale = False, 0.1
        note = f"바운딩 박스 최대 변 {extent} units — 큼. mm 단위로 보이며 ×0.1 보정 권장."
    else:
        note = f"바운딩 박스 최대 변 {extent} units ≈ {extent}cm (1 unit=1cm) — 정상 범위."
    return {
        "dimensions_units": dims,
        "assumed_unit_cm": True,
        "scale_ok": scale_ok,
        "suggested_scale": suggested_scale,
        "note": note,
    }


def _safe_suffix(filename: str) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in ALLOWED_MODEL_EXTENSIONS:
        raise ValueError("Only STEP, STP, and GLB files are supported.")
    return suffix


def _assert_upload_size(data: bytes) -> None:
    settings = get_settings()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise ValueError(f"Uploaded file is too large. Limit: {settings.max_upload_mb}MB")


def _run_step_converter(input_path: Path, output_path: Path) -> tuple[bool, str]:
    settings = get_settings()
    if not settings.step_converter_cmd:
        return False, "STEP_CONVERTER_CMD is not configured."

    command = [part.format(input=str(input_path), output=str(output_path)) for part in shlex.split(settings.step_converter_cmd)]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=settings.step_converter_timeout_seconds,
            check=False,
        )
    except Exception as exc:
        return False, f"STEP converter failed to start: {exc}"

    # unique_timestamped_model_path가 경로를 원자적으로 선점하며 빈 파일을 만들어 두므로,
    # 존재 여부만으로는 변환 성공을 판정할 수 없다 → 내용이 실제로 쓰였는지(size>0)까지 본다.
    if result.returncode != 0 or not output_path.exists() or output_path.stat().st_size == 0:
        stderr = (result.stderr or result.stdout or "").strip()[-500:]
        return False, f"STEP converter returned {result.returncode}: {stderr}"
    return True, "STEP converted to GLB."


def handle_model_upload_bytes(
    *,
    filename: str,
    data: bytes,
    upload_dir: Path,
    model_dir: Path,
    public_base_url: str,
    product_name: str | None = None,
) -> dict:
    suffix = _safe_suffix(filename or "uploaded.step")
    _assert_upload_size(data)

    digest = hashlib.sha256(data).hexdigest()[:12]
    upload_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)
    name_source = product_name or Path(filename or "").stem or "uploaded_model"

    if suffix == ".glb":
        if not data.startswith(b"glTF"):
            raise ValueError("The uploaded GLB header is invalid.")
        output_path = unique_timestamped_model_path(model_dir, name_source, fallback="uploaded_model")
        model_name = output_path.name
        output_path.write_bytes(data)
        unit_check = glb_unit_check(data)
        message = "Uploaded GLB is ready for the 3D viewer."
        if unit_check and not unit_check["scale_ok"]:
            message += f" (스케일 주의: {unit_check['note']})"
        return {
            "model_url": f"{public_base_url}/static/models/{model_name}",
            "source_file": filename,
            "source_size": len(data),
            "sha256": digest,
            "conversion": "glb_passthrough",
            "message": message,
            "model_file": model_name,
            "unit_check": unit_check,
        }

    output_path = unique_timestamped_model_path(model_dir, name_source, fallback="uploaded_model")
    model_name = output_path.name
    source_name = f"{output_path.stem}{suffix}"
    source_path = upload_dir / source_name
    source_path.write_bytes(data)

    converted, message = _run_step_converter(source_path, output_path)
    if converted:
        unit_check = glb_unit_check(output_path.read_bytes())
        if unit_check and not unit_check["scale_ok"]:
            message += f" (스케일 주의: {unit_check['note']})"
        return {
            "model_url": f"{public_base_url}/static/models/{model_name}",
            "source_file": filename,
            "source_size": len(data),
            "sha256": digest,
            "conversion": "step_to_glb",
            "message": message,
            "model_file": model_name,
            "unit_check": unit_check,
        }

    proxy_meta = build_uploaded_step_proxy_glb(
        output_path=output_path,
        source_name=filename or source_name,
        source_size=len(data),
    )
    proxy_meta.update(
        {
            "model_url": f"{public_base_url}/static/models/{model_name}",
            "sha256": digest,
            "converter_note": message,
        }
    )
    return proxy_meta


def copy_existing_glb(
    *,
    source_path: Path,
    model_dir: Path,
    public_base_url: str,
    product_name: str | None = None,
) -> dict:
    output_path = unique_timestamped_model_path(
        model_dir,
        product_name or source_path.stem,
        fallback="library_model",
    )
    model_name = output_path.name
    shutil.copyfile(source_path, output_path)
    return {"model_url": f"{public_base_url}/static/models/{model_name}", "model_file": model_name}
