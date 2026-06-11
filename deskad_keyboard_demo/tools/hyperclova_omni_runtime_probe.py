#!/usr/bin/env python3
"""Inspect local readiness for a HyperCLOVA X SEED Omni runtime.

The probe is intentionally offline. It checks installed packages, CUDA/VRAM,
local Hugging Face cache entries, Ollama HyperCLOVA models, and the DeskAd
HyperCLOVA env split without downloading model files or printing secrets.
"""
from __future__ import annotations

import argparse
import importlib.metadata as metadata
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
FULL_OMNI_MODEL = "naver-hyperclovax/HyperCLOVAX-SEED-Omni-8B"
GGUF_OMNI_MODEL = "naver-ellm/HyperCLOVAX-SEED-Omni-8B-GGUF"
TEXT_MODELS = (
    "naver-hyperclovax/HyperCLOVAX-SEED-Text-Instruct-0.5B",
    "naver-hyperclovax/HyperCLOVAX-SEED-Text-Instruct-1.5B",
    "naver-hyperclovax/HyperCLOVAX-SEED-Think-14B",
)
PACKAGE_NAMES = (
    "torch",
    "transformers",
    "accelerate",
    "bitsandbytes",
    "vllm",
    "sglang",
    "xformers",
    "flash-attn",
    "huggingface-hub",
)
ENV_KEYS = (
    "HYPERCLOVA_BASE_URL",
    "HYPERCLOVA_MODEL",
    "HYPERCLOVA_VISION_BASE_URL",
    "HYPERCLOVA_VISION_MODEL",
    "HYPERCLOVA_IMAGE_BASE_URL",
    "HYPERCLOVA_IMAGE_MODEL",
    "HYPERCLOVA_IMAGE_MODE",
    "HYPERCLOVA_SUPPORTS_VISION",
    "GPU_WORKER_MODE",
)


def _load_dotenv() -> bool:
    env_path = PROJECT_DIR / ".env"
    if not env_path.exists():
        return False
    try:
        from dotenv import load_dotenv
    except Exception:
        return False
    load_dotenv(env_path, override=False)
    return True


def _package_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for package in PACKAGE_NAMES:
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            versions[package] = None
    return versions


def _torch_report() -> dict[str, Any]:
    report: dict[str, Any] = {
        "importable": False,
        "cuda_available": False,
        "device_count": 0,
        "devices": [],
    }
    try:
        import torch
    except Exception as exc:
        report["error"] = str(exc)
        return report

    report["importable"] = True
    report["version"] = getattr(torch, "__version__", "")
    report["cuda_runtime"] = getattr(getattr(torch, "version", object()), "cuda", None)
    report["cuda_available"] = bool(torch.cuda.is_available())
    if not report["cuda_available"]:
        return report

    report["device_count"] = int(torch.cuda.device_count())
    devices = []
    for index in range(report["device_count"]):
        props = torch.cuda.get_device_properties(index)
        devices.append(
            {
                "index": index,
                "name": props.name,
                "total_vram_gb": round(props.total_memory / (1024**3), 2),
                "capability": f"{props.major}.{props.minor}",
            }
        )
    report["devices"] = devices
    return report


