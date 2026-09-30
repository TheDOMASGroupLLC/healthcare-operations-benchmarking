from datetime import datetime
import logging
import os
from pathlib import Path

import pandas as pd

from config import RAW_DIR

def import_all_sheets(excel_path):
    global all_sheets
    all_sheets = pd.read_excel(excel_path, sheet_name=None)
    return all_sheets

def file_stats(excel_path):
    sheet_stats = []
    output_path = Path(RAW_DIR / "import_file_stats.csv")

    for name, df in all_sheets.items():
        stats = {
            "run_timestamp": datetime.now().isoformat(timespec="seconds"),
            "file_name": excel_path.name,
            "sheet_name": name,
            "file_size_kb": round(excel_path.stat().st_size / 1024, 2),
            "n_rows": len(df),
            "n_cols": len(df.columns),
            "columns": list(df.columns)
        }
        sheet_stats.append(stats)
        print(f"Wrote file stats for {excel_path.name} / {name}: {output_path}")
        logging.info("Wrote file stats for %s / %s: %s", excel_path.name, name, output_path)

    stats_df = pd.DataFrame(sheet_stats)
    
    if output_path.exists():
        stats_df.to_csv(output_path, mode="a", header=False, index=False)
    else:
        stats_df.to_csv(output_path, index=False)




excel_files = [f for f in os.listdir(RAW_DIR) if f.lower().endswith('.xlsx')]
if not excel_files:
    print(f"No Excel files found in {RAW_DIR}. Please add Excel files and try again.")
    logging.error(f"No Excel files found in {RAW_DIR}. Please add Excel files and try again.")
else:
    print(f"Excel files identified in {RAW_DIR}.")
    logging.info("Excel files identified in %s.", RAW_DIR)

    for filename in excel_files:
        print(f"Importing workbook: {filename}")
        logging.info("Importing workbook: %s", filename)

        excel_path = RAW_DIR / filename
        
        all_sheets = import_all_sheets(excel_path)  

        file_stats(excel_path)

        print(f"Import complete: {filename}")        
        logging.info("Import complete: %s", filename)



        