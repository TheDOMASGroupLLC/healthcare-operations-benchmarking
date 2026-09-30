from datetime import datetime
import logging
from pathlib import Path

import pandas as pd

from config import PROCESSED_DIR, RAW_DIR


def import_all_sheets(excel_path: Path) -> dict[str, pd.DataFrame]:
    return pd.read_excel(excel_path, sheet_name=None)


def write_file_stats(excel_path: Path, sheets: dict[str, pd.DataFrame]) -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    output_path = PROCESSED_DIR / "import_file_stats.csv"

    rows = []
    for name, df in sheets.items():
        rows.append({
            "run_timestamp": datetime.now().isoformat(timespec="seconds"),
            "file_name": excel_path.name,
            "sheet_name": name,
            "file_size_kb": round(excel_path.stat().st_size / 1024, 2),
            "n_rows": len(df),
            "n_cols": len(df.columns),
            "columns": list(df.columns),
        })

    stats_df = pd.DataFrame(rows)
    stats_df.to_csv(
        output_path,
        mode="a" if output_path.exists() else "w",
        header=not output_path.exists(),
        index=False,
    )
    logging.info("Wrote import file stats: %s", output_path)


def load_source_workbook() -> dict[str, pd.DataFrame]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    excel_files = sorted(
        path for path in RAW_DIR.glob("*.xlsx")
        if not path.name.startswith("~$")
    )

    if not excel_files:
        raise FileNotFoundError(
            f"No Excel workbook found in {RAW_DIR}. Add the source workbook and try again."
        )
    if len(excel_files) > 1:
        names = ", ".join(path.name for path in excel_files)
        raise ValueError(
            f"Expected one source workbook in {RAW_DIR}, found {len(excel_files)}: {names}"
        )

    excel_path = excel_files[0]
    logging.info("Importing workbook: %s", excel_path.name)
    sheets = import_all_sheets(excel_path)

    required_sheets = {"Weight", "Incidents"}
    missing = required_sheets.difference(sheets)
    if missing:
        missing_names = ", ".join(sorted(missing))
        raise ValueError(
            f"Source workbook is missing required sheet(s): {missing_names}"
        )

    write_file_stats(excel_path, sheets)
    logging.info("Import complete: %s", excel_path.name)
    return sheets
