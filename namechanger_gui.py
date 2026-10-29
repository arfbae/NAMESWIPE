import tkinter as tk
from tkinter import messagebox
import subprocess
import sys
from pathlib import Path

VERSION = "v1.0.0"
SCRIPT_PATH = Path("namechanger_engine.py")

class NameChangerApp:

    def __init__(self, root):
        self.root = root
        self.root.title(f"NameChanger {VERSION}")
        self.root.geometry("500x300")

        tk.Label(root, text=f"NameChanger {VERSION}", font=("Arial", 16, "bold")).pack(pady=10)
        tk.Label(root, text="Professional File Renaming & Sorting Tool").pack()

        tk.Button(root, text="Run Engine", command=self.run_engine).pack(pady=20)

    def run_engine(self):
        subprocess.Popen([sys.executable, str(SCRIPT_PATH)])
        messagebox.showinfo("NameChanger", "Engine launched.")

def show_splash():
    splash = tk.Tk()
    splash.overrideredirect(True)
    splash.geometry("400x200+500+300")
    splash.configure(bg="black")

    tk.Label(
        splash,
        text="NameChanger v1.0.0",
        fg="white",
        bg="black",
        font=("Arial", 18, "bold")
    ).pack(expand=True)

    tk.Label(
        splash,
        text="Initializing system...",
        fg="gray",
        bg="black"
    ).pack()

    splash.after(2000, splash.destroy)
    splash.mainloop()

if __name__ == "__main__":
    show_splash()
    root = tk.Tk()
    app = NameChangerApp(root)
    root.mainloop()
