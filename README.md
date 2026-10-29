# Offline Image Auto-Renamer for SB3D Pipeline

This project renames image files using an AI captioning model, cleans the caption into a safe filename, and moves the renamed files into an output folder. It is designed for Windows-first local use, but the core logic also works in a headless environment.

## Quick start

1. Install Python 3.8+ and ensure it is on PATH.
2. Install dependencies:
   ```bash
   python -m pip install -r requirements.txt
   ```
3. Add images to `./input_images`.
4. Run the tool:
   ```bash
   python image_renamer.py
   ```

## Helpful commands

```bash
python image_renamer.py --dry-run
python image_renamer.py --input-dir ./my-images --output-dir ./renamed
python image_renamer.py --model-name microsoft/Florence-2-base
```

## Config

The repo uses a single JSON config at `config.json`:

```json
{
  "input_dir": "./input_images",
  "output_dir": "./SB3D_output",
  "model_name": "microsoft/Florence-2-large",
  "max_words": 8,
  "min_words": 2,
  "max_new_tokens": 20,
  "num_beams": 3,
  "fallback_name": "Untitled",
  "blocklist": ["a", "photo", "image", "the"]
}
```

## Behavior

- scans a source folder for supported image types (`.jpg`, `.jpeg`, `.png`, `.heic`, `.heif`, `.webp`, `.bmp`)
- captions each image using a Hugging Face vision-language model
- strips junk words and generic prefixes from the generated caption
- preserves date-like suffixes when present in the original filename
- creates unique output names to prevent overwrites
- falls back to `Untitled`-style naming if the model output is unusable

## Windows helpers

- `setup.bat` installs the required Python packages
- `run_renamer.bat` creates `input_images` and `SB3D_output`, then launches the renamer

## Notes

- The project depends on `torch`, `transformers`, `Pillow`, `pillow-heif`, and `tqdm`.
- The primary implementation is `image_renamer.py`; the other scripts are legacy experiments and should be treated as references rather than the source of truth.
