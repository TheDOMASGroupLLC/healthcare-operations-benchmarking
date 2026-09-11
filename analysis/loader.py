from pathlib import Path
import os
import pandas as pd
from config import RAW_DIR
import logging
from datetime import datetime

def import_all_sheets(excel_path):
    global all_sheets
    all_sheets = pd.read_excel(excel_path, sheet_name=None)
    return all_sheets

def file_stats(excel_path):
    file_stats = []
    output_path = Path(RAW_DIR / "import_file_stats.csv")

    # For each sheet, record file stats
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
        file_stats.append(stats)
        print(f"File stats for {excel_path.name} - {name} appended to {output_path}")
        logging.info(f"File stats for {excel_path.name} - {name} appended to {output_path}")

    # Convert to dataframe
    stats_df = pd.DataFrame(file_stats)
    
    # Append stats if file already exists, otherwise create it
    if output_path.exists():
        stats_df.to_csv(output_path, mode="a", header=False, index=False)
    else:
        stats_df.to_csv(output_path, index=False)

    # print(stats_df)



# Auto-detects Excel files in RAW_DIR and imports the files
global excel_files
excel_files = [f for f in os.listdir(RAW_DIR) if f.lower().endswith('.xlsx')]
if not excel_files:
    print(f"No Excel files found in {RAW_DIR}. Please add Excel files and try again.")
    logging.error(f"No Excel files found in {RAW_DIR}. Please add Excel files and try again.")
else:
    print(f"Excel files successfully indentified in {RAW_DIR}.")
    logging.info(f"Excel files successfully indentified in {RAW_DIR}.")

    # Import and save file stats
    for file in excel_files:
        print("BEGIN IMPORT: ", file)
        logging.info("BEGIN IMPORT: ", file)

        excel_path = RAW_DIR / file
        
        # Import all sheets
        all_sheets = import_all_sheets(excel_path)  
        # print(all_sheets)

        # Get file stats for each sheet
        file_stats(excel_path)

        print("IMPORT COMPLETE: ", file)        
        logging.info("IMPORT COMPLETE: ", file)



        