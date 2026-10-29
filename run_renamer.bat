import argparse
import json
import logging
import os
import re
import shutil
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, List, Sequence

import torch
from PIL import Image
from pillow_heif import register_heif_opener
from tqdm import tqdm
from transformers import AutoModelForCausalLM, AutoProcessor

register_heif_opener()

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".bmp"}
DEFAULT_BLOCKLIST = [
    "a",
    "an",
    "and",
    "artwork",
    "computer",
    "device",
    "digital",
    "for",
    "gpu",
    "graphic",
    "icon",
    "image",
    "in",
    "logo",
    "of",
    "on",
    "photo",
    "picture",
    "render",
    "screenshot",
    "the",
    "to",
    "wallpaper",
    "with",
]

DEFAULT_CONFIG = {
    "input_dir": "./input_images",
    "output_dir": "./SB3D_output",
    "model_name": "microsoft/Florence-2-large",
    "max_words": 8,
    "min_words": 2,
    "max_new_tokens": 20,
    "num_beams": 3,
    "fallback_name": "Untitled",
    "blocklist": DEFAULT_BLOCKLIST,
}


@dataclass
class AppConfig:
    input_dir: str = "./input_images"
    output_dir: str = "./SB3D_output"
    model_name: str = "microsoft/Florence-2-large"
    max_words: int = 8
    min_words: int = 2
    max_new_tokens: int = 20
    num_beams: int = 3
    fallback_name: str = "Untitled"
    blocklist: List[str] = field(default_factory=lambda: list(DEFAULT_BLOCKLIST))

    def to_dict(self) -> dict:
        return asdict(self)


def configure_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def ensure_config(config_path: str | Path) -> Path:
    config_path = Path(config_path)
    if config_path.exists() and config_path.stat().st_size > 0:
        return config_path

    if config_path.exists() and config_path.stat().st_size == 0:
        logging.warning("Config file %s is empty; replacing it with a default config.", config_path)

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(DEFAULT_CONFIG, indent=2) + "\n", encoding="utf-8")
    logging.info("Created default config at %s", config_path)
    return config_path


def load_config(config_path: str | Path) -> AppConfig:
    path = ensure_config(config_path)
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw_text = f.read().strip()
        if not raw_text:
            raise ValueError("Config file is empty.")
        raw = json.loads(raw_text)
    except (json.JSONDecodeError, ValueError) as exc:
        logging.warning("Invalid config file at %s: %s. Replacing with defaults.", path, exc)
        path.write_text(json.dumps(DEFAULT_CONFIG, indent=2) + "\n", encoding="utf-8")
        raw = json.loads(path.read_text(encoding="utf-8"))

    config = AppConfig()
    for field_name, value in raw.items():
        if hasattr(config, field_name):
            setattr(config, field_name, value)

    config.blocklist = [str(item).lower() for item in config.blocklist]
    if config.max_words <= 0:
        raise ValueError("max_words must be greater than 0")
    if config.min_words <= 0:
        raise ValueError("min_words must be greater than 0")
    if config.max_new_tokens <= 0:
        raise ValueError("max_new_tokens must be greater than 0")
    if config.num_beams <= 0:
        raise ValueError("num_beams must be greater than 0")
    return config


def extract_date_suffix(filename: str) -> str:
    patterns = [
        r"(\d{4})[-_.](\d{1,2})[-_.](\d{1,2})",
        r"(\d{1,2})[-_.](\d{1,2})[-_.](\d{4})",
    ]
    for pattern in patterns:
        match = re.search(pattern, filename)
        if not match:
            continue
        if len(match.group(1)) == 4:
            year, month, day = match.group(1), match.group(2), match.group(3)
        else:
            day, month, year = match.group(1), match.group(2), match.group(3)
        return f"{int(day):02d}-{int(month):02d}-{int(year)}"
    return ""


