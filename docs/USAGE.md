# NameSwipe Usage Guide

## CLI usage

```bash
python image_renamer.py --config ./config.json --dry-run
python image_renamer.py --input-dir ./input_images --output-dir ./SB3D_output
```

## What the tool does

1. Finds image files in a source folder.
2. Uses a local Hugging Face vision-language model to generate a caption.
3. Filters junk words and generic prefixes.
4. Produces a clean filename such as `Dragon-House-02-05-2024.jpg`.
5. Moves the result into the output folder without overwriting existing files.

## Troubleshooting

- If the model download fails, verify your internet connection and that the model name is valid.
- If no images are found, ensure your source directory contains supported extensions.
- If the output folder is missing, the tool will create it automatically.
- If a rename fails, the tool falls back to a safe `Untitled` naming pattern.
