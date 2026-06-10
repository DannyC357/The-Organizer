import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import threading
from typing import Dict, List, Optional

from organizer_engine import AudioClassifier, OrganizerEngine, CATEGORY_PRIORITY, DEFAULT_RULES, calculate_folder_stats, export_folder

# Dark Theme Color Palette (Doppelganger Orange Accent Theme)
BG_DARK = "#0f0f11"       # Very dark charcoal / near-black main window
BG_PANEL = "#16161a"      # Slightly lighter dark gray panels
BG_SURFACE = "#222226"    # Inner cards / inputs / button normal state
FG_LIGHT = "#ffffff"      # Clean white text
FG_MUTED = "#9e9e9e"      # Soft gray subtext
ACCENT_ORANGE = "#ff6b00" # Primary Doppelganger orange accent
ACCENT_DIM_ORANGE = "#9e4300" # Dimmed orange for selections/active scrollbars
ACCENT_GREEN = "#00e676"  # Success status
ACCENT_RED = "#ff1744"    # Error/warning status
ACCENT_PEACH = "#ff9100"  # Warning highlights

# Code Compatibility Mappings (maps legacy blue/purple variables to orange/gray)
ACCENT_BLUE = ACCENT_ORANGE
ACCENT_MAUVE = ACCENT_ORANGE

# Category Colors for Visual Badges in List (All unified to clean Percussion blue-gray)
CATEGORY_COLORS = {
    "Kicks": "#b0bec5",       # Unified soft blue-gray
    "Snares": "#b0bec5",
    "Claps": "#b0bec5",
    "Hi-Hats": "#b0bec5",
    "Toms": "#b0bec5",
    "Cymbals": "#b0bec5",
    "Bass & 808s": "#b0bec5",
    "Vocals & Vox": "#b0bec5",
    "FX & Textures": "#b0bec5",
    "Melodic & Stabs": "#b0bec5",
    "Percussion": "#b0bec5",
    "Uncategorized": "#b0bec5"
}


class ModernButton(tk.Button):
    """Custom Tkinter button with text-only styling and hover effects (no box)."""
    def __init__(self, parent, text, command, bg_color=None, fg_color=FG_LIGHT, active_bg=None, active_fg=FG_LIGHT, font=("Segoe UI", 10, "bold"), **kwargs):
        # Determine background color to match parent frame seamlessly
        try:
            parent_bg = parent.cget("bg")
        except Exception:
            parent_bg = BG_PANEL
            
        button_bg = bg_color if bg_color is not None else parent_bg
        
        super().__init__(
            parent,
            text=text,
            command=command,
            bg=button_bg,
            fg=fg_color,
            activebackground=button_bg,
            activeforeground=active_fg,
            disabledforeground="#404044",
            font=font,
            bd=0,
            relief="flat",
            highlightthickness=0,
            padx=10,
            pady=4,
            cursor="hand2",
            **kwargs
        )
        self.bg_color = button_bg
        self.fg_color = fg_color
        self.hover_fg = active_fg
        
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _on_enter(self, e):
        if self.cget("state") == "normal":
            self.config(fg=self.hover_fg)

    def _on_leave(self, e):
        if self.cget("state") == "normal":
            self.config(fg=self.fg_color)


class CollapsiblePane(tk.Frame):
    """A collapsible frame container for rules editor."""
    def __init__(self, parent, title="", expanded=False, fg_color=FG_LIGHT):
        super().__init__(parent, bg=BG_DARK)
        self.expanded = expanded
        
        self.toggle_btn = ModernButton(
            self,
            text=f"▼ {title}" if expanded else f"▶ {title}",
            command=self.toggle,
            bg_color=BG_PANEL,
            fg_color=fg_color,
            active_fg=FG_LIGHT,
            font=("Segoe UI", 10, "bold"),
            anchor="w"
        )
        self.toggle_btn.pack(fill="x", expand=True)
        
        self.content_frame = tk.Frame(self, bg=BG_PANEL, bd=1, relief="flat")
        if self.expanded:
            self.content_frame.pack(fill="both", expand=True, padx=5, pady=2)

    def toggle(self):
        if self.expanded:
            self.content_frame.pack_forget()
            self.toggle_btn.config(text=self.toggle_btn.cget("text").replace("▼", "▶"))
            self.expanded = False
        else:
            self.content_frame.pack(fill="both", expand=True, padx=5, pady=2)
            self.toggle_btn.config(text=self.toggle_btn.cget("text").replace("▶", "▼"))
            self.expanded = True


class DrumOrganizerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("")
        self.root.geometry("1100x750" if sys.platform == "darwin" else "1150x780")
        self.root.configure(bg=BG_DARK)

        # Set custom window icon to get rid of default Tkinter feather icon
        icon_path = Path("app_icon.ico")
        if not icon_path.exists() and hasattr(sys, '_MEIPASS'):
            icon_path = Path(sys._MEIPASS) / "app_icon.ico"
        if icon_path.exists():
            try:
                self.root.iconbitmap(str(icon_path))
            except Exception:
                pass
                
        # Make the title bar black on Windows using DWM API
        if sys.platform == "win32":
            try:
                import ctypes
                hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
                if hwnd == 0:
                    hwnd = self.root.winfo_id()
                
                # Immersive dark mode (attribute 20)
                dark_mode = ctypes.c_int(1)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, 
                    20, 
                    ctypes.byref(dark_mode), 
                    ctypes.sizeof(dark_mode)
                )
                
                # Set caption color to pure black (attribute 35)
                black_color = ctypes.c_int(0x000000)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    35,
                    ctypes.byref(black_color),
                    ctypes.sizeof(black_color)
                )
            except Exception:
                pass

        # Load rules & engine (saved in ~/.drum_organizer/ to allow running from anywhere)
        self.config_dir = Path.home() / ".drum_organizer"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.rules_path = self.config_dir / "rules.json"
        self.history_path = self.config_dir / "history.json"
        self.classifier = AudioClassifier(self.rules_path)
        self.engine = OrganizerEngine(self.classifier)
        
        self.scan_results = {}
        self.selected_group = None
        self.currently_playing = None
        
        self.setup_styles()
        self.build_ui()
        
        # Set default directory to E:\Kits & Loops\Steve Lawrence
        # If it doesn't exist, check standard directories or fallback to blank
        default_dir = Path("E:/Kits & Loops/Steve Lawrence")
        if default_dir.exists():
            self.dir_entry.insert(0, str(default_dir))
        else:
            self.dir_entry.insert(0, str(Path.home() / "Desktop"))

    def setup_styles(self):
        """Configure styles for ttk widgets to match dark theme."""
        style = ttk.Style()
        style.theme_use("clam")
        
        # Configure frames and labels
        style.configure("TFrame", background=BG_DARK)
        style.configure("Panel.TFrame", background=BG_PANEL)
        style.configure("TLabel", background=BG_DARK, foreground=FG_LIGHT, font=("Segoe UI", 10))
        style.configure("Panel.TLabel", background=BG_PANEL, foreground=FG_LIGHT, font=("Segoe UI", 10))
        
        # Configure Entry
        style.configure("TEntry", fieldbackground=BG_SURFACE, foreground=FG_LIGHT, bordercolor=BG_PANEL, lightcolor=BG_PANEL, darkcolor=BG_PANEL)
        
        # Configure Treeview (Files List)
        style.configure("Treeview",
            background=BG_PANEL,
            foreground=FG_LIGHT,
            fieldbackground=BG_PANEL,
            rowheight=25,
            font=("Segoe UI", 10),
            borderwidth=0
        )
        style.configure("Treeview.Heading",
            background=BG_SURFACE,
            foreground=FG_LIGHT,
            font=("Segoe UI", 10, "bold"),
            borderwidth=0
        )
        style.map("Treeview",
            background=[("selected", ACCENT_DIM_ORANGE)],
            foreground=[("selected", FG_LIGHT)]
        )
        style.map("Treeview.Heading",
            background=[("active", BG_SURFACE)],
            foreground=[("active", FG_LIGHT)]
        )
        
        # Configure Scrollbar
        style.configure("Vertical.TScrollbar",
            background=BG_SURFACE,
            troughcolor=BG_PANEL,
            bordercolor=BG_PANEL,
            arrowcolor=FG_LIGHT,
            relief="flat"
        )
        style.map("Vertical.TScrollbar",
            background=[("active", ACCENT_DIM_ORANGE)]
        )
        
        # Configure Progressbar
        style.configure("Horizontal.TProgressbar",
            background=ACCENT_BLUE,
            troughcolor=BG_SURFACE,
            thickness=8
        )

    def build_ui(self):
        # --- Top Section: Header & Folder Browser ---
        top_panel = tk.Frame(self.root, bg=BG_PANEL, pady=10, padx=15)
        top_panel.pack(fill="x", side="top", padx=10, pady=10)
        
        # Logo/Title & Branding Header
        header_frame = tk.Frame(top_panel, bg=BG_PANEL)
        header_frame.pack(fill="x")
        
        title_label = tk.Label(
            header_frame, 
            text="THE ORGANIZER", 
            font=("Segoe UI", 16, "bold"), 
            bg=BG_PANEL, 
            fg=FG_LIGHT
        )
        title_label.pack(side="left")
        
        sep_label = tk.Label(
            header_frame, 
            text="|", 
            font=("Segoe UI", 16), 
            bg=BG_PANEL, 
            fg=FG_MUTED
        )
        sep_label.pack(side="left", padx=10)
        
        studio_label = tk.Label(
            header_frame, 
            text="357 Studio", 
            font=("Segoe UI", 16, "bold"), 
            bg=BG_PANEL, 
            fg=FG_LIGHT
        )
        studio_label.pack(side="left")
        
        solutions_label = tk.Label(
            header_frame, 
            text="Solutions", 
            font=("Segoe UI", 10), 
            bg=BG_PANEL, 
            fg=FG_LIGHT
        )
        solutions_label.pack(side="left", padx=(4, 0), pady=(5, 0))
        
        sub_title = tk.Label(
            top_panel, 
            text="Organize unorganized subfolders of one-shot samples into clean sound categories.", 
            font=("Segoe UI", 9, "italic"), 
            bg=BG_PANEL, 
            fg=FG_MUTED
        )
        sub_title.pack(anchor="w", pady=(0, 10))
        
        # Directory row
        dir_frame = tk.Frame(top_panel, bg=BG_PANEL)
        dir_frame.pack(fill="x", expand=True)
        
        dir_lbl = tk.Label(dir_frame, text="Target Folder:", bg=BG_PANEL, fg=FG_LIGHT, font=("Segoe UI", 10, "bold"))
        dir_lbl.pack(side="left", padx=(0, 10))
        
        self.dir_entry = tk.Entry(dir_frame, bg=BG_SURFACE, fg=FG_LIGHT, insertbackground=FG_LIGHT, bd=0, font=("Segoe UI", 10))
        self.dir_entry.pack(side="left", fill="x", expand=True, ipady=6, padx=5)
        
        browse_btn = ModernButton(
            dir_frame, 
            text="Browse...", 
            command=self.browse_folder,
            fg_color=FG_LIGHT,
            active_fg=FG_LIGHT
        )
        browse_btn.pack(side="left", padx=5)
        
        # Options Frame
        options_frame = tk.Frame(top_panel, bg=BG_PANEL)
        options_frame.pack(fill="x", pady=(10, 0))
        
        self.copy_mode_var = tk.BooleanVar(value=False)
        self.copy_mode_cb = tk.Checkbutton(
            options_frame, 
            text="Copy Mode (Leave originals untouched, safer)", 
            variable=self.copy_mode_var,
            bg=BG_PANEL, 
            fg=FG_LIGHT, 
            selectcolor=BG_PANEL, 
            activebackground=BG_PANEL, 
            activeforeground=ACCENT_ORANGE,
            font=("Segoe UI", 9)
        )
        self.copy_mode_cb.pack(side="left", padx=(0, 20))
        
        self.recursive_var = tk.BooleanVar(value=True)
        self.recursive_cb = tk.Checkbutton(
            options_frame, 
            text="Recursive Scan (Search nested subdirectories)", 
            variable=self.recursive_var,
            bg=BG_PANEL, 
            fg=FG_LIGHT, 
            selectcolor=BG_PANEL, 
            activebackground=BG_PANEL, 
            activeforeground=ACCENT_ORANGE,
            font=("Segoe UI", 9)
        )
        self.recursive_cb.pack(side="left")

        # Layout Mode Row
        layout_frame = tk.Frame(top_panel, bg=BG_PANEL)
        layout_frame.pack(fill="x", pady=(8, 0))
        
        layout_lbl = tk.Label(layout_frame, text="Target Layout Structure:", bg=BG_PANEL, fg=FG_LIGHT, font=("Segoe UI", 9, "bold"))
        layout_lbl.pack(side="left", padx=(0, 15))
        
        self.layout_mode_var = tk.StringVar(value="inplace")
        self.inplace_rb = tk.Radiobutton(
            layout_frame, 
            text="In-Place (create Kicks/Snares inside each subfolder)", 
            variable=self.layout_mode_var, 
            value="inplace",
            command=self.on_layout_mode_changed,
            bg=BG_PANEL, fg=FG_LIGHT, selectcolor=BG_PANEL,
            activebackground=BG_PANEL, activeforeground=ACCENT_ORANGE,
            font=("Segoe UI", 9)
        )
        self.inplace_rb.pack(side="left", padx=(0, 20))
        
        self.consolidate_rb = tk.Radiobutton(
            layout_frame, 
            text="Consolidated (extract all sounds directly to MainFolder/Kicks, etc.)", 
            variable=self.layout_mode_var, 
            value="consolidated",
            command=self.on_layout_mode_changed,
            bg=BG_PANEL, fg=FG_LIGHT, selectcolor=BG_PANEL,
            activebackground=BG_PANEL, activeforeground=ACCENT_ORANGE,
            font=("Segoe UI", 9)
        )
        self.consolidate_rb.pack(side="left")

        # --- Accordion Section: Rules Configurator ---
        self.rules_pane = CollapsiblePane(self.root, title="Custom Keyword Categories & Matching Rules", expanded=False)
        self.rules_pane.pack(fill="x", padx=10, pady=(0, 10))
        self.build_rules_ui()

        # --- Main Section: Split Pane (Sidebar / Files Grid) ---
        main_split = tk.PanedWindow(self.root, orient="horizontal", bd=0, sashwidth=6, bg=BG_DARK)
        main_split.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # Left Panel: Subfolders List
        left_panel = tk.Frame(main_split, bg=BG_PANEL)
        
        self.groups_list = ttk.Treeview(left_panel, columns=("files"), show="tree headings", selectmode="extended")
        self.groups_list.heading("#0", text="Folder/Kit Name", anchor="w")
        self.groups_list.heading("files", text="Files", anchor="center")
        self.groups_list.column("#0", width=220, stretch=True)
        self.groups_list.column("files", width=60, stretch=False, anchor="center")
        self.groups_list.pack(fill="both", expand=True, padx=5, pady=5)
        self.groups_list.bind("<<TreeviewSelect>>", self.on_group_select)
        self.groups_list.bind("<Button-3>", self.show_groups_context_menu)
        
        # Add scrollbar to groups list
        gl_scroll = ttk.Scrollbar(self.groups_list, orient="vertical", command=self.groups_list.yview)
        self.groups_list.configure(yscrollcommand=gl_scroll.set)
        gl_scroll.pack(side="right", fill="y")
        
        # Add Export Buttons at the bottom of the sidebar (Selected vs Whole Main Folder)
        export_frame = tk.Frame(left_panel, bg=BG_PANEL)
        export_frame.pack(fill="x", padx=5, pady=(0, 5))
        
        self.export_selected_btn = ModernButton(
            export_frame,
            text="Export Selected...",
            command=self.open_export_dialog,
            fg_color=ACCENT_ORANGE,
            active_fg=FG_LIGHT,
            font=("Segoe UI", 9, "bold")
        )
        self.export_selected_btn.pack(side="left", fill="x", expand=True, padx=(0, 2))
        
        self.export_main_btn = ModernButton(
            export_frame,
            text="Export Main Folder...",
            command=self.open_export_main_dialog,
            fg_color=ACCENT_ORANGE,
            active_fg=FG_LIGHT,
            font=("Segoe UI", 9, "bold")
        )
        self.export_main_btn.pack(side="right", fill="x", expand=True, padx=(2, 0))
        
        main_split.add(left_panel, minsize=200, width=280)
        
        # Right Panel: Files in selected subfolder
        right_panel = tk.Frame(main_split, bg=BG_PANEL)
        self.right_lbl = tk.Label(right_panel, text="One-Shot Files", bg=BG_PANEL, fg=ACCENT_BLUE, font=("Segoe UI", 10, "bold"), anchor="w")
        
        self.files_grid = ttk.Treeview(
            right_panel, 
            columns=("name", "category", "size", "new_path"), 
            show="headings", 
            selectmode="browse"
        )
        self.files_grid.heading("name", text="File Name", anchor="w")
        self.files_grid.heading("category", text="Detected Category", anchor="center")
        self.files_grid.heading("size", text="Size", anchor="center")
        self.files_grid.heading("new_path", text="New Organized Folder", anchor="w")
        
        self.files_grid.column("name", width=250, minwidth=150, stretch=True)
        self.files_grid.column("category", width=120, minwidth=100, stretch=False, anchor="center")
        self.files_grid.column("size", width=80, minwidth=70, stretch=False, anchor="center")
        self.files_grid.column("new_path", width=250, minwidth=150, stretch=True)
        
        self.files_grid.pack(fill="both", expand=True, padx=5, pady=5)
        self.files_grid.bind("<Button-3>", self.show_context_menu) # Right-click manual reclassify
        
        # Add scrollbar to files grid
        fg_scroll = ttk.Scrollbar(self.files_grid, orient="vertical", command=self.files_grid.yview)
        self.files_grid.configure(yscrollcommand=fg_scroll.set)
        fg_scroll.pack(side="right", fill="y")
        
        main_split.add(right_panel, minsize=400)
        
        # --- Bottom Panel: Controls, Log, and Progress ---
        bottom_panel = tk.Frame(self.root, bg=BG_PANEL)
        bottom_panel.pack(fill="x", side="bottom", padx=10, pady=(0, 10))
        
        # Progress bar & stats label
        prog_frame = tk.Frame(bottom_panel, bg=BG_PANEL)
        prog_frame.pack(fill="x", padx=10, pady=(5, 5))
        
        self.prog_bar = ttk.Progressbar(prog_frame, orient="horizontal", mode="determinate")
        self.prog_bar.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        self.stats_lbl = tk.Label(prog_frame, text="Ready. Scan a folder to begin.", bg=BG_PANEL, fg=FG_MUTED, font=("Segoe UI", 9, "bold"))
        self.stats_lbl.pack(side="right")
        
        # Button bar
        btn_bar = tk.Frame(bottom_panel, bg=BG_PANEL)
        btn_bar.pack(fill="x", padx=10, pady=(5, 10))
        
        self.scan_btn = ModernButton(
            btn_bar, 
            text="Scan", 
            command=self.start_scan, 
            fg_color=ACCENT_ORANGE, 
            active_fg=FG_LIGHT
        )
        self.scan_btn.pack(side="left", padx=(0, 10))
        
        self.organize_btn = ModernButton(
            btn_bar, 
            text="Organize Files", 
            command=self.start_organization, 
            fg_color=ACCENT_GREEN, 
            active_fg=FG_LIGHT
        )
        self.organize_btn.pack(side="left", padx=10)
        self.organize_btn.config(state="disabled") # Enabled only after scan
        
        self.undo_btn = ModernButton(
            btn_bar, 
            text="Undo Last Run", 
            command=self.start_undo, 
            fg_color=ACCENT_RED, 
            active_fg=FG_LIGHT
        )
        self.undo_btn.pack(side="left", padx=10)
        self.check_undo_state()
        
        # Expandable Logs Console
        log_pane = CollapsiblePane(bottom_panel, title="System Logs & Outputs", expanded=False)
        log_pane.pack(fill="x", padx=5, pady=5)
        
        self.log_txt = tk.Text(
            log_pane.content_frame, 
            height=6, 
            bg=BG_DARK, 
            fg=FG_LIGHT, 
            insertbackground=FG_LIGHT, 
            bd=0, 
            font=("Consolas", 9)
        )
        self.log_txt.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Configure tags in log
        self.log_txt.tag_config("info", foreground=ACCENT_BLUE)
        self.log_txt.tag_config("success", foreground=ACCENT_GREEN)
        self.log_txt.tag_config("error", foreground=ACCENT_RED)
        self.log_txt.tag_config("warning", foreground=ACCENT_PEACH)
        
        log_scroll = ttk.Scrollbar(self.log_txt, orient="vertical", command=self.log_txt.yview)
        self.log_txt.configure(yscrollcommand=log_scroll.set)
        log_scroll.pack(side="right", fill="y")

    def build_rules_ui(self):
        """Populates the rules accordion panel with text entry fields for keyword mappings."""
        frame = self.rules_pane.content_frame
        
        # Instructions
        inst = tk.Label(
            frame, 
            text="Enter comma-separated keywords for each category. Priority checks go from top to bottom.",
            bg=BG_PANEL, 
            fg=FG_MUTED, 
            font=("Segoe UI", 9, "italic")
        )
        inst.grid(row=0, column=0, columnspan=4, sticky="w", padx=10, pady=5)
        
        self.rule_entries = {}
        row = 1
        col = 0
        
        # Draw text entries in a grid
        for category in CATEGORY_PRIORITY:
            lbl = tk.Label(frame, text=category, bg=BG_PANEL, fg=FG_LIGHT, font=("Segoe UI", 9, "bold"), anchor="e")
            lbl.grid(row=row, column=col, padx=(10, 5), pady=4, sticky="e")
            
            keywords_str = ", ".join(self.classifier.rules.get(category, []))
            entry = tk.Entry(frame, bg=BG_SURFACE, fg=FG_LIGHT, insertbackground=FG_LIGHT, bd=0, font=("Segoe UI", 9), width=28)
            entry.insert(0, keywords_str)
            entry.grid(row=row, column=col+1, padx=5, pady=4, sticky="w")
            
            self.rule_entries[category] = entry
            
            col += 2
            if col >= 4:
                col = 0
                row += 1
                
        # Action buttons for rules
        btn_frame = tk.Frame(frame, bg=BG_PANEL)
        btn_frame.grid(row=row+1, column=0, columnspan=4, pady=10, sticky="e", padx=10)
        
        save_btn = ModernButton(
            btn_frame, 
            text="Save Rules & Apply", 
            command=self.save_custom_rules,
            fg_color=ACCENT_ORANGE,
            active_fg=FG_LIGHT
        )
        save_btn.pack(side="right", padx=5)
        
        reset_btn = ModernButton(
            btn_frame, 
            text="Reset to Defaults", 
            command=self.reset_default_rules,
            fg_color=FG_MUTED,
            active_fg=FG_LIGHT
        )
        reset_btn.pack(side="right", padx=5)

    def log(self, text: str, tag: str = "info"):
        self.log_txt.config(state="normal")
        self.log_txt.insert(tk.END, text + "\n", tag)
        self.log_txt.see(tk.END)
        self.log_txt.config(state="disabled")

    def browse_folder(self):
        folder = filedialog.askdirectory(title="Select Drum Kits Main Directory")
        if folder:
            self.dir_entry.delete(0, tk.END)
            self.dir_entry.insert(0, os.path.abspath(folder))

    def save_custom_rules(self):
        new_rules = {}
        for category, entry in self.rule_entries.items():
            keywords = [w.strip() for w in entry.get().split(",") if w.strip()]
            new_rules[category] = keywords
            
        if self.classifier.save_rules(new_rules):
            self.log("Rules saved successfully and applied.", "success")
            # If we already scanned, we can re-classify the currently scanned file set in-memory
            # and refresh the UI without hitting the hard drive again.
            if self.scan_results:
                self.reclassify_loaded_files()
        else:
            self.log("Failed to save rules config.", "error")
            messagebox.showerror("Error", "Could not save custom rules configuration.")

    def reset_default_rules(self):
        if messagebox.askyesno("Reset Rules", "Are you sure you want to reset all category keywords to their default values?"):
            self.classifier.save_rules(DEFAULT_RULES)
            for category, entry in self.rule_entries.items():
                entry.delete(0, tk.END)
                entry.insert(0, ", ".join(DEFAULT_RULES.get(category, [])))
            self.log("Rules reset to defaults.", "warning")
            if self.scan_results:
                self.reclassify_loaded_files()

    def reclassify_loaded_files(self):
        """Applies updated rules in-memory to currently loaded scan results and updates views."""
        self.log("Reclassifying loaded files with updated rules...", "info")
        updated_scan = {}
        
        for group, categories in self.scan_results.items():
            updated_scan[group] = {}
            for cat, files in categories.items():
                for file_info in files:
                    file_path = Path(file_info["full_path"])
                    new_cat = self.classifier.classify(file_path)
                    
                    if new_cat not in updated_scan[group]:
                        updated_scan[group][new_cat] = []
                    
                    file_info["detected_category"] = new_cat
                    updated_scan[group][new_cat].append(file_info)
                    
        self.scan_results = updated_scan
        self.update_groups_list()
        self.log("Reclassification completed.", "success")

    def on_layout_mode_changed(self):
        """Callback when layout structure choice is changed. Refreshes the preview column."""
        if self.scan_results:
            self.on_group_select(None)
            self.log(f"Switched preview layout to: {self.layout_mode_var.get().upper()}", "info")

    def check_undo_state(self):
        """Enable the Undo button if history.json exists and contains operations."""
        import json
        if self.history_path.exists():
            try:
                with open(self.history_path, 'r', encoding='utf-8') as f:
                    history_data = json.load(f)
                if history_data.get("operations"):
                    self.undo_btn.config(state="normal")
                    return
            except Exception:
                pass
        self.undo_btn.config(state="disabled")

    def start_undo(self):
        import json
        if not self.history_path.exists():
            return
            
        try:
            with open(self.history_path, 'r', encoding='utf-8') as f:
                history_data = json.load(f)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read undo history:\n{e}")
            return
            
        total_ops = len(history_data.get("operations", []))
        if total_ops == 0:
            messagebox.showinfo("Undo", "No operations found in last history to undo.")
            return
            
        is_folder_export = (history_data.get("type") == "folder_export")
        copy_mode = history_data.get("copy_mode", False)
        
        if is_folder_export:
            mode_str = "DELETE exported folder copies" if copy_mode else "MOVE exported folders back to their original locations"
        else:
            mode_str = "DELETE copied files" if copy_mode else "MOVE files back to their original locations"
            
        confirm_msg = (
            f"Are you sure you want to undo the last operation?\n\n"
            f"This will {mode_str} for {total_ops} targets."
        )
        
        if not messagebox.askyesno("Confirm Undo", confirm_msg):
            return
            
        self.scan_btn.config(state="disabled")
        self.organize_btn.config(state="disabled")
        self.undo_btn.config(state="disabled")
        self.prog_bar.config(value=0)
        self.log("Starting undo process...", "warning")
        
        # Run in thread
        threading.Thread(target=self.run_undo_thread, args=(history_data,), daemon=True).start()

    def run_undo_thread(self, history_data):
        try:
            def progress_cb(current, total):
                percent = (current / total) * 100 if total > 0 else 100
                self.root.after(0, self.update_progress, percent, current, total)
                
            is_folder_export = (history_data.get("type") == "folder_export")
            if is_folder_export:
                operations = self.engine.undo_folder_export(history_data, progress_callback=progress_cb)
            else:
                operations = self.engine.undo_organization(history_data, progress_callback=progress_cb)
                
            self.root.after(0, self.on_undo_complete, operations, history_data)
        except Exception as e:
            self.root.after(0, self.on_undo_error, str(e))

    def on_undo_complete(self, operations, history_data):
        self.scan_btn.config(state="normal")
        self.prog_bar.config(value=100)
        
        is_folder_export = (history_data.get("type") == "folder_export")
        copy_mode = history_data.get("copy_mode", False)
        
        # Delete history file
        if self.history_path.exists():
            try:
                self.history_path.unlink()
            except Exception:
                pass
                
        self.check_undo_state()
        
        successes = sum(1 for op in operations if op[2])
        failures = len(operations) - successes
        
        self.log("Undo operation completed!", "success")
        self.log(f"Restored/Cleaned: {successes} folders/files", "success")
        if failures > 0:
            self.log(f"Failures during undo: {failures}", "error")
            for op in operations:
                if not op[2]:
                    self.log(f"  Undo failed for: {Path(op[0]).name} -> {op[3]}", "error")
                    
        self.stats_lbl.config(text=f"Undo complete. Restored: {successes} targets.")
        
        # Special Case: If we undid a main folder move export, update the entry field back to the original location!
        if is_folder_export and not copy_mode:
            ops = history_data.get("operations", [])
            # If the original main folder itself was restored
            if len(ops) == 1:
                original_src = ops[0].get("src")
                current_dest = ops[0].get("dest")
                if original_src and current_dest:
                    # If dir_entry is currently pointing to current_dest, update it back to original_src!
                    if Path(self.dir_entry.get().strip()).resolve() == Path(current_dest).resolve():
                        self.dir_entry.delete(0, tk.END)
                        self.dir_entry.insert(0, str(original_src))
                        self.log(f"Scanned main folder path restored to: {original_src}", "warning")
                        self.start_scan()
                    else:
                        self.log("Restored folders. Refreshing scanned list.", "warning")
                        self.start_scan()
            else:
                self.log("Restored folders. Refreshing scanned list.", "warning")
                self.start_scan()
        
        messagebox.showinfo(
            "Undo Complete", 
            f"Undo operation completed successfully!\n\n"
            f"Successfully restored: {successes}\n"
            f"Failed: {failures}"
        )

    def on_undo_error(self, err_msg):
        self.scan_btn.config(state="normal")
        self.check_undo_state()
        self.log(f"Undo operation failed: {err_msg}", "error")
        self.stats_lbl.config(text="Undo failed.")
        messagebox.showerror("Undo Error", f"An error occurred during undo:\n{err_msg}")

    def start_scan(self):
        dir_path = self.dir_entry.get().strip()
        if not dir_path:
            messagebox.showwarning("Warning", "Please select a target directory first.")
            return
            
        base_path = Path(dir_path)
        if not base_path.exists() or not base_path.is_dir():
            messagebox.showerror("Error", f"Directory does not exist:\n{dir_path}")
            return
            
        self.scan_btn.config(state="disabled")
        self.organize_btn.config(state="disabled")
        self.log(f"Scanning target directory: {base_path}...", "info")
        
        # Run scan in background thread to keep GUI responsive
        threading.Thread(target=self.run_scan_thread, args=(base_path,), daemon=True).start()

    def run_scan_thread(self, base_path: Path):
        try:
            recursive = self.recursive_var.get()
            self.scan_results = self.engine.scan_directory(base_path, recursive=recursive)
            
            # Count total files
            total_files = sum(
                len(files) 
                for group, cats in self.scan_results.items() 
                for cat, files in cats.items()
            )
            
            self.root.after(0, self.on_scan_complete, total_files)
        except Exception as e:
            self.root.after(0, self.on_scan_error, str(e))

    def on_scan_complete(self, total_files: int):
        self.scan_btn.config(state="normal")
        
        # Populate sidebar subfolders list
        self.update_groups_list()
        
        if total_files > 0:
            self.organize_btn.config(state="normal")
            self.log(f"Scan complete. Found {total_files} audio files across {len(self.scan_results)} folders.", "success")
            self.stats_lbl.config(text=f"Scanned {len(self.scan_results)} folders. Total files: {total_files}")
        else:
            self.organize_btn.config(state="disabled")
            self.log("Scan complete. No audio files found to organize.", "warning")
            self.stats_lbl.config(text="No audio files found.")
            messagebox.showinfo("No Files", "No audio files (.wav, .mp3, etc.) matching the rules were found in the selected folder.")

    def on_scan_error(self, err_msg: str):
        self.scan_btn.config(state="normal")
        self.log(f"Scan failed: {err_msg}", "error")
        self.stats_lbl.config(text="Scan failed.")
        messagebox.showerror("Scan Error", f"An error occurred while scanning:\n{err_msg}")

    def update_groups_list(self):
        """Refreshes the sidebar treeview showing detected subfolders/kits."""
        # Clear existing
        for item in self.groups_list.get_children():
            self.groups_list.delete(item)
            
        if not self.scan_results:
            return
            
        # Add a special "." root node if present
        sorted_groups = sorted(self.scan_results.keys())
        
        for group in sorted_groups:
            # Count files in this group
            file_count = sum(len(files) for files in self.scan_results[group].values())
            
            # Friendly label for root files
            display_name = "[Files at Root]" if group == "." else group
            
            # Insert item
            self.groups_list.insert("", "end", iid=group, text=display_name, values=(file_count,))
            
        # Auto-select the first group if available
        if sorted_groups:
            first_group = sorted_groups[0]
            self.groups_list.selection_set(first_group)
            self.on_group_select(None)

    def on_group_select(self, event):
        """Callback when user selects one or more subfolders (kits) in the sidebar list."""
        selected_items = self.groups_list.selection()
        if not selected_items:
            return
            
        self.selected_group = selected_items[0]
        
        # Format a display name showing all selected folders
        if len(selected_items) == 1:
            display_name = "[Files at Root]" if selected_items[0] == "." else selected_items[0]
        else:
            names = [("[Files at Root]" if g == "." else g) for g in selected_items[:3]]
            display_name = ", ".join(names)
            if len(selected_items) > 3:
                display_name += f", and {len(selected_items) - 3} more..."
                
        self.right_lbl.config(text=f"One-Shots in: {display_name} (Double-click to play .wav)")
        
        # Clear files grid
        for item in self.files_grid.get_children():
            self.files_grid.delete(item)
            
        # Populate files list by consolidating from all selected groups
        consolidated_files = {}
        for category in CATEGORY_PRIORITY + ["Uncategorized"]:
            consolidated_files[category] = []
            
        for group in selected_items:
            group_cats = self.scan_results.get(group, {})
            for category in group_cats:
                consolidated_files[category].extend(group_cats[category])
        
        # Group file listings together by category
        for category in CATEGORY_PRIORITY + ["Uncategorized"]:
            file_list = consolidated_files.get(category, [])
            for file_info in file_list:
                # Format size
                size_bytes = file_info["size"]
                if size_bytes < 1024:
                    size_str = f"{size_bytes} B"
                elif size_bytes < 1024 * 1024:
                    size_str = f"{size_bytes/1024:.1f} KB"
                else:
                    size_str = f"{size_bytes/(1024*1024):.1f} MB"
                
                # Predict target path
                if self.layout_mode_var.get() == "consolidated":
                    target_folder = f"[Main] / {category}"
                else:
                    target_folder = category
                
                # Insert row
                item_id = self.files_grid.insert("", "end", values=(
                    file_info["name"],
                    category,
                    size_str,
                    target_folder
                ))
                
                # Color code category tag
                self.files_grid.tag_configure(category, foreground=CATEGORY_COLORS.get(category, FG_LIGHT))
                self.files_grid.item(item_id, tags=(category,))

    def show_groups_context_menu(self, event):
        """Displays right-click menu on the subfolders treeview to export selected folders."""
        selected = self.groups_list.selection()
        item_id = self.groups_list.identify_row(event.y)
        if item_id and item_id not in selected:
            # If clicked on an unselected item, make it the single selection
            self.groups_list.selection_set(item_id)
            self.on_group_select(None)
            
        menu = tk.Menu(self.root, tearoff=0, bg=BG_PANEL, fg=FG_LIGHT, activebackground=ACCENT_BLUE, activeforeground=BG_DARK)
        menu.add_command(label="Export / Move Selected...", command=self.open_export_dialog)
        menu.tk_popup(event.x_root, event.y_root)

    def open_export_dialog(self):
        selected_groups = self.groups_list.selection()
        if not selected_groups:
            messagebox.showwarning("Warning", "Please select one or more subfolders/kits from the sidebar list first.")
            return
            
        dir_path = self.dir_entry.get().strip()
        if not dir_path:
            return
            
        base_path = Path(dir_path)
        src_dirs = []
        for g in selected_groups:
            if g == ".":
                continue # Skip root files for individual directory exports
            src_dir = base_path / g
            if src_dir.exists() and src_dir.is_dir():
                src_dirs.append(src_dir)
                
        if not src_dirs:
            messagebox.showwarning("Warning", "Please select valid subfolders/kits to export.")
            return
            
        # Ask for destination folder
        dest_parent = filedialog.askdirectory(title=f"Export {len(src_dirs)} Folders - Select Destination Folder")
        if not dest_parent:
            return
            
        dest_parent_path = Path(dest_parent)
        if not dest_parent_path.exists():
            return
            
        self.show_export_window(src_dirs, dest_parent_path)

    def open_export_main_dialog(self):
        dir_path = self.dir_entry.get().strip()
        if not dir_path:
            messagebox.showwarning("Warning", "No directory has been scanned yet.")
            return
            
        main_dir = Path(dir_path)
        if not main_dir.exists() or not main_dir.is_dir():
            messagebox.showerror("Error", f"Scanned main directory not found:\n{dir_path}")
            return
            
        # Ask for destination folder
        dest_parent = filedialog.askdirectory(title=f"Export Main Folder '{main_dir.name}' - Select Destination Folder")
        if not dest_parent:
            return
            
        dest_parent_path = Path(dest_parent)
        if not dest_parent_path.exists():
            return
            
        # Pass main_dir as a single-element list to the unified window
        self.show_export_window([main_dir], dest_parent_path)

    def show_export_window(self, src_dirs: List[Path], dest_parent: Path):
        is_single_main = False
        dir_path = self.dir_entry.get().strip()
        if len(src_dirs) == 1 and dir_path and src_dirs[0].resolve() == Path(dir_path).resolve():
            is_single_main = True
            
        # Calculate combined stats for gauge
        self.log(f"Calculating total stats for {len(src_dirs)} folders...", "info")
        total_files = 0
        total_bytes = 0
        for sd in src_dirs:
            fc, sz = calculate_folder_stats(sd)
            total_files += fc
            total_bytes += sz
            
        # Format size bytes
        if total_bytes < 1024:
            size_str = f"{total_bytes} B"
        elif total_bytes < 1024 * 1024:
            size_str = f"{total_bytes/1024:.1f} KB"
        else:
            size_str = f"{total_bytes/(1024*1024):.1f} MB"
            
        # Create popup modal
        win = tk.Toplevel(self.root)
        if is_single_main:
            win.title(f"Export Main Folder - {src_dirs[0].name}")
        elif len(src_dirs) == 1:
            win.title(f"Export - {src_dirs[0].name}")
        else:
            win.title(f"Export - {len(src_dirs)} Folders")
            
        win.geometry("500x340")
        win.configure(bg=BG_DARK)
        win.transient(self.root)
        win.grab_set()
        
        # Center Toplevel relative to root
        win.update_idletasks()
        width = win.winfo_width()
        height = win.winfo_height()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (width // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (height // 2)
        win.geometry(f"+{x}+{y}")
        
        # Content frame
        frame = tk.Frame(win, bg=BG_PANEL, padx=15, pady=15)
        frame.pack(fill="both", expand=True, padx=15, pady=15)
        
        # Title text
        if is_single_main:
            title_text = f"Export Main Folder: {src_dirs[0].name}"
        elif len(src_dirs) == 1:
            title_text = f"Export Kit: {src_dirs[0].name}"
        else:
            title_text = f"Export {len(src_dirs)} Selected Kits"
            
        title = tk.Label(frame, text=title_text, font=("Segoe UI", 12, "bold"), bg=BG_PANEL, fg=ACCENT_BLUE)
        title.pack(anchor="w", pady=(0, 5))
        
        # Source display
        if len(src_dirs) == 1:
            src_lbl_text = f"Source: {src_dirs[0]}"
        else:
            folders_list_str = ", ".join(sd.name for sd in src_dirs[:3])
            if len(src_dirs) > 3:
                folders_list_str += f", and {len(src_dirs) - 3} more..."
            src_lbl_text = f"Source Kits: {folders_list_str}"
            
        src_lbl = tk.Label(frame, text=src_lbl_text, bg=BG_PANEL, fg=FG_MUTED, font=("Segoe UI", 8), justify="left", anchor="w", wraplength=420)
        src_lbl.pack(anchor="w", fill="x", pady=(0, 2))
        
        dest_lbl = tk.Label(frame, text=f"Destination Parent: {dest_parent}", bg=BG_PANEL, fg=FG_MUTED, font=("Segoe UI", 8), justify="left", anchor="w", wraplength=420)
        dest_lbl.pack(anchor="w", fill="x", pady=(0, 10))
        
        # Size gauge display
        stats_frame = tk.Frame(frame, bg=BG_SURFACE, padx=10, pady=5)
        stats_frame.pack(fill="x", pady=(0, 15))
        stats_txt = f"Gauge: {total_files} files | Total size: {size_str}"
        gauge_lbl = tk.Label(stats_frame, text=stats_txt, bg=BG_SURFACE, fg=ACCENT_PEACH, font=("Segoe UI", 10, "bold"))
        gauge_lbl.pack(anchor="w")
        
        # Radio buttons
        export_mode_var = tk.StringVar(value="copy")
        copy_rb = tk.Radiobutton(
            frame, text="Copy files (keep originals in place)", variable=export_mode_var, value="copy",
            bg=BG_PANEL, fg=FG_LIGHT, selectcolor=BG_PANEL, activebackground=BG_PANEL, activeforeground=ACCENT_ORANGE, font=("Segoe UI", 9)
        )
        copy_rb.pack(anchor="w", pady=2)
        
        move_rb = tk.Radiobutton(
            frame, text="Move files (delete originals from source after copy)", variable=export_mode_var, value="move",
            bg=BG_PANEL, fg=FG_LIGHT, selectcolor=BG_PANEL, activebackground=BG_PANEL, activeforeground=ACCENT_ORANGE, font=("Segoe UI", 9)
        )
        move_rb.pack(anchor="w", pady=2)
        
        # Progress elements
        prog_frame = tk.Frame(frame, bg=BG_PANEL)
        prog_frame.pack(fill="x", pady=10)
        
        dlg_prog = ttk.Progressbar(prog_frame, orient="horizontal", mode="determinate")
        dlg_prog.pack(fill="x", expand=True)
        
        dlg_status = tk.Label(prog_frame, text="Ready to export.", bg=BG_PANEL, fg=FG_MUTED, font=("Segoe UI", 8, "italic"), justify="left", anchor="w", wraplength=420)
        dlg_status.pack(anchor="w", fill="x", pady=(2, 0))
        
        # Button bar
        btn_frame = tk.Frame(frame, bg=BG_PANEL)
        btn_frame.pack(fill="x", side="bottom")
        
        cancel_btn = ModernButton(
            btn_frame, text="Cancel", command=win.destroy,
            fg_color=FG_LIGHT, active_fg=ACCENT_RED
        )
        cancel_btn.pack(side="right", padx=5)
        
        export_action_btn = ModernButton(
            btn_frame, text="Start Export", 
            command=lambda: self.run_export_task(src_dirs, dest_parent, export_mode_var.get() == "move", dlg_prog, dlg_status, export_action_btn, cancel_btn, win),
            fg_color=ACCENT_ORANGE, active_fg=FG_LIGHT
        )
        export_action_btn.pack(side="right", padx=5)

    def run_export_task(self, src_dirs: List[Path], dest_parent: Path, move_mode: bool, progress_bar, status_label, action_btn, cancel_btn, window):
        action_btn.config(state="disabled")
        cancel_btn.config(state="disabled")
        
        def bg_run():
            # Get stats for all targets
            folder_stats = []
            total_global_files = 0
            total_global_bytes = 0
            
            for sd in src_dirs:
                fc, sz = calculate_folder_stats(sd)
                folder_stats.append((sd, fc, sz))
                total_global_files += fc
                total_global_bytes += sz
                
            global_processed_files = 0
            global_processed_bytes = 0
            
            success = True
            err_msg = ""
            history_ops = []
            
            for idx, (src_dir, fc, sz) in enumerate(folder_stats):
                if fc == 0:
                    continue
                    
                def progress_cb(current, total, current_bytes, total_bytes, filename):
                    cur_files = global_processed_files + current
                    cur_bytes = global_processed_bytes + current_bytes
                    percent = (cur_files / total_global_files) * 100 if total_global_files > 0 else 100
                    
                    def format_b(b):
                        if b < 1024: return f"{b} B"
                        elif b < 1024*1024: return f"{b/1024:.1f} KB"
                        else: return f"{b/(1024*1024):.1f} MB"
                        
                    status_text = (
                        f"Folder {idx+1}/{len(src_dirs)}: {src_dir.name}\n"
                        f"Copying: {filename}\n"
                        f"Total Progress: {cur_files} of {total_global_files} files | "
                        f"{format_b(cur_bytes)} / {format_b(total_global_bytes)} ({percent:.1f}%)"
                    )
                    self.root.after(0, lambda: progress_bar.config(value=percent))
                    self.root.after(0, lambda: status_label.config(text=status_text, fg=FG_LIGHT))
                    
                sub_success, sub_msg = export_folder(src_dir, dest_parent, move_mode=move_mode, progress_callback=progress_cb)
                
                if not sub_success:
                    success = False
                    err_msg = f"Error in '{src_dir.name}': {sub_msg}"
                    break
                    
                # Log success for this directory in history incrementally
                history_ops.append({
                    "src": str(src_dir),
                    "dest": str(dest_parent / src_dir.name),
                    "success": True
                })
                
                global_processed_files += fc
                global_processed_bytes += sz
                
            def complete_gui():
                window.destroy()
                
                # Save history for folder export undo (even for partially successful ones)!
                if history_ops:
                    import json
                    try:
                        history_data = {
                            "type": "folder_export",
                            "copy_mode": not move_mode,
                            "operations": history_ops
                        }
                        with open(self.history_path, 'w', encoding='utf-8') as f:
                            json.dump(history_data, f, indent=4)
                    except Exception as e:
                        self.log(f"Failed to save undo history for folder export: {e}", "warning")
                        
                    self.check_undo_state()
                    
                if success:
                    op_type = "Moved" if move_mode else "Copied"
                    self.log(f"Export Successful: {len(src_dirs)} folders {op_type.lower()} to '{dest_parent}'", "success")
                    messagebox.showinfo("Export Success", f"{len(src_dirs)} folders have been successfully {op_type.lower()}!")
                    
                    # Special Case: If the main folder itself was moved, update the entry field to the new location!
                    main_dir_path = Path(self.dir_entry.get().strip())
                    if move_mode and len(src_dirs) == 1 and src_dirs[0].resolve() == main_dir_path.resolve():
                        new_main_path = dest_parent / src_dirs[0].name
                        self.dir_entry.delete(0, tk.END)
                        self.dir_entry.insert(0, str(new_main_path))
                        self.log(f"Scanned main folder path updated to: {new_main_path}", "warning")
                        self.start_scan()
                    elif move_mode:
                        # Otherwise, if subfolders were moved, refresh scanned list
                        self.log("Scanned folders were moved. Refreshing scanned list.", "warning")
                        self.start_scan()
                else:
                    self.log(f"Export Failed: {err_msg}", "error")
                    if move_mode and history_ops:
                        self.log("Some scanned folders were moved before the failure. Refreshing scanned list.", "warning")
                        self.start_scan()
                    messagebox.showerror("Export Error", f"Export failed:\n{err_msg}")
                    
            self.root.after(0, complete_gui)
            
        threading.Thread(target=bg_run, daemon=True).start()



    def show_context_menu(self, event):
        """Shows right-click menu to manually reclassify a file's category."""
        selected_items = self.files_grid.selection()
        if not selected_items:
            return
            
        item = selected_items[0]
        item_values = self.files_grid.item(item, "values")
        filename = item_values[0]
        current_cat = item_values[1]
        
        # Create menu
        menu = tk.Menu(self.root, tearoff=0, bg=BG_PANEL, fg=FG_LIGHT, activebackground=ACCENT_BLUE, activeforeground=BG_DARK)
        
        # Add categories as menu items
        for cat in CATEGORY_PRIORITY + ["Uncategorized"]:
            menu.add_command(
                label=f"Mark as {cat}", 
                command=lambda c=cat: self.manually_reclassify_file(filename, current_cat, c, item)
            )
            
        menu.tk_popup(event.x_root, event.y_root)

    def manually_reclassify_file(self, filename: str, old_cat: str, new_cat: str, tree_item_id):
        if old_cat == new_cat:
            return
            
        # Find which selected group contains this file
        target_group = None
        file_info = None
        for group in self.groups_list.selection():
            old_cat_files = self.scan_results.get(group, {}).get(old_cat, [])
            file_info = next((f for f in old_cat_files if f["name"] == filename), None)
            if file_info:
                target_group = group
                break
                
        if not target_group or not file_info:
            return
            
        # Move in-memory
        self.scan_results[target_group][old_cat].remove(file_info)
        file_info["detected_category"] = new_cat
        
        if new_cat not in self.scan_results[target_group]:
            self.scan_results[target_group][new_cat] = []
        self.scan_results[target_group][new_cat].append(file_info)
        
        # Update files grid row
        target_path = f"[Main] / {new_cat}" if self.layout_mode_var.get() == "consolidated" else new_cat
        self.files_grid.item(tree_item_id, values=(
            filename,
            new_cat,
            self.files_grid.item(tree_item_id, "values")[2],
            target_path
        ))
        
        # Re-apply color coding tag
        self.files_grid.item(tree_item_id, tags=(new_cat,))
        self.files_grid.tag_configure(new_cat, foreground=CATEGORY_COLORS.get(new_cat, FG_LIGHT))
        
        # Update sidebar count
        file_count = sum(len(files) for files in self.scan_results[target_group].values())
        self.groups_list.item(target_group, values=(file_count,))
        
        self.log(f"Manually marked '{filename}' as {new_cat} in kit '{target_group}'", "info")

    def start_organization(self):
        dir_path = self.dir_entry.get().strip()
        if not dir_path or not self.scan_results:
            return
            
        base_path = Path(dir_path)
        copy_mode = self.copy_mode_var.get()
        
        total_files = sum(
            len(files) 
            for group, cats in self.scan_results.items() 
            for cat, files in cats.items()
        )
        
        consolidate_mode = (self.layout_mode_var.get() == "consolidated")
        layout_str = "CONSOLIDATED into main folder" if consolidate_mode else "IN-PLACE inside subfolders"
        mode_str = "COPY" if copy_mode else "MOVE"
        
        confirm_msg = (
            f"Are you sure you want to organize {total_files} files?\n\n"
            f"Operation: {mode_str}\n"
            f"Layout Structure: {layout_str}\n\n"
            f"Target: {base_path}"
        )
        
        if not messagebox.askyesno("Confirm Organization", confirm_msg):
            return
            
        self.scan_btn.config(state="disabled")
        self.organize_btn.config(state="disabled")
        self.prog_bar.config(value=0)
        self.log(f"Starting file organization ({mode_str} - {layout_str})...", "warning")
        
        # Execute in background thread
        threading.Thread(target=self.run_organization_thread, args=(base_path, copy_mode, consolidate_mode), daemon=True).start()

    def run_organization_thread(self, base_path: Path, copy_mode: bool, consolidate_mode: bool):
        try:
            # Define progress callback
            def progress_cb(current, total):
                percent = (current / total) * 100
                self.root.after(0, self.update_progress, percent, current, total)
                
            operations = self.engine.organize(
                base_path, 
                self.scan_results, 
                copy_mode=copy_mode, 
                consolidate_mode=consolidate_mode,
                progress_callback=progress_cb
            )
            
            self.root.after(0, self.on_organization_complete, operations)
        except Exception as e:
            self.root.after(0, self.on_organization_error, str(e))

    def update_progress(self, percent: float, current: int, total: int):
        self.prog_bar.config(value=percent)
        self.stats_lbl.config(text=f"Processed: {current}/{total} ({percent:.1f}%)")

    def on_organization_complete(self, operations: List):
        self.scan_btn.config(state="normal")
        self.organize_btn.config(state="disabled")
        self.prog_bar.config(value=100)
        
        successes = sum(1 for op in operations if op[2])
        failures = len(operations) - successes
        
        self.log("File organization execution finished!", "success")
        self.log(f"Total Successful Operations: {successes}", "success")
        if failures > 0:
            self.log(f"Total Failures: {failures}", "error")
            for op in operations:
                if not op[2]:
                    self.log(f"  Failed to move: {Path(op[0]).name} -> Reason: {op[3]}", "error")
                    
        self.stats_lbl.config(text=f"Completed. Organized: {successes} files.")
        
        # Save history for undo
        import json
        history_ops = []
        for src, dest, success, msg in operations:
            if success and dest and src != dest and "Already in place" not in msg:
                history_ops.append({
                    "src": src,
                    "dest": dest,
                    "success": success
                })
        
        if history_ops:
            try:
                history_data = {
                    "type": "file_organization",
                    "copy_mode": self.copy_mode_var.get(),
                    "operations": history_ops
                }
                with open(self.history_path, 'w', encoding='utf-8') as f:
                    json.dump(history_data, f, indent=4)
            except Exception as e:
                self.log(f"Failed to save history log for undo: {e}", "warning")
        
        # Refresh undo button state
        self.check_undo_state()
        
        # Clear scan results since files have moved
        self.scan_results = {}
        for item in self.groups_list.get_children():
            self.groups_list.delete(item)
        for item in self.files_grid.get_children():
            self.files_grid.delete(item)
            
        messagebox.showinfo(
            "Organization Complete", 
            f"Successfully processed files!\n\n"
            f"Successful: {successes}\n"
            f"Failed: {failures}\n\n"
            f"See console output logs for details."
        )

    def on_organization_error(self, err_msg: str):
        self.scan_btn.config(state="normal")
        self.organize_btn.config(state="normal")
        self.log(f"Organization failed: {err_msg}", "error")
        self.stats_lbl.config(text="Organization failed.")
        messagebox.showerror("Execution Error", f"An error occurred during organization:\n{err_msg}")


def main():
    root = tk.Tk()
    app = DrumOrganizerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