def normalize_token(token: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]", "", token.lower())
    if not cleaned:
        return ""
    if cleaned in {"3d", "2d"}:
        return cleaned.upper()
    return cleaned


def title_token(token: str) -> str:
    cleaned = normalize_token(token)
    if not cleaned:
        return ""
    if cleaned.upper() in {"3D", "2D"}:
        return cleaned.upper()
    return cleaned.capitalize()


def sanitize_caption(
    caption: str,
    original_name: str = "",
    max_words: int = 8,
    min_words: int = 2,
    blocklist: Sequence[str] | None = None,
) -> str:
    if blocklist is None:
        blocklist = []
    blocklist_set = {normalize_token(word) for word in blocklist if normalize_token(word)}

    raw_words = re.findall(r"[A-Za-z0-9]+", caption or "")
    tokens: List[str] = []
    seen = set()

    for word in raw_words:
        token = normalize_token(word)
        if not token or token in blocklist_set:
            continue
        if token in seen:
            continue
        seen.add(token)
        tokens.append(token)

    if len(tokens) < min_words:
        fallback_words = re.findall(r"[A-Za-z0-9]+", (original_name or "").replace(".", " "))
        for word in fallback_words:
            token = normalize_token(word)
            if not token or token in blocklist_set:
                continue
            if token in seen:
                continue
            seen.add(token)
            tokens.append(token)

    tokens = tokens[:max_words]
    if len(tokens) < min_words:
        tokens = ["untitled"]

    cleaned = [title_token(token) for token in tokens if title_token(token)]
    base = "-".join(cleaned)

    generic_prefixes = (
        "Gpu-",
        "Computer-",
        "Image-",
        "Photo-",
        "Picture-",
        "Screenshot-",
        "Artwork-",
        "Graphic-",
    )
    if base.lower().startswith(generic_prefixes):
        base = base.split("-", 1)[1] if "-" in base else base

    if not base or base.lower() in {"untitled", "photo", "image", "gpu"}:
        base = "Untitled"

    date_suffix = extract_date_suffix(original_name)
    if date_suffix:
        base = f"{base}-{date_suffix}" if base != "Untitled" else f"Untitled-{date_suffix}"

    return base


def safe_output_name(base_name: str, ext: str, output_dir: str | Path) -> str:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    candidate = f"{base_name}{ext.lower()}"
    destination = output_dir / candidate
    counter = 1
    while destination.exists():
        candidate = f"{base_name}_{counter}{ext.lower()}"
        destination = output_dir / candidate
        counter += 1
    return candidate


