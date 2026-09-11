# helpers.py
import pandas as pd
import numpy as np
import ast
import re


def to_list_cell(x):
    # Convert one cell to a Python list (handles strings, tuples/arrays, NaN)."""
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
                return ast.literal_eval(s)  # safe parser for list-literals
            except Exception:
                pass
        return [p.strip() for p in s.split(",")] if s else []
    return [x]

def explode_aligned_columns(df: pd.DataFrame, cols) -> pd.DataFrame:
    
    # Explode multiple list-columns in lockstep. Assumes all lists have equal length.
    out = df.copy()

    # make sure columns exist
    missing = [c for c in cols if c not in out.columns]
    if missing:
        raise KeyError(f"Missing column: {missing}")

    # validate equal lengths
    lens = out[cols].stack().map(len).unstack()
    ok_mask = lens.nunique(axis=1).eq(1)
    if not ok_mask.all():
        bad_idx = out.index[~ok_mask].tolist()
        raise AssertionError(f"Found unequal list lengths in rows: {bad_idx}")

    # build list of tuples per row: [(c1_i, c2_i, ...), ...]
    pairs = [list(zip(*row)) for _, row in out[cols].iterrows()]

    
    # replace empty pairs with a single tuple of NaNs so explode keeps the row
    width = len(cols)
    pairs = [p if len(p) else [tuple([np.nan] * width)] for p in pairs]

    out["_pairs"] = pairs
    out = out.explode("_pairs", ignore_index=True)

    # vectorized split back into original columns
    if len(out) and out["_pairs"].notna().any():
        out[cols] = pd.DataFrame(out["_pairs"].tolist(), index=out.index)
    else:
        # if everything was empty and keep_empty=False, you'll have an empty frame here
        out[cols] = pd.DataFrame(columns=cols)

    return out.drop(columns="_pairs")

def _safe_col(s: str) -> str:
    # make option names safe for column headers
    return re.sub(r'[^0-9A-Za-z]+', '_', str(s)).strip('_').lower()

def multiselect_to_dummies(df: pd.DataFrame, col: str, prefix: str = None, dtype="bool") -> pd.DataFrame:
    """
    Expand a list-valued 'col' (checkbox selections) into one column per distinct option.
    - df[col] must already be a list (use to_list_cell upstream if needed)
    - dtype: 'bool' or 'int'
    Returns a copy with new dummy columns joined.
    """
    out = df.copy()
    s = out[col].explode()                      # one option per row
    d = pd.crosstab(s.index, s, dropna=True)    # rows x options
    if dtype == "bool":
        d = d > 0
    elif dtype == "int":
        d = d.astype("int64")
    else:
        raise ValueError("dtype must be 'bool' or 'int'")

    # rename columns with optional prefix and safe names
    if prefix is None:
        prefix = col
    d.columns = [f"{prefix}__{_safe_col(c)}" for c in d.columns]

    # join back; rows with empty lists will get NaN -> fill to 0/False
    out = out.join(d, how="left")
    if dtype == "bool":
        out[d.columns] = out[d.columns].fillna(False)
    else:
        out[d.columns] = out[d.columns].fillna(0)

    return out
