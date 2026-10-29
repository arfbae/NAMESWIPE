
import os
import re
import shutil
import json
from PIL import Image
import torch
from transformers import AutoProcessor, AutoModelForCausalLM
from pillow_heif import register_heif_opener
from tqdm import tqdm

# Register HEIF opener for Pillow
register_heif_opener()

# --- Configuration --- #
INPUT_FOLDER = "./input_images"
SB3D_FOLDER = "./SB3D_output"
CONFIG_FILE = "./config.json"

def load_config(config_path: str) -> dict:
    """Loads configuration from a JSON file."""
    with open(config_path, 'r') as f:
        return json.load(f)

def clean_caption_for_filename(caption: str, rules: dict) -> str:
    """Cleans a caption to be suitable for a filename based on rules."""
    if rules.get("to_lowercase", True):
        caption = caption.lower()
    
    if rules.get("remove_punctuation", True):
        caption = re.sub(r'[^a-z0-9\s]', '', caption)  # remove punctuation/emojis
    
    words = caption.split()
    max_words = rules.get("max_words", 8)
    caption = words[:max_words]

    replace_char = rules.get("replace_spaces_with", "_")
    caption = replace_char.join(caption)
    
    return caption

def process_images(input_dir: str, output_dir: str, config: dict):
    """Processes images in input_dir, renames them, and moves to output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(input_dir, exist_ok=True)

    caption_rules = config.get("caption_cleaning_rules", {})
    model_config = config.get("model_config", {})
    model_name = model_config.get("model_name", "microsoft/Florence-2-large")
    max_new_tokens = model_config.get("max_new_tokens", 20)
    num_beams = model_config.get("num_beams", 3)

    # Determine device (GPU if available, else CPU)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")

    print(f"Loading model: {model_name}...")
    processor = AutoProcessor.from_pretrained(model_name, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(model_name, trust_remote_code=True).to(device)
    print("Model loaded.")

    image_extensions = (".jpg", ".jpeg", ".png", ".heic")
    untitled_counter = 0

    image_files = [f for f in os.listdir(input_dir) if f.lower().endswith(image_extensions)]

    if not image_files:
        print(f"No images found in {input_dir}. Please place your images there.")
        return

    for filename in tqdm(image_files, desc="Processing Images"):
        original_filepath = os.path.join(input_dir, filename)
        name, ext = os.path.splitext(filename)

        try:
            image = Image.open(original_filepath).convert("RGB")

            # Generate caption
            prompt = "An image of"
            inputs = processor(text=prompt, images=image, return_tensors="pt").to(device)
            generated_ids = model.generate(
                input_ids=inputs["input_ids"],
                pixel_values=inputs["pixel_values"],
                max_new_tokens=max_new_tokens,
                num_beams=num_beams,
                do_sample=False
            )
            generated_text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
            caption = generated_text.replace(prompt, "").strip()

            if caption:
                new_filename_base = clean_caption_for_filename(caption, caption_rules)
            else:
                untitled_counter += 1
                new_filename_base = f"untitled_{untitled_counter}"
                tqdm.write(f"Could not generate caption for {filename}, using fallback: {new_filename_base}")

            new_filename = f"{new_filename_base}{ext.lower()}"
            destination_filepath = os.path.join(output_dir, new_filename)

            # Ensure unique filename if one already exists
            counter = 1
            while os.path.exists(destination_filepath):
                new_filename = f"{new_filename_base}_{counter}{ext.lower()}"
                destination_filepath = os.path.join(output_dir, new_filename)
                counter += 1

            shutil.move(original_filepath, destination_filepath)
            # tqdm.write(f"Renamed \'{filename}\' to \'{new_filename}\' and moved to \'{output_dir}\'")

        except Exception as e:
            tqdm.write(f"Error processing {filename}: {e}")
            # Fallback for errors during processing
            untitled_counter += 1
            new_filename_base = f"untitled_{untitled_counter}"
            new_filename = f"{new_filename_base}{ext.lower()}"
            destination_filepath = os.path.join(output_dir, new_filename)
            
            counter = 1
            while os.path.exists(destination_filepath):
                new_filename = f"{new_filename_base}_{counter}{ext.lower()}"
                destination_filepath = os.path.join(output_dir, new_filename)
                counter += 1

            shutil.move(original_filepath, destination_filepath)
            tqdm.write(f"Moved \'{filename}\' to \'{new_filename}\' in \'{output_dir}\' due to error.")

    print("Image processing complete.")

if __name__ == "__main__":
    print("Starting image renaming tool...")
    try:
        config = load_config(CONFIG_FILE)
    except FileNotFoundError:
        print(f"Error: Configuration file \'{CONFIG_FILE}\' not found. Please ensure it exists.")
        exit(1)
    except json.JSONDecodeError:
        print(f"Error: Could not parse \'{CONFIG_FILE}\'. Please check its format.")
        exit(1)

    process_images(INPUT_FOLDER, SB3D_FOLDER, config)
    print("Tool finished.")