def list_image_files(input_dir: str | Path) -> List[Path]:
    input_path = Path(input_dir)
    if not input_path.exists():
        logging.warning("Input directory does not exist yet: %s", input_path)
        input_path.mkdir(parents=True, exist_ok=True)
        return []

    files = [
        path
        for path in sorted(input_path.iterdir(), key=lambda p: p.name.lower())
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    return files


def load_model(model_name: str):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logging.info("Loading model '%s' on %s", model_name, device)
    processor = AutoProcessor.from_pretrained(model_name, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(model_name, trust_remote_code=True).to(device)
    logging.info("Model loaded successfully.")
    return model, processor, device


def generate_caption(model, processor, image: Image.Image, device: torch.device) -> str:
    prompt = "Describe the main object or scene in this image in a few concise words."
    inputs = processor(text=prompt, images=image, return_tensors="pt").to(device)
    generated_ids = model.generate(
        input_ids=inputs["input_ids"],
        pixel_values=inputs["pixel_values"],
        max_new_tokens=20,
        num_beams=3,
        do_sample=False,
    )
    generated_text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
    caption = generated_text.replace(prompt, "").strip()
    return caption


def process_images(config: AppConfig, dry_run: bool = False) -> int:
    input_dir = Path(config.input_dir)
    output_dir = Path(config.output_dir)
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    image_files = list_image_files(input_dir)
    if not image_files:
        logging.info("No supported image files were found in %s", input_dir)
        return 0

    model = None
    processor = None
    device = None

    processed = 0
    for image_path in tqdm(image_files, desc="Processing Images"):
        original_name = image_path.name
        ext = image_path.suffix.lower()
        logging.info("Processing %s", original_name)

        try:
            if model is None or processor is None or device is None:
                model, processor, device = load_model(config.model_name)

            with Image.open(image_path) as image:
                rgb = image.convert("RGB")
                caption = generate_caption(model, processor, rgb, device)

            generated_name = sanitize_caption(
                caption,
                original_name=original_name,
                max_words=config.max_words,
                min_words=config.min_words,
                blocklist=config.blocklist,
            )
            final_name = safe_output_name(generated_name, ext, output_dir)
            destination = output_dir / final_name

            if dry_run:
                logging.info("DRY RUN: %s -> %s", original_name, final_name)
                processed += 1
                continue

            if image_path.resolve() == destination.resolve():
                logging.info("%s already matches the output name; skipping move.", original_name)
                processed += 1
                continue

            shutil.move(str(image_path), str(destination))
            logging.info("Renamed %s -> %s", original_name, final_name)
            processed += 1

        except Exception as exc:
            fallback_base = config.fallback_name or "Untitled"
            date_suffix = extract_date_suffix(original_name)
            if date_suffix:
                fallback_base = f"{fallback_base}-{date_suffix}" if fallback_base != "Untitled" else f"Untitled-{date_suffix}"
            fallback_name = safe_output_name(fallback_base, ext, output_dir)
            destination = output_dir / fallback_name
            logging.warning("Falling back for %s: %s", original_name, exc)

            if dry_run:
                logging.info("DRY RUN: %s -> %s", original_name, fallback_name)
                processed += 1
                continue

            try:
                shutil.move(str(image_path), str(destination))
                logging.info("Fallback rename applied for %s: %s", original_name, fallback_name)
            except Exception as move_exc:
                logging.error("Could not move %s to %s: %s", image_path, destination, move_exc)
            processed += 1

    logging.info("Finished. Processed %s image(s).", processed)
    return processed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Offline AI image renamer for image libraries and SB3D pipelines.",
    )
    parser.add_argument("--config", default="./config.json", help="Path to JSON config file.")
    parser.add_argument("--input-dir", default=None, help="Directory containing source images.")
    parser.add_argument("--output-dir", default=None, help="Directory to move renamed images into.")
    parser.add_argument("--model-name", default=None, help="Hugging Face model name to use for captioning.")
    parser.add_argument("--max-words", type=int, default=None, help="Max words to keep in generated names.")
    parser.add_argument("--min-words", type=int, default=None, help="Minimum words before fallbacks kick in.")
    parser.add_argument("--dry-run", action="store_true", help="Preview rename targets without moving files.")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging.")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging(args.verbose)

    try:
        config = load_config(args.config)
    except ValueError as exc:
        logging.error(str(exc))
        return 2

    if args.input_dir:
        config.input_dir = args.input_dir
    if args.output_dir:
        config.output_dir = args.output_dir
    if args.model_name:
        config.model_name = args.model_name
    if args.max_words is not None:
        config.max_words = args.max_words
    if args.min_words is not None:
        config.min_words = args.min_words

    if config.max_words < config.min_words:
        logging.warning(
            "max_words (%s) is smaller than min_words (%s); adjusting max_words to min_words.",
            config.max_words,
            config.min_words,
        )
        config.max_words = config.min_words

    logging.info("Using input_dir=%s output_dir=%s model=%s", config.input_dir, config.output_dir, config.model_name)
    try:
        processed = process_images(config, dry_run=args.dry_run)
    except Exception as exc:
        logging.exception("Unexpected failure while processing images: %s", exc)
        return 1
    return 0 if processed >= 0 else 1


if __name__ == "__main__":
    sys.exit(main())
