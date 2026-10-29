# Offline Image Auto-Renamer for SB3D Pipeline (v2.0)

This upgraded tool provides a fully offline, Windows-based solution to automatically rename images based on their visual content, integrating seamlessly with your SB3D pipeline. It leverages advanced open-source vision-language models to generate highly descriptive filenames, eliminating the need for manual renaming or cloud services.

## Features

*   **Enhanced Content-Based Renaming:** Utilizes the powerful Florence-2-large model for more accurate and descriptive image captions.
*   **100% Offline Operation:** All processing, including model inference, occurs locally on your Windows machine without requiring an internet connection after initial setup.
*   **GPU Acceleration:** Automatically detects and utilizes NVIDIA GPUs (if available) for significantly faster processing.
*   **HEIC Support:** Seamlessly processes HEIC image files thanks to `pillow-heif` integration.
*   **Configurable Naming Rules:** Customize caption cleaning rules (lowercase, space replacement, punctuation removal, max words) via a `config.json` file.
*   **Batch Processing with Progress Bar:** Efficiently handles hundreds of images with a visual progress indicator.
*   **SB3D Integration:** Renamed images are automatically moved to a designated SB3D output folder.
*   **Robust Fallback:** If content description fails, a sequential `untitled_` naming convention is used.

## Requirements

*   **Operating System:** Windows 10 or later.
*   **Python:** Version 3.8 or higher.
*   **Internet Connection (for initial setup only):** Required to download Python, pip packages, and the Florence-2-large model.
*   **Disk Space:** Sufficient space to download the model (several GBs) and store your images.
*   **NVIDIA GPU (Optional, for acceleration):** If you have an NVIDIA GPU, PyTorch will automatically use it. Ensure you have up-to-date NVIDIA drivers.

## Installation and Setup

Follow these steps to get the Image Auto-Renamer up and running on your Windows machine:

1.  **Install Python (if not already installed):**
    *   Download the latest Python 3.8+ installer from the official website: [python.org](https://www.python.org/downloads/windows/)
    *   During installation, **crucially check the box that says "Add Python to PATH"** before proceeding with the installation.
    *   Open Command Prompt and type `python --version` to verify the installation. You should see the Python version number.

2.  **Download the Tool:**
    *   Download the `image_renamer.py`, `setup.bat`, `run_renamer.bat`, and `config.json` files into a new, empty folder on your computer (e.g., `C:\ImageRenamer`).

3.  **Run the Setup Script:**
    *   Navigate to the folder where you saved the files (e.g., `C:\ImageRenamer`) using File Explorer.
    *   Double-click `setup.bat`.
    *   This script will install all necessary Python libraries (PyTorch, HuggingFace Transformers, Pillow, pillow-heif, tqdm). This step requires an internet connection and may take some time as it downloads the model and dependencies.
    *   Once completed, press any key to close the window.

## Usage

1.  **Prepare Your Images:**
    *   Inside the tool's folder (e.g., `C:\ImageRenamer`), you will find a newly created folder named `input_images`.
    *   Copy all the images you want to rename (JPG, PNG, HEIC formats are supported) into this `input_images` folder.

2.  **Configure Naming Rules (Optional):**
    *   Open `config.json` in a text editor.
    *   You can modify the `caption_cleaning_rules` to adjust how filenames are generated. For example:
        *   `"to_lowercase": true` (default) / `false`
        *   `"replace_spaces_with": "_"` (default) / `"-"` / `" "`
        *   `"remove_punctuation": true` (default) / `false`
        *   `"max_words": 8` (default) / any integer
    *   You can also change the `model_name` to `"microsoft/Florence-2-base"` if `Florence-2-large` is too slow for your hardware, or experiment with other compatible models.

3.  **Run the Renamer:**
    *   Double-click `run_renamer.bat`.
    *   A command prompt window will open, indicating that the tool is starting.
    *   Press any key to begin the renaming process.
    *   A progress bar will show the status of image processing.
    *   The tool will process each image, generate a content-based caption, clean it into a filename, and then rename and move the image.

4.  **Access Renamed Images:**
    *   Once the process is complete, all renamed images will be moved to the `SB3D_output` folder, located in the same directory as the tool.

## Technical Details

*   **Model Used:** Florence-2-large ([microsoft/Florence-2-large](https://huggingface.co/microsoft/Florence-2-large))
*   **Caption Cleaning:** Configurable via `config.json`.
*   **Fallback Logic:** If the model fails to generate a caption or an error occurs during processing, the image will be renamed `untitled_X.ext` (where X is an incrementing number) and moved to the `SB3D_output` folder.
*   **GPU Usage:** The script automatically checks for and uses an available NVIDIA GPU. If no GPU is found, it defaults to CPU.

## Creating a Standalone Executable (.exe)

To run the tool without a Python installation, you can package it into a standalone `.exe` file using PyInstaller. This process also requires an internet connection for PyInstaller to download necessary components.

1.  **Install PyInstaller:**
    *   Open Command Prompt and run: `pip install pyinstaller`

2.  **Generate the Executable:**
    *   Navigate to your tool's folder (e.g., `C:\ImageRenamer`) in Command Prompt.
    *   Run the following command:
        ```bash
        pyinstaller --onefile --add-data "config.json;." image_renamer.py
        ```
    *   This command will create a `dist` folder containing `image_renamer.exe`.

3.  **Run the EXE:**
    *   Copy the `image_renamer.exe` from the `dist` folder to your tool's main directory (e.g., `C:\ImageRenamer`).
    *   You can then run the `image_renamer.exe` directly, or modify `run_renamer.bat` to call `image_renamer.exe` instead of `python image_renamer.py`.
    *   **Note:** The first run of the EXE might be slow as it extracts its contents. Subsequent runs will be faster.

## Troubleshooting

*   **Python not found:** Ensure Python is installed and "Add Python to PATH" was selected during installation. If not, reinstall Python.
*   **Installation errors:** Check your internet connection. Some packages (especially PyTorch and the model) are large and require a stable connection.
*   **Model download issues:** The Florence-2-large model is downloaded automatically by the `transformers` library. If there are issues, ensure you have enough disk space and a stable internet connection during `setup.bat` execution.
*   **Images not processed:** Verify that your images are in the `input_images` folder and are in a supported format (JPG, PNG, HEIC).
*   **Slow performance:** Image captioning is a computationally intensive task. For faster inference, a dedicated NVIDIA GPU is highly recommended. If you have a GPU but it's not being used, ensure your NVIDIA drivers are up to date and PyTorch is installed with CUDA support (this is handled by `setup.bat`).
*   **`config.json` not found:** Ensure `config.json` is in the same directory as `image_renamer.py` (or `image_renamer.exe`).

## Contributing

This project is open-source. Feel free to fork the repository, submit issues, or propose enhancements.

---

**Manus AI**
April 3, 2026
