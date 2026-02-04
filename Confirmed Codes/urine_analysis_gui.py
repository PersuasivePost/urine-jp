import os
import cv2
import sqlite3
import numpy as np
import pandas as pd
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
from datetime import datetime

# ==============================
# CONFIG
# ==============================
class UrineAnalysisApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Urine Analysis System")
        self.root.geometry("1200x800")
        self.root.configure(bg="#f0f0f0")
        
        # Default paths
        self.patch_dir = None
        self.csv_folder = r"c:\Users\Ashvatth\OneDrive\Desktop\AshWorks\J\urine\patch_csv_files"
        self.db_path = r"c:\Users\Ashvatth\OneDrive\Desktop\AshWorks\J\urine\Confirmed Codes\urine_color_lookup.db"
        
        self.PAD_SEQUENCE = [
            "GLU", "BIL", "KET", "SG", "BLO",
            "PH", "PRO", "URO", "NIT", "LEU"
        ]
        
        self.PAD_ANALYTE_MAP = {
            1: ("GLU", "Glucose", "mg/dL (mmol/L)"),
            2: ("BIL", "Bilirubin", "mg/dL (µmol/L)"),
            3: ("KET", "Ketone", "mg/dL (mmol/L)"),
            4: ("SG",  "Specific Gravity", ""),
            5: ("BLO", "Blood", "Ery/µL"),
            6: ("PH",  "pH", ""),
            7: ("PRO", "Protein", "mg/dL (g/L)"),
            8: ("URO", "Urobilinogen", "mg/dL (µmol/L)"),
            9: ("NIT", "Nitrite", ""),
            10: ("LEU", "Leukocyte", "Leu/µL")
        }
        
        self.VALUE_LABELS = {
            "LEU": ["-", "15 ±", "70 +", "125 ++", "500 +++"],
            "NIT": ["-", "+"],
            "URO": ["0.2(3.5)", "1(17)", "2(35)", "4(70)", "8(140)", "12(200)"],
            "PRO": ["-", "15(0.15)", "30(0.3)", "100(1.0)", "300(3.0)", "2000(20)"],
            "PH":  ["5.0", "6.0", "6.5", "7.0", "7.5", "8.0", "9.0"],
            "BLO": ["-", "±", "+", "++", "+++", "5–10", "50 Ery/µL"],
            "SG":  ["1.000", "1.005", "1.010", "1.015", "1.020", "1.025", "1.030"],
            "KET": ["-", "5(0.5)", "15(1.5)", "40(4.0)", "80(8.0)", "160(16)"],
            "BIL": ["-", "1(17)", "2(35)", "4(70)"],
            "GLU": ["-", "100(5)", "250(15)", "500(30)", "1000(60)", "≥2000(110)"]
        }
        
        self.patch_images = []
        self.results_df = None
        
        self.create_widgets()
        
    def create_widgets(self):
        # Title
        title_frame = tk.Frame(self.root, bg="#2c3e50", height=80)
        title_frame.pack(fill=tk.X, padx=0, pady=0)
        title_frame.pack_propagate(False)
        
        title_label = tk.Label(title_frame, text="🧪 Urine Analysis System",
                              font=("Arial", 24, "bold"), bg="#2c3e50", fg="white")
        title_label.pack(pady=20)
        
        # Main container
        main_container = tk.Frame(self.root, bg="#f0f0f0")
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Left panel - Controls
        left_panel = tk.Frame(main_container, bg="white", relief=tk.RAISED, borderwidth=2)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 10), pady=0)
        
        # Control buttons
        control_frame = tk.LabelFrame(left_panel, text="Controls", font=("Arial", 12, "bold"),
                                     bg="white", fg="#2c3e50", padx=10, pady=10)
        control_frame.pack(fill=tk.X, padx=10, pady=10)
        
        btn_style = {"font": ("Arial", 10), "width": 25, "height": 2}
        
        self.btn_select_images = tk.Button(control_frame, text="📁 Select Patch Images",
                                          command=self.select_images, bg="#3498db", fg="white",
                                          activebackground="#2980b9", **btn_style)
        self.btn_select_images.pack(pady=5)
        
        self.btn_init_db = tk.Button(control_frame, text="🗄️ Initialize Database",
                                    command=self.initialize_database, bg="#9b59b6", fg="white",
                                    activebackground="#8e44ad", **btn_style)
        self.btn_init_db.pack(pady=5)
        
        self.btn_analyze = tk.Button(control_frame, text="🔬 Analyze Samples",
                                    command=self.analyze_samples, bg="#27ae60", fg="white",
                                    activebackground="#229954", **btn_style, state=tk.DISABLED)
        self.btn_analyze.pack(pady=5)
        
        self.btn_export = tk.Button(control_frame, text="💾 Export Results",
                                   command=self.export_results, bg="#e67e22", fg="white",
                                   activebackground="#d35400", **btn_style, state=tk.DISABLED)
        self.btn_export.pack(pady=5)
        
        self.btn_clear = tk.Button(control_frame, text="🗑️ Clear All",
                                  command=self.clear_all, bg="#e74c3c", fg="white",
                                  activebackground="#c0392b", **btn_style)
        self.btn_clear.pack(pady=5)
        
        # Status frame
        status_frame = tk.LabelFrame(left_panel, text="Status", font=("Arial", 12, "bold"),
                                    bg="white", fg="#2c3e50", padx=10, pady=10)
        status_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.status_text = tk.Text(status_frame, height=15, width=35, wrap=tk.WORD,
                                  font=("Courier", 9), bg="#ecf0f1", state=tk.DISABLED)
        status_text_scroll = tk.Scrollbar(status_frame, command=self.status_text.yview)
        self.status_text.configure(yscrollcommand=status_text_scroll.set)
        self.status_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        status_text_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Right panel - Results
        right_panel = tk.Frame(main_container, bg="white", relief=tk.RAISED, borderwidth=2)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=0, pady=0)
        
        # Patch images display
        image_frame = tk.LabelFrame(right_panel, text="Patch Images", font=("Arial", 12, "bold"),
                                   bg="white", fg="#2c3e50", padx=10, pady=10)
        image_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.image_canvas = tk.Canvas(image_frame, height=120, bg="#ecf0f1")
        self.image_canvas.pack(fill=tk.X)
        
        # Results table
        results_frame = tk.LabelFrame(right_panel, text="Analysis Results", font=("Arial", 12, "bold"),
                                     bg="white", fg="#2c3e50", padx=10, pady=10)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create Treeview
        tree_scroll = tk.Scrollbar(results_frame)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.results_tree = ttk.Treeview(results_frame, columns=("Pad", "Analyte", "Value", "Unit"),
                                        show="headings", yscrollcommand=tree_scroll.set, height=15)
        tree_scroll.config(command=self.results_tree.yview)
        
        # Configure columns
        self.results_tree.heading("Pad", text="Pad #")
        self.results_tree.heading("Analyte", text="Analyte")
        self.results_tree.heading("Value", text="Value")
        self.results_tree.heading("Unit", text="Unit")
        
        self.results_tree.column("Pad", width=80, anchor=tk.CENTER)
        self.results_tree.column("Analyte", width=150, anchor=tk.W)
        self.results_tree.column("Value", width=150, anchor=tk.CENTER)
        self.results_tree.column("Unit", width=200, anchor=tk.W)
        
        # Alternating row colors
        self.results_tree.tag_configure('oddrow', background='#f9f9f9')
        self.results_tree.tag_configure('evenrow', background='white')
        
        self.results_tree.pack(fill=tk.BOTH, expand=True)
        
        self.log_status("System initialized. Ready to start.")
        
    def log_status(self, message):
        """Add message to status log"""
        self.status_text.configure(state=tk.NORMAL)
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.status_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.status_text.see(tk.END)
        self.status_text.configure(state=tk.DISABLED)
        self.root.update()
        
    def select_images(self):
        """Select folder containing patch images"""
        folder = filedialog.askdirectory(title="Select Patch Images Folder")
        if folder:
            self.patch_dir = folder
            # Load and display images
            self.load_patch_images()
            self.log_status(f"Selected folder: {folder}")
            if len(self.patch_images) == 10:
                self.btn_analyze.configure(state=tk.NORMAL)
                self.log_status(f"✓ Found {len(self.patch_images)} patch images")
            else:
                self.log_status(f"⚠ Warning: Found {len(self.patch_images)} images (expected 10)")
                messagebox.showwarning("Image Count", 
                                     f"Expected 10 patch images but found {len(self.patch_images)}")
    
    def load_patch_images(self):
        """Load patch images from selected folder"""
        if not self.patch_dir:
            return
            
        self.patch_images = []
        patch_files = sorted([
            f for f in os.listdir(self.patch_dir)
            if f.lower().endswith((".jpg", ".jpeg", ".png"))
        ])
        
        # Clear canvas
        self.image_canvas.delete("all")
        
        x_offset = 10
        for idx, file in enumerate(patch_files[:10]):
            path = os.path.join(self.patch_dir, file)
            self.patch_images.append(path)
            
            # Load and resize for display
            img = Image.open(path)
            img.thumbnail((80, 80))
            photo = ImageTk.PhotoImage(img)
            
            # Keep reference to prevent garbage collection
            if not hasattr(self, 'image_refs'):
                self.image_refs = []
            self.image_refs.append(photo)
            
            self.image_canvas.create_image(x_offset, 10, anchor=tk.NW, image=photo)
            self.image_canvas.create_text(x_offset + 40, 100, text=f"Pad {idx+1}",
                                         font=("Arial", 8))
            x_offset += 100
    
    def initialize_database(self):
        """Initialize database with color lookup data"""
        try:
            self.log_status("Initializing database...")
            conn = self.create_database()
            self.build_lookup_table(conn)
            conn.close()
            self.log_status("✓ Database initialized successfully")
            messagebox.showinfo("Success", "Database initialized successfully!")
        except Exception as e:
            self.log_status(f"✗ Error initializing database: {str(e)}")
            messagebox.showerror("Error", f"Failed to initialize database:\n{str(e)}")
    
    def create_database(self):
        """Create database connection and table"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DROP TABLE IF EXISTS color_lookup")
        cursor.execute("""
            CREATE TABLE color_lookup (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pad_index INTEGER,
                analyte_code TEXT,
                analyte_name TEXT,
                level_index INTEGER,
                value_label TEXT,
                r_mean REAL,
                g_mean REAL,
                b_mean REAL
            )
        """)
        conn.commit()
        return conn
    
    def build_lookup_table(self, conn):
        """Build color lookup table from CSV files"""
        cursor = conn.cursor()
        files = os.listdir(self.csv_folder)
        csv_map = {}
        
        for f in files:
            if f.lower().endswith(".csv"):
                for analyte in self.PAD_SEQUENCE:
                    if analyte in f.upper():
                        csv_map[analyte] = f
        
        for pad_index, analyte_code in enumerate(self.PAD_SEQUENCE, start=1):
            if analyte_code not in csv_map:
                self.log_status(f"⚠ Warning: No CSV found for {analyte_code}")
                continue
                
            df = pd.read_csv(os.path.join(self.csv_folder, csv_map[analyte_code]))
            labels = self.VALUE_LABELS[analyte_code]
            _, analyte_name, _ = self.PAD_ANALYTE_MAP[pad_index]
            
            for i, row in df.iterrows():
                cursor.execute("""
                    INSERT INTO color_lookup
                    (pad_index, analyte_code, analyte_name,
                     level_index, value_label, r_mean, g_mean, b_mean)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    pad_index,
                    analyte_code,
                    analyte_name,
                    i,
                    labels[min(i, len(labels)-1)],
                    row["R_mean"],
                    row["G_mean"],
                    row["B_mean"]
                ))
        
        conn.commit()
        self.log_status(f"Loaded data for {len(csv_map)} analytes")
    
    def analyze_samples(self):
        """Analyze patch images and predict values"""
        if not self.patch_images:
            messagebox.showwarning("No Images", "Please select patch images first!")
            return
        
        if len(self.patch_images) != 10:
            if not messagebox.askyesno("Confirm", 
                f"Found {len(self.patch_images)} images instead of 10. Continue anyway?"):
                return
        
        try:
            self.log_status("Starting analysis...")
            
            # Extract RGB values
            pad_rgb_map = self.extract_pad_rgbs()
            
            # Connect to database
            conn = sqlite3.connect(self.db_path)
            
            # Predict
            self.results_df = self.predict_all_pads(conn, pad_rgb_map)
            conn.close()
            
            # Display results
            self.display_results()
            
            self.log_status("✓ Analysis complete!")
            self.btn_export.configure(state=tk.NORMAL)
            
        except Exception as e:
            self.log_status(f"✗ Error during analysis: {str(e)}")
            messagebox.showerror("Error", f"Analysis failed:\n{str(e)}")
    
    def extract_pad_rgbs(self):
        """Extract RGB values from patch images"""
        pad_rgb_map = {}
        
        for idx, path in enumerate(self.patch_images, start=1):
            img = cv2.imread(path)
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            
            pixels = img.reshape(-1, 3)
            mean_rgb = np.mean(pixels, axis=0).astype(int)
            
            pad_rgb_map[idx] = mean_rgb.tolist()
            self.log_status(f"Pad {idx}: RGB = {mean_rgb.tolist()}")
        
        return pad_rgb_map
    
    def predict_all_pads(self, conn, pad_rgb_map):
        """Predict values for all pads"""
        results = []
        
        for pad_index, rgb in pad_rgb_map.items():
            rgb = np.array(rgb, dtype=float)
            
            df = pd.read_sql("""
                SELECT level_index, value_label, r_mean, g_mean, b_mean
                FROM color_lookup
                WHERE pad_index = ?
            """, conn, params=(pad_index,))
            
            if df.empty:
                self.log_status(f"⚠ No reference data for pad {pad_index}")
                continue
            
            ref_rgb = df[["r_mean", "g_mean", "b_mean"]].values
            distances = np.linalg.norm(ref_rgb - rgb, axis=1)
            
            best_idx = distances.argmin()
            best = df.iloc[best_idx]
            
            _, analyte, unit = self.PAD_ANALYTE_MAP[pad_index]
            
            results.append({
                "Pad": pad_index,
                "Analyte": analyte,
                "Level": int(best["level_index"]),
                "Value": best["value_label"],
                "Unit": unit
            })
        
        return pd.DataFrame(results)
    
    def display_results(self):
        """Display results in treeview"""
        # Clear existing results
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        
        if self.results_df is None or self.results_df.empty:
            return
        
        # Insert new results
        for idx, row in self.results_df.iterrows():
            tag = 'evenrow' if idx % 2 == 0 else 'oddrow'
            self.results_tree.insert("", tk.END, 
                                   values=(row["Pad"], row["Analyte"], 
                                          row["Value"], row["Unit"]),
                                   tags=(tag,))
    
    def export_results(self):
        """Export results to CSV file"""
        if self.results_df is None or self.results_df.empty:
            messagebox.showwarning("No Results", "No results to export!")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"urine_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        
        if filename:
            try:
                self.results_df.to_csv(filename, index=False)
                self.log_status(f"✓ Results exported to: {filename}")
                messagebox.showinfo("Success", f"Results exported successfully to:\n{filename}")
            except Exception as e:
                self.log_status(f"✗ Error exporting results: {str(e)}")
                messagebox.showerror("Error", f"Failed to export results:\n{str(e)}")
    
    def clear_all(self):
        """Clear all data and reset"""
        if messagebox.askyesno("Confirm", "Clear all data and reset?"):
            self.patch_images = []
            self.results_df = None
            self.image_refs = []
            
            # Clear displays
            self.image_canvas.delete("all")
            for item in self.results_tree.get_children():
                self.results_tree.delete(item)
            
            # Disable buttons
            self.btn_analyze.configure(state=tk.DISABLED)
            self.btn_export.configure(state=tk.DISABLED)
            
            self.log_status("System reset. Ready to start.")

# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    root = tk.Tk()
    app = UrineAnalysisApp(root)
    root.mainloop()
