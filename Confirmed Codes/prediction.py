import os
import cv2
import sqlite3
import numpy as np
import pandas as pd

# ==============================
# CONFIG
# ==============================
PATCH_DIR = r"G:\My Drive\Prachi Maam\PREDICTION LOGIC\Confirmed Codes\images"   # patch images
CSV_FOLDER = r"G:\My Drive\Prachi Maam\PREDICTION LOGIC\patch_csv_files"
DB_PATH = "urine_color_lookup.db"

PAD_SEQUENCE = [
    "GLU", "BIL", "KET", "SG", "BLO",
    "PH", "PRO", "URO", "NIT", "LEU"
]

# ==============================
# PAD → ANALYTE MAP
# ==============================
PAD_ANALYTE_MAP = {
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

# ==============================
# VALUE LABELS
# ==============================
VALUE_LABELS = {
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

# ==============================
# DATABASE SETUP
# ==============================
def create_database():
    conn = sqlite3.connect(DB_PATH)
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

# ==============================
# BUILD LOOKUP TABLE
# ==============================
def build_lookup_table(conn):
    cursor = conn.cursor()
    files = os.listdir(CSV_FOLDER)
    csv_map = {}

    for f in files:
        if f.lower().endswith(".csv"):
            for analyte in PAD_SEQUENCE:
                if analyte in f.upper():
                    csv_map[analyte] = f

    for pad_index, analyte_code in enumerate(PAD_SEQUENCE, start=1):
        df = pd.read_csv(os.path.join(CSV_FOLDER, csv_map[analyte_code]))
        labels = VALUE_LABELS[analyte_code]
        _, analyte_name, _ = PAD_ANALYTE_MAP[pad_index]

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

# ==============================
# EXTRACT RGB FROM PATCH IMAGES
# ==============================
def extract_pad_rgbs():
    pad_rgb_map = {}

    patch_files = sorted([
        f for f in os.listdir(PATCH_DIR)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ])

    if len(patch_files) != 10:
        raise ValueError("Exactly 10 patch images are required")

    for idx, file in enumerate(patch_files, start=1):
        path = os.path.join(PATCH_DIR, file)
        img = cv2.imread(path)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        pixels = img.reshape(-1, 3)
        mean_rgb = np.mean(pixels, axis=0).astype(int)

        pad_rgb_map[idx] = mean_rgb.tolist()

    return pad_rgb_map

# ==============================
# PREDICT ALL PADS
# ==============================
def predict_all_pads(conn, pad_rgb_map):
    results = []

    for pad_index, rgb in pad_rgb_map.items():
        rgb = np.array(rgb, dtype=float)

        df = pd.read_sql("""
            SELECT level_index, value_label, r_mean, g_mean, b_mean
            FROM color_lookup
            WHERE pad_index = ?
        """, conn, params=(pad_index,))

        ref_rgb = df[["r_mean", "g_mean", "b_mean"]].values
        distances = np.linalg.norm(ref_rgb - rgb, axis=1)

        best_idx = distances.argmin()
        best = df.iloc[best_idx]

        _, analyte, unit = PAD_ANALYTE_MAP[pad_index]

        results.append({
            "Pad": pad_index,
            "Analyte": analyte,
            "Level": int(best["level_index"]),
            "Value": best["value_label"],
            "Unit": unit
        })

    return pd.DataFrame(results)

# ==============================
# MAIN PIPELINE
# ==============================
if __name__ == "__main__":

    conn = create_database()
    build_lookup_table(conn)

    pad_rgb_map = extract_pad_rgbs()
    results = predict_all_pads(conn, pad_rgb_map)

    print("\n===== FINAL URINE STRIP RESULTS =====")
    print(results)

    conn.close()