def _run_command(args: list[str], timeout: int = 8) -> dict[str, Any]:
    if not shutil.which(args[0]):
        return {"available": False}
    try:
        result = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except Exception as exc:
        return {"available": True, "ok": False, "error": str(exc)}
    return {
        "available": True,
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def _nvidia_smi_report() -> dict[str, Any]:
    result = _run_command(
        [
            "nvidia-smi",
            "--query-gpu=index,name,memory.total,memory.used",
            "--format=csv,noheader,nounits",
        ]
    )
    if not result.get("available") or not result.get("ok"):
        return result
    gpus = []
    for line in str(result.get("stdout", "")).splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 4:
            continue
        gpus.append(
            {
                "index": parts[0],
                "name": parts[1],
                "memory_total_mb": parts[2],
                "memory_used_mb": parts[3],
            }
        )
    return {"available": True, "ok": True, "gpus": gpus}


def _repo_cache_dir(model_id: str, cache_root: Path) -> Path:
    return cache_root / ("models--" + model_id.replace("/", "--"))


def _hf_cache_roots() -> list[Path]:
    roots: list[Path] = []
    if os.getenv("HUGGINGFACE_HUB_CACHE"):
        roots.append(Path(os.environ["HUGGINGFACE_HUB_CACHE"]).expanduser())
    if os.getenv("TRANSFORMERS_CACHE"):
        roots.append(Path(os.environ["TRANSFORMERS_CACHE"]).expanduser())
    hf_home = Path(os.getenv("HF_HOME", "~/.cache/huggingface")).expanduser()
    roots.append(hf_home / "hub")

    unique: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        resolved = root.resolve() if root.exists() else root
        if resolved not in seen:
            unique.append(root)
            seen.add(resolved)
    return unique


def _snapshot_summary(repo_dir: Path) -> dict[str, Any]:
    snapshots_dir = repo_dir / "snapshots"
    snapshots = sorted(snapshots_dir.glob("*")) if snapshots_dir.exists() else []
    summary: dict[str, Any] = {
        "exists": repo_dir.exists(),
        "path": str(repo_dir),
        "snapshot_count": len(snapshots),
        "has_config": False,
        "has_safetensors": False,
        "has_gguf": False,
    }
    for snapshot in snapshots[:3]:
        if (snapshot / "config.json").exists():
            summary["has_config"] = True
        if any(snapshot.glob("*.safetensors")) or any(snapshot.glob("*.safetensors.index.json")):
            summary["has_safetensors"] = True
        if any(snapshot.glob("*.gguf")):
            summary["has_gguf"] = True
    return summary


def _hf_cache_report() -> dict[str, Any]:
    roots = _hf_cache_roots()
    model_ids = (FULL_OMNI_MODEL, GGUF_OMNI_MODEL, *TEXT_MODELS)
    models: dict[str, Any] = {}
    for model_id in model_ids:
        entries = []
        for root in roots:
            entries.append(_snapshot_summary(_repo_cache_dir(model_id, root)))
        models[model_id] = entries
    return {"roots": [str(root) for root in roots], "models": models}


def _ollama_report() -> dict[str, Any]:
    result = _run_command(["ollama", "list"])
    report: dict[str, Any] = {
        "available": result.get("available", False),
        "ok": result.get("ok", False),
        "hyperclova_models": [],
    }
    if not result.get("ok"):
        report["error"] = result.get("stderr") or result.get("error") or ""
        return report

    names = []
    for line in str(result.get("stdout", "")).splitlines()[1:]:
        name = line.split()[0] if line.split() else ""
        if "hyperclova" in name.lower():
            names.append(name)

    for name in names:
        show = _run_command(["ollama", "show", name], timeout=15)
        capabilities = []
        if show.get("ok"):
            in_capabilities = False
            for line in str(show.get("stdout", "")).splitlines():
                stripped = line.strip()
                if stripped == "Capabilities":
                    in_capabilities = True
                    continue
                if in_capabilities and not stripped:
                    break
                if in_capabilities:
                    capabilities.append(stripped)
        report["hyperclova_models"].append({"name": name, "capabilities": capabilities})
    return report


def _env_report() -> dict[str, Any]:
    report = {}
    for key in ENV_KEYS:
        value = os.getenv(key, "")
        if key.endswith("_BASE_URL") or key.endswith("_MODEL") or key in {"HYPERCLOVA_IMAGE_MODE", "GPU_WORKER_MODE"}:
            report[key] = value or "missing"
        else:
            report[key] = "set" if value else "missing"
    report["HYPERCLOVA_API_KEY"] = "set" if os.getenv("HYPERCLOVA_API_KEY") else "missing"
    report["HYPERCLOVA_VISION_API_KEY"] = "set" if os.getenv("HYPERCLOVA_VISION_API_KEY") else "missing"
    report["HYPERCLOVA_IMAGE_API_KEY"] = "set" if os.getenv("HYPERCLOVA_IMAGE_API_KEY") else "missing"
    return report


def _model_cached(cache: dict[str, Any], model_id: str) -> bool:
    entries = cache.get("models", {}).get(model_id, [])
    return any(entry.get("exists") and entry.get("snapshot_count", 0) > 0 for entry in entries)


def _recommendations(report: dict[str, Any]) -> list[str]:
    recs = []
    torch_report = report["torch"]
    packages = report["packages"]
    cache = report["hf_cache"]
    ollama_models = report["ollama"].get("hyperclova_models", [])
    devices = torch_report.get("devices", [])
    max_vram = max((device.get("total_vram_gb", 0) for device in devices), default=0)
    single_l4 = len(devices) == 1 and "L4" in str(devices[0].get("name", ""))

    if single_l4:
        recs.append(
            "Single NVIDIA L4 detected. Treat HyperCLOVA Omni workers as exclusive/sequential; do not run full OmniServe Track B compose alongside ComfyUI."
        )
    elif devices:
        recs.append(
            f"Detected {len(devices)} CUDA device(s), max VRAM {max_vram} GB. Confirm GPU layout before attempting full OmniServe."
        )
    else:
        recs.append("No CUDA GPU detected by torch. Local Omni inference is not ready.")

    for model in ollama_models:
        caps = set(model.get("capabilities", []))
        if model.get("name", "").startswith("hyperclova-omni-8b-text") and "vision" not in caps:
            recs.append("Ollama hyperclova-omni-8b-text is a valid text-only fallback, not a vision/image runtime.")
        if "vision" in caps:
            recs.append(
                f"Ollama model {model.get('name')} advertises vision, but keep it out of HYPERCLOVA_VISION_* unless an image chat call succeeds."
            )

    if not _model_cached(cache, FULL_OMNI_MODEL):
        recs.append(
            f"{FULL_OMNI_MODEL} is not present in the local HF cache. Download approval is required before vLLM/Transformers Omni trials."
        )
    else:
        recs.append(f"{FULL_OMNI_MODEL} is cached locally; vision runtime trials can run without a model download.")

    if packages.get("vllm"):
        recs.append(
            "vLLM is installed. First trial should be an OpenAI-compatible vision endpoint on a separate port, wired only to HYPERCLOVA_VISION_*."
        )
    elif packages.get("sglang"):
        recs.append(
            "SGLang is installed. Use it as the second OpenAI-compatible vision endpoint candidate if vLLM is unavailable or incompatible."
        )
    elif packages.get("transformers"):
        recs.append(
            "Transformers is installed. Use tools/hyperclova_omni_openai_vision_server.py as the single-process fallback for text+image -> text."
        )
    else:
        recs.append("No vLLM/SGLang/Transformers runtime found. Install one before attempting HyperCLOVA Omni.")

    env = report["env"]
    if env.get("HYPERCLOVA_VISION_BASE_URL") == "missing":
        recs.append("HYPERCLOVA_VISION_* is unset, so DeskAd correctly keeps HyperCLOVA image input disabled.")
    if env.get("HYPERCLOVA_IMAGE_BASE_URL") == "missing":
        recs.append(
            "HYPERCLOVA_IMAGE_* is unset. HyperCLOVA image output still needs OmniServe Track B decoder/S3 or an OpenAI Images-compatible wrapper."
        )
    return recs


def build_report() -> dict[str, Any]:
    return {
        "project_dir": str(PROJECT_DIR),
        "dotenv_loaded": _load_dotenv(),
        "env": _env_report(),
        "packages": _package_versions(),
        "torch": _torch_report(),
        "nvidia_smi": _nvidia_smi_report(),
        "hf_cache": _hf_cache_report(),
        "ollama": _ollama_report(),
    }


def _print_human(report: dict[str, Any]) -> None:
    print("# HyperCLOVA Omni runtime probe")
    print(f"- project_dir: {report['project_dir']}")
    print(f"- dotenv_loaded: {report['dotenv_loaded']}")

    print("\n## Environment")
    for key, value in report["env"].items():
        print(f"- {key}: {value}")

    print("\n## Packages")
    for key, value in report["packages"].items():
        print(f"- {key}: {value or 'missing'}")

    print("\n## CUDA")
    torch_report = report["torch"]
    print(f"- torch_importable: {torch_report.get('importable')}")
    print(f"- torch_cuda_available: {torch_report.get('cuda_available')}")
    print(f"- torch_cuda_runtime: {torch_report.get('cuda_runtime')}")
    for device in torch_report.get("devices", []):
        print(
            f"- gpu{device['index']}: {device['name']} / {device['total_vram_gb']} GB / cc {device['capability']}"
        )
    smi = report["nvidia_smi"]
    if smi.get("ok"):
        for gpu in smi.get("gpus", []):
            print(
                f"- nvidia-smi gpu{gpu['index']}: {gpu['name']} / used {gpu['memory_used_mb']} MiB of {gpu['memory_total_mb']} MiB"
            )

    print("\n## Hugging Face cache")
    print("- roots: " + ", ".join(report["hf_cache"].get("roots", [])))
    for model_id, entries in report["hf_cache"].get("models", {}).items():
        cached = any(entry.get("exists") and entry.get("snapshot_count", 0) > 0 for entry in entries)
        print(f"- {model_id}: {'cached' if cached else 'missing'}")

    print("\n## Ollama")
    ollama = report["ollama"]
    print(f"- available: {ollama.get('available')}")
    print(f"- ok: {ollama.get('ok')}")
    for model in ollama.get("hyperclova_models", []):
        caps = ", ".join(model.get("capabilities", [])) or "unknown"
        print(f"- {model.get('name')}: {caps}")

    print("\n## Recommendations")
    for recommendation in _recommendations(report):
        print(f"- {recommendation}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    report = build_report()
    report["recommendations"] = _recommendations(report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_human(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
