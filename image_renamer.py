import os
import re
import shutil
import json
from pathlib import Path

from PIL import Image
import torch
from transformers import AutoProcessor, AutoModelForCausalLM
from pillow_heif import register_heif_opener
from tqdm import tqdm

register_heif_opener()

INPUT_FOLDER = "./input_images"
SB3D_FOLDER = "./SB3D_output"
CONFIG_FILE = "./config.json"

# Hard reject list for any leading junk words
BLOCKLIST = {
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
}

VALID_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".bmp"}

def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

def extract_date_suffix(filename: str) -> str:
    """Return dd-mm-yyyy if the original filename contains a date."""
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
    token = re.sub(r"[^a-z0-9]", "", token.lower())
    if not token:
        return ""
    if token in {"3d", "2d"}:
        return token.upper()
    return token

def title_token(token: str) -> str:
    token = normalize_token(token)
    if not token:
        return ""
    if token.upper() in {"3D", "2D"}:
        return token.upper()
    return token.capitalize()

def is_junk_prefix(word: str) -> bool:
    return word.lower() in BLOCKLIST

def sanitize_caption(caption: str, original_name: str = "", max_words: int = 8) -> str:
    raw_words = re.findall(r"[A-Za-z0-9]+", caption or "")
    tokens = []
    seen = set()

    for word in raw_words:
        token = normalize_token(word)
        if not token:
            continue
        if is_junk_prefix(token):
            continue
        if token in seen:
            continue
        seen.add(token)
        tokens.append(token)

    # If caption is too weak, use the original filename as fallback source
    if len(tokens) < 2:
        fallback_words = re.findall(r"[A-Za-z0-9]+", original_name.replace(".", " "))
        for word in fallback_words:
            token = normalize_token(word)
            if not token:
                continue
            if is_junk_prefix(token):
                continue
            if token in seen:
                continue
            seen.add(token)
            tokens.append(token)

    tokens = tokens[:max_words]
    if len(tokens) < 2:
        tokens = ["untitled"]

    cleaned = [title_token(t) for t in tokens if title_token(t)]
    base = "-".join(cleaned)

    # Force out any leading generic junk if it passed through
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
        base = f"{base}-{date_suffix}"

    return base

def safe_output_name(base_name: str, ext: str, output_dir: str) -> str:
    candidate = f"{base_name}{ext.lower()}"
    final = os.path.join(output_dir, candidate)
    counter = 1
    while os.path.exists(final):
        candidate = f"{base_name}_{counter}{ext.lower()}"
        final = os.path.join(output_dir, candidate)
        counter += 1
    return candidate

def process_images(input_dir: str, output_dir: str, config: dict):
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(input_dir, exist_ok=True)

    caption_rules = config.get("caption_cleaning_rules", {})
    model_config = config.get("model_config", {})
    model_name = model_config.get("model_name", "microsoft/Florence-2-large")
    max_new_tokens = int(model_config.get("max_new_tokens", 20))
    num_beams = int(model_config.get("num_beams", 3))
    max_words = int(caption_rules.get("max_words", 8))

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")

    print(f"Loading model: {model_name}...")
    processor = AutoProcessor.from_pretrained(model_name, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(model_name, trust_remote_code=True).to(device)
    print("Model loaded.")

    image_files = [
        f for f in sorted(os.listdir(input_dir))
        if f.lower().endswith(tuple(VALID_EXTS))
    ]

    if not image_files:
        print(f"No images found in {input_dir}. Please place your images there.")
        return

    for filename in tqdm(image_files, desc="Processing Images"):
        original_path = os.path.join(input_dir, filename)
        _, ext = os.path.splitext(filename)

        try:
            image = Image.open(original_path).convert("RGB")
            prompt = "An image of"
            inputs = processor(text=prompt, images=image, return_tensors="pt").to(device)

            generated_ids = model.generate(
                input_ids=inputs["input_ids"],
                pixel_values=inputs["pixel_values"],
                max_new_tokens=max_new_tokens,
                num_beams=num_beams,
                do_sample=False,
            )

            generated_text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
            caption = generated_text.replace(prompt, "").strip()

            if caption:
                generated_name = sanitize_caption(caption, original_name=filename, max_words=max_words)
            else:
                generated_name = sanitize_caption("", original_name=filename, max_words=max_words)

            final_name = safe_output_name(generated_name, ext, output_dir)
            destination = os.path.join(output_dir, final_name)

            shutil.move(original_path, destination)
            print(f"Renamed: {filename} -> {final_name}")

        except Exception as e:
            tqdm.write(f"Error processing {filename}: {e}")
            fallback_base = "Untitled"
            date_suffix = extract_date_suffix(filename)
            if date_suffix:
                fallback_base = f"{fallback_base}-{date_suffix}"
            final_name = safe_output_name(fallback_base, ext, output_dir)
            destination = os.path.join(output_dir, final_name)

            try:
                shutil.move(original_path, destination)
                tqdm.write(f"Fallback rename used: {final_name}")
            except Exception as move_err:
                tqdm.write(f"Move failed for {filename}: {move_err}")

    print("Image processing complete.")

if __name__ == "__main__":
    print("Starting image renaming tool...")
    try:
        config = load_config(CONFIG_FILE)
    except FileNotFoundError:
        print(f"Error: Configuration file '{CONFIG_FILE}' not found. Please ensure it exists.")
        raise SystemExit(1)
    except json.JSONDecodeError:
        print(f"Error: Could not parse '{CONFIG_FILE}'. Please check its format.")
        raise SystemExit(1)

    process_images(INPUT_FOLDER, SB3D_FOLDER, config)
    print("Tool finished.")