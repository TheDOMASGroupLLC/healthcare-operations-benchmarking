import pandas as pd
import numpy as np
import ast
import re


def to_list_cell(x):
    if isinstance(x, list):
        return x
    if isinstance(x, (tuple, np.ndarray)):
        return list(x)
    if pd.isna(x):
        return []
    if isinstance(x, str):
        s = x.strip()
        if s.startswith("[") and s.endswith("]"):
            try:
                return ast.literal_eval(s)
            except Exception:
                pass
        return [p.strip() for p in s.split(",")] if s else []
    return [x]

def explode_aligned_columns(df: pd.DataFrame, cols) -> pd.DataFrame:
    
    result = df.copy()

    missing = [c for c in cols if c not in result.columns]
    if missing:
        raise KeyError(f"Missing column: {missing}")

    lens = result[cols].stack().map(len).unstack()
    ok_mask = lens.nunique(axis=1).eq(1)
    if not ok_mask.all():
        bad_idx = result.index[~ok_mask].tolist()
        raise AssertionError(f"Found unequal list lengths in rows: {bad_idx}")

    pairs = [list(zip(*row)) for _, row in result[cols].iterrows()]

    
    width = len(cols)
    pairs = [p if len(p) else [tuple([np.nan] * width)] for p in pairs]

    result["_pairs"] = pairs
    result = result.explode("_pairs", ignore_index=True)

    if len(result) and result["_pairs"].notna().any():
        result[cols] = pd.DataFrame(result["_pairs"].tolist(), index=result.index)
    else:
        result[cols] = pd.DataFrame(columns=cols)

    return result.drop(columns="_pairs")

def _safe_col(s: str) -> str:
    return re.sub(r'[^0-9A-Za-z]+', '_', str(s)).strip('_').lower()

def multiselect_to_dummies(df: pd.DataFrame, col: str, prefix: str = None, dtype="bool") -> pd.DataFrame:
    """Expand list-valued selections into indicator columns."""
    result = df.copy()
    s = result[col].explode()
    d = pd.crosstab(s.index, s, dropna=True)
    if dtype == "bool":
        d = d > 0
    elif dtype == "int":
        d = d.astype("int64")
    else:
        raise ValueError("dtype must be 'bool' or 'int'")

    if prefix is None:
        prefix = col
    d.columns = [f"{prefix}__{_safe_col(c)}" for c in d.columns]

    result = result.join(d, how="left")
    if dtype == "bool":
        result[d.columns] = result[d.columns].fillna(False)
    else:
        result[d.columns] = result[d.columns].fillna(0)

    return result
