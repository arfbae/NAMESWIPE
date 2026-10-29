## Cloud/GPU Workflow (Google Colab + Google Drive)

This project can also be run in Google Colab using GPU acceleration and Google Drive for file persistence.

This is the recommended cloud workflow when you want to:
- use GPU instead of local CPU
- avoid the desktop/Tkinter app
- process large batches of images
- keep your files in Google Drive
- download the renamed output as a ZIP file

### Why use Colab?
The original project was designed as a local Windows desktop utility. In Colab, you can run the same AI-driven renaming logic with a GPU-backed vision model, which is much faster and more scalable for image batches.

### Recommended setup
- Google Drive
- Google Colab
- GPU runtime enabled
- a folder like:
  - `MyDrive/NAMESWIPE/input_images`
  - `MyDrive/NAMESWIPE/SB3D_output`

### 1) Open Colab and mount Google Drive
Run this in a notebook cell:

```python
from google.colab import drive
drive.mount("/content/drive")
```

### 2) Create folders
```python
from pathlib import Path

INPUT_DIR = Path("/content/drive/MyDrive/NAMESWIPE/input_images")
OUTPUT_DIR = Path("/content/drive/MyDrive/NAMESWIPE/SB3D_output")
ZIP_PATH = Path("/content/drive/MyDrive/NAMESWIPE/output.zip")

INPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("Input:", INPUT_DIR)
print("Output:", OUTPUT_DIR)
print("ZIP:", ZIP_PATH)
```

### 3) Install dependencies
```python
!pip install -q transformers pillow torch tqdm
```

### 4) Upload images
```python
from google.colab import files

uploaded = files.upload()

for filename, content in uploaded.items():
    target = INPUT_DIR / filename
    with open(target, "wb") as f:
        f.write(content)
    print("Saved:", target)
```

### 5) Run the GPU renamer
This notebook uses the same renaming philosophy as the repo’s original desktop workflow:
- caption generation from the image
- filtering junk words and generic prefixes
- safe filename cleanup
- date suffix support
- duplicate-name protection

```python
import os
import re
import shutil
from pathlib import Path

import torch
from PIL import Image
from transformers import AutoProcessor, AutoModelForCausalLM

BLOCKLIST = {
    "a","an","and","artwork","computer","device","digital","for","gpu","graphic",
    "icon","image","in","logo","of","on","photo","picture","render","screenshot",
    "the","to","wallpaper","with"
}

VALID_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".bmp"}

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

    generic_prefixes = (
        "Gpu-","Computer-","Image-","Photo-","Picture-","Screenshot-","Artwork-","Graphic-"
    )
    if base.lower().startswith(generic_prefixes):
        base = base.split("-", 1)[1] if "-" in base else base

    if not base or base.lower() in {"untitled","photo","image","gpu"}:
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

def list_images(input_dir: Path):
    return sorted(
        [p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() in VALID_EXTS],
        key=lambda p: p.name
    )

model_name = "microsoft/Florence-2-base"
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using device: {device}")
print(f"Loading model: {model_name}")

processor = AutoProcessor.from_pretrained(model_name, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(model_name, trust_remote_code=True).to(device)
print("Model loaded.")

def generate_caption(image_path: str) -> str:
    try:
        image = Image.open(image_path).convert("RGB")
        prompt = "An image of"
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
    except Exception as e:
        print(f"Caption generation failed: {e}")
        return ""

image_files = list_images(INPUT_DIR)

print(f"Found {len(image_files)} images.")

for idx, image_path in enumerate(image_files, start=1):
    filename = image_path.name
    ext = image_path.suffix.lower()
    print(f"\n[{idx}/{len(image_files)}] Processing: {filename}")

    try:
        caption = generate_caption(str(image_path))
        if caption:
            generated_name = sanitize_caption(caption, original_name=filename, max_words=8)
        else:
            generated_name = sanitize_caption("", original_name=filename, max_words=8)

        final_name = safe_output_name(generated_name, ext, str(OUTPUT_DIR))
        destination = OUTPUT_DIR / final_name

        shutil.move(str(image_path), str(destination))
        print(f"Renamed: {filename} -> {final_name}")

    except Exception as e:
        print(f"Error processing {filename}: {e}")
        fallback_base = "Untitled"
        date_suffix = extract_date_suffix(filename)
        if date_suffix:
            fallback_base = f"{fallback_base}-{date_suffix}"
        final_name = safe_output_name(fallback_base, ext, str(OUTPUT_DIR))
        destination = OUTPUT_DIR / final_name
        try:
            shutil.move(str(image_path), str(destination))
            print(f"Fallback rename used: {final_name}")
        except Exception as move_err:
            print(f"Move failed for {filename}: {move_err}")
```

### 6) Zip and download results
```python
import zipfile
from google.colab import files

def zip_folder(folder_path: Path, zip_path: Path):
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file in sorted(folder_path.rglob("*")):
            if file.is_file():
                zf.write(file, file.relative_to(folder_path.parent))

zip_folder(OUTPUT_DIR, ZIP_PATH)
print(f"ZIP created: {ZIP_PATH}")

files.download(str(ZIP_PATH))
```

### Notes
- This workflow is meant for Google Colab or any GPU-enabled environment.
- The output is stored in `SB3D_output`.
- The ZIP file is ideal for downloading the final renamed batch.
- This version is intended to keep the original project behavior consistent while adding cloud/GPU support.

### Recommended model
```python
model_name = "microsoft/Florence-2-base"
```

This is a strong default for Colab because it is more suitable than a tiny CPU-only model while still being practical to run on a GPU-enabled runtime.

---

This is the cleanest GitHub-ready section for your repo. If you want, I can also turn this into a full README.md draft for the repo with:
- installation
- local Windows flow
- cloud/Colab flow
- troubleshooting
- usage examples
- model notes
- deployment notes.
