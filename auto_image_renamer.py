import argparse
import logging
import os
import re
from PIL import Image
import torch
from tqdm import tqdm
from transformers import BlipForConditionalGeneration, BlipProcessor

# --- Configuration Defaults ---
INPUT_DIR = "./input_images"
ALLOWED_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
)
MIN_WORDS = 2
MAX_WORDS = 6

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def load_model():
  """Loads the BLIP captioning model and processor onto GPU if available."""
  device = "cuda" if torch.cuda.is_available() else "cpu"
  logging.info(f"Loading BLIP image captioning model on device: {device}...")

  processor = BlipProcessor.from_pretrained(
      "Salesforce/blip-image-captioning-base"
  )
  model = BlipForConditionalGeneration.from_pretrained(
      "Salesforce/blip-image-captioning-base"
  ).to(device)

  logging.info("Model loaded successfully.")
  return model, processor, device


def sanitize_and_format_caption(
    caption: str, min_words=MIN_WORDS, max_words=MAX_WORDS
) -> str:
  """Sanitizes raw caption text and converts it to a 2-6 word snake_case string."""
  # Remove punctuation and split into lowercase words
  words = re.findall(r"\b[a-zA-Z0-9]+\b", caption.lower())

  # Enforce length constraints
  words = words[:max_words]
  if len(words) < min_words:
    words.append("photo")

  return "_".join(words)


def generate_unique_filename(directory: str, base_name: str, ext: str) -> str:
  """Handles potential filename collisions by appending a numeric counter."""
  candidate_name = f"{base_name}{ext}"
  counter = 1
  while os.path.exists(os.path.join(directory, candidate_name)):
    candidate_name = f"{base_name}_{counter}{ext}"
    counter += 1
  return candidate_name


def process_images(input_dir: str):
  """Scans input_dir, generates captions, and renames images in snake_case format."""
  if not os.path.exists(input_dir):
    logging.error(f"Directory '{input_dir}' does not exist.")
    return

  image_files = [
      f
      for f in os.listdir(input_dir)
      if f.lower().endswith(ALLOWED_EXTENSIONS)
  ]

  if not image_files:
    logging.info(f"No valid images found in '{input_dir}'.")
    return

  model, processor, device = load_model()

  logging.info(f"Processing {len(image_files)} images...")

  for filename in tqdm(image_files, desc="Renaming Images"):
    file_path = os.path.join(input_dir, filename)
    ext = os.path.splitext(filename)[1].lower()

    try:
      # Load and preprocess image
      raw_image = Image.open(file_path).convert("RGB")
      inputs = processor(raw_image, return_tensors="pt").to(device)

      # Generate caption
      with torch.no_grad():
        output = model.generate(**inputs, max_new_tokens=20)
      raw_caption = processor.decode(output[0], skip_special_tokens=True)

      # Format caption into snake_case
      snake_name = sanitize_and_format_caption(raw_caption)

      # Handle collisions and perform rename
      new_filename = generate_unique_filename(input_dir, snake_name, ext)
      new_file_path = os.path.join(input_dir, new_filename)

      os.rename(file_path, new_file_path)
      logging.info(
          f"Renamed: '{filename}' -> '{new_filename}' (Caption: '{raw_caption}')"
      )

    except Exception as e:
      logging.error(f"Failed to process image '{filename}': {e}")


if __name__ == "__main__":
  parser = argparse.ArgumentParser(
      description="Auto-rename images based on content using BLIP."
  )
  parser.add_argument(
      "--input_dir",
      type=str,
      default=INPUT_DIR,
      help="Target directory containing images.",
  )
  args = parser.parse_args()

  process_images(args.input_dir)