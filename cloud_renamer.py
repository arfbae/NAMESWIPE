#!/usr/bin/env python3
"""Cloud GPU image renamer for Google Colab / remote GPU machines.

This script mimics the behavior of the current desktop renamer, but removes the
Tkinter + local Ollama dependence. It uses a Hugging Face vision model, runs on
GPU when available, and renames files in an `input_images` folder into an
`SB3D_output` folder.

Typical use in Colab:
    !pip install -q transformers pillow torch
    !python cloud_renamer.py --input /content/input_images --output /content/SB3D_output --model Salesforce/blip-image-captioning-base

If you want a notebook wrapper, you can paste the same logic into a Colab cell.
"""

import argparse
import os
import re
import sys
import time
from pathlib import Path

import torch
from PIL import Image
from transformers import pipeline

SUPPORTED_EXTS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
    ".heic",
    ".heif",
}


def clean_caption(text: str, max_chars: int = 50) -> str:
    """Convert a model caption into a safe filename fragment."""
    cleaned = text.lower()
    cleaned = cleaned.replace("-", "_")
    cleaned = re.sub(r"[^a-z0-9_]+", "_", cleaned)
    cleaned = cleaned.strip("_")
    if not cleaned:
        cleaned = "untitled"
    return cleaned[:max_chars]


def build_model(model_name: str):
    device = 0 if torch.cuda.is_available() else -1
    print(f"Loading model: {model_name}")
    print(f"Using device: {'CUDA' if device == 0 else 'CPU'}")
    return pipeline("image-to-text", model=model_name, device=device)


def generate_caption(captioner, image_path: str) -> str:
    try:
        with Image.open(image_path) as img:
            rgb = img.convert("RGB")
            result = captioner(rgb, max_new_tokens=40)
    except Exception as exc:
        print(f"  [ERROR] Could not process {image_path}: {exc}")
        return ""

    # Transformers image-to-text can return dicts or lists of dicts.
    if isinstance(result, list):
        text = result[0].get("generated_text", "") if result and isinstance(result[0], dict) else ""
    elif isinstance(result, dict):
        text = result.get("generated_text", "")
    else:
        text = str(result)

    return text.strip()


def make_unique_destination(folder: Path, base_name: str, ext: str) -> Path:
    destination = folder / f"{base_name}{ext}"
    index = 1
    while destination.exists():
        destination = folder / f"{base_name}_{index}{ext}"
        index += 1
    return destination


def list_images(folder: Path):
    files = []
    for item in sorted(folder.iterdir()):
        if item.is_file() and item.suffix.lower() in SUPPORTED_EXTS:
            files.append(item)
    return files


def main():
    parser = argparse.ArgumentParser(description="GPU image renamer for Colab / cloud environments")
    parser.add_argument("--input", default="input_images", help="Folder containing input images")
    parser.add_argument("--output", default="SB3D_output", help="Folder to move renamed images into")
    parser.add_argument(
        "--model",
        default=os.environ.get("RENAMER_MODEL", "Salesforce/blip-image-captioning-base"),
        help="HF vision model to use for captioning"
    )
    parser.add_argument("--dry-run", action="store_true", help="Only preview names without renaming")
    args = parser.parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output)

    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    images = list_images(input_dir)
    if not images:
        print(f"No supported image files found in: {input_dir}")
        return 0

    print(f"Found {len(images)} images in {input_dir}")
    title = f"Loading {args.model}"
    print("=" * len(title))
    print(title)
    print("=" * len(title))

    captioner = build_model(args.model)

    processed = 0
    for index, image_path in enumerate(images, start=1):
        print(f"\n[{index}/{len(images)}] Processing: {image_path.name}")

        caption = generate_caption(captioner, str(image_path))
        if not caption:
            print("  [WARNING] Model returned no caption. Using fallback name.")
            caption = "untitled"

        base_name = clean_caption(caption)
        ext = image_path.suffix.lower()
        destination = make_unique_destination(output_dir, base_name, ext)

        if args.dry_run:
            print(f"  Suggested rename: {destination.name}")
            processed += 1
            continue

        try:
            shutil_move = str(image_path).lower() != str(destination).lower()
            if shutil_move:
                import shutil
                shutil.move(str(image_path), str(destination))
                print(f"  [OK] Renamed -> {destination.name}")
            else:
                print(f"  [OK] Already in target name: {destination.name}")
            processed += 1
        except Exception as exc:
            print(f"  [ERROR] Failed to move image: {exc}")

    print(f"\nCompleted. Processed {processed} images.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
