#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def build_caption(*, stem: str, trigger_token: str, style: str, product_type: str, extra: str) -> str:
    parts = [
        trigger_token,
        product_type,
        "deskterior product advertising photo",
        f"style {style}",
        "clean desk setup, commercial product composition, no brand logo",
    ]
    if extra:
        parts.append(extra)
    parts.append(stem.replace("_", " ").replace("-", " "))
    return ", ".join(part for part in parts if part)


def prepare_dataset(args: argparse.Namespace) -> None:
    source_dir = Path(args.images_dir)
    output_dir = Path(args.output_dir)
    image_out = output_dir / "images"
    image_out.mkdir(parents=True, exist_ok=True)

    image_paths = sorted(path for path in source_dir.iterdir() if path.suffix.lower() in IMAGE_EXTENSIONS)
    if not image_paths:
        raise SystemExit(f"No images found in {source_dir}")

    records = []
    license_records = []
    for index, source_path in enumerate(image_paths, start=1):
        target_name = f"desk_lora_{index:04d}{source_path.suffix.lower()}"
        target_path = image_out / target_name
        if args.symlink:
            if target_path.exists():
                target_path.unlink()
            target_path.symlink_to(source_path.resolve())
        else:
            shutil.copy2(source_path, target_path)

        caption = build_caption(
            stem=source_path.stem,
            trigger_token=args.trigger_token,
            style=args.style,
            product_type=args.product_type,
            extra=args.extra_caption,
        )
        records.append({"file_name": f"images/{target_name}", "text": caption})
        license_records.append(
            {
                "file_name": f"images/{target_name}",
                "original_path": str(source_path),
                "source": args.source,
                "license": args.license,
                "commercial_use_checked": args.commercial_use_checked,
            }
        )

    (output_dir / "metadata.jsonl").write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n",
        encoding="utf-8",
    )
    (output_dir / "license_manifest.json").write_text(
        json.dumps(license_records, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Prepared {len(records)} images in {output_dir}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare a DeskAd LoRA dataset with captions and license manifest.")
    parser.add_argument("--images-dir", required=True, help="Directory containing merchant-owned or commercial-safe images.")
    parser.add_argument("--output-dir", required=True, help="Output dataset directory.")
    parser.add_argument("--trigger-token", default="deskadkb", help="Unique token used in LoRA prompts.")
    parser.add_argument("--style", default="minimal deskterior", help="Visual style label for captions.")
    parser.add_argument("--product-type", default="custom keyboard and desk accessory", help="Product type caption phrase.")
    parser.add_argument("--extra-caption", default="", help="Extra caption phrase appended to all samples.")
    parser.add_argument("--source", default="merchant-owned", help="Dataset source label for the license manifest.")
    parser.add_argument("--license", default="merchant-owned-commercial", help="License label for the manifest.")
    parser.add_argument("--commercial-use-checked", action="store_true", help="Mark that commercial-use rights were checked.")
    parser.add_argument("--symlink", action="store_true", help="Symlink images instead of copying them.")
    return parser.parse_args()


if __name__ == "__main__":
    prepare_dataset(parse_args())
