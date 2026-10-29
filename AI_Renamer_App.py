import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import requests
import base64
import threading
import re
import ctypes
import time
from PIL import Image
import io

# --- CONFIGURATION ---
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_TAGS_URL = "http://localhost:11434/api/tags"

# REFINED PROMPT: Forcing the AI to be more descriptive and avoid gibberish
PROMPT = "Describe the object in this coloring book page. Use 3 simple words. Example: 'cute_baby_dragon' or 'running_tiger_outline'. Use only lowercase and underscores."

# Garbage words that moondream often spits out when confused
BANNED_WORDS = ['ers', 'ike', 'ursa', 'urn', 'ikey', 'ers_1', 'ers_2']

class RenamerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AI Visual Asset Renamer - SMART MODE")
        self.root.geometry("700x650")
        self.root.configure(bg="#f4f4f9")

        self.setup_ui()
        self.selected_folder = ""
        self.is_running = False
        self.active_model = "moondream"
        
        threading.Thread(target=self.check_ollama_status, daemon=True).start()

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="1. Select Image Folder", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        folder_frame = ttk.Frame(main_frame)
        folder_frame.pack(fill=tk.X, pady=(5, 15))
        
        self.path_entry = ttk.Entry(folder_frame)
        self.path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(folder_frame, text="Browse", command=self.browse_folder).pack(side=tk.RIGHT)

        self.ollama_status = ttk.Label(main_frame, text="Checking Ollama...", foreground="orange")
        self.ollama_status.pack(anchor="w")

        self.progress = ttk.Progressbar(main_frame, orient="horizontal", mode="determinate")
        self.progress.pack(fill=tk.X, pady=10)

        self.log = tk.Text(main_frame, height=18, state='disabled', font=("Consolas", 9), bg="white")
        self.log.pack(pady=5, fill=tk.BOTH, expand=True)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=10)
        self.start_btn = ttk.Button(btn_frame, text="START RENAMING", command=self.start_process)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        self.stop_btn = ttk.Button(btn_frame, text="STOP", command=self.stop_process, state='disabled')
        self.stop_btn.pack(side=tk.LEFT, padx=5)

    def check_ollama_status(self):
        try:
            res = requests.get(OLLAMA_TAGS_URL, timeout=5)
            if res.status_code == 200:
                models = [m['name'] for m in res.json().get('models', [])]
                found = next((m for m in models if "moondream" in m), None)
                if found:
                    self.active_model = found
                    self.ollama_status.config(text=f"● Connected: Using {self.active_model}", foreground="green")
        except:
            self.ollama_status.config(text="● Connection Failed", foreground="red")

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.selected_folder = os.path.normpath(folder)
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, self.selected_folder)

    def write_log(self, message):
        self.log.config(state='normal')
        self.log.insert(tk.END, message + "\n")
        self.log.see(tk.END)
        self.log.config(state='disabled')

    def get_ai_name(self, image_path, is_first=False):
        try:
            with Image.open(image_path) as img:
                img.thumbnail((512, 512))
                buffered = io.BytesIO()
                img.convert("RGB").save(buffered, format="JPEG", quality=85)
                b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        except: return None

        timeout = 120 if is_first else 40
        for attempt in range(3):
            try:
                # Ask for a description, but tell it specifically to avoid one-word garbage
                current_prompt = PROMPT if attempt == 0 else "What exactly is the animal or object in this drawing? Give me 3 words."
                
                payload = {"model": self.active_model, "prompt": current_prompt, "stream": False, "images": [b64]}
                res = requests.post(OLLAMA_URL, json=payload, timeout=timeout)
                if res.status_code == 200:
                    name = res.json().get("response", "").strip().lower()
                    clean = re.sub(r'[^a-z0-9_]', '', name.replace(" ", "_").replace("-", "_")).strip("_")
                    
                    # If it gives us a banned garbage word, try one more time
                    if clean in BANNED_WORDS or len(clean) < 3:
                        if attempt < 2: continue
                    
                    return clean[:50]
            except:
                time.sleep(2)
        return None

    def start_process(self):
        if not self.selected_folder: return
        self.is_running = True
        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        threading.Thread(target=self.process_loop, daemon=True).start()

    def stop_process(self):
        self.is_running = False

    def process_loop(self):
        files = [f for f in os.listdir(self.selected_folder) 
                 if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
        
        if not files:
            self.write_log("No images found.")
            self.reset_ui()
            return

        self.write_log(f"Processing {len(files)} files with Garbage-Filter enabled...")
        self.progress["maximum"] = len(files)
        success_count = 0

        for i, filename in enumerate(files):
            if not self.is_running: break
            
            old_path = os.path.join(self.selected_folder, filename)
            self.write_log(f"[{i+1}/{len(files)}] AI Analyzing: {filename}")
            
            ai_name = self.get_ai_name(old_path, is_first=(i==0))
            
            if ai_name:
                ext = os.path.splitext(filename)[1]
                new_filename = f"{ai_name}{ext}"
                new_path = os.path.join(self.selected_folder, new_filename)
                
                # Deduplicate
                idx = 1
                while os.path.exists(new_path) and old_path.lower() != new_path.lower():
                    new_path = os.path.join(self.selected_folder, f"{ai_name}_{idx}{ext}")
                    idx += 1
                
                try:
                    if old_path.lower() != new_path.lower():
                        os.rename(old_path, new_path)
                        success_count += 1
                        self.write_log(f"   ✔ Renamed to: {os.path.basename(new_path)}")
                    else:
                        self.write_log("   ℹ Name is already fine.")
                except Exception as e:
                    self.write_log(f"   ✖ Rename failed: {e}")
            else:
                self.write_log("   ✖ AI failed to respond. Taking 5s break...")
                time.sleep(5) 
            
            self.progress["value"] = i + 1
            ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)

        self.write_log(f"\n--- COMPLETED. {success_count} files fixed. ---")
        self.reset_ui()

    def reset_ui(self):
        self.is_running = False
        self.start_btn.config(state='normal')
        self.stop_btn.config(state='disabled')

if __name__ == "__main__":
    root = tk.Tk()
    app = RenamerApp(root)
    root.mainloop()