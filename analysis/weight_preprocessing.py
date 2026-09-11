# comment Imports used for data prep and event logic
import numpy as np
import pandas as pd
from helpers import to_list_cell, explode_aligned_columns


# Past-only threshold detection
def add_threshold_within_window(df, max_days, threshold_pct, prefix, add_max_abs_30d: bool = False):
    df = df.copy()

    pct_col   = f"pct_{prefix}_thresh"
    date_col  = f"date_{prefix}_thresh"
    refwt_col = f"ref_wt_{prefix}"
    days_col  = f"days_{prefix}_thresh"
    dir_col   = f"dir_{prefix}"
    maxabs_col = "max_abs_change_30d"

    df[[pct_col, refwt_col, days_col]] = np.nan
    df[date_col] = pd.NaT
    df[dir_col] = pd.Series(pd.NA, index=df.index, dtype="string")
    if add_max_abs_30d and maxabs_col not in df:
        df[maxabs_col] = np.nan

    for _, g in df.groupby("resident_id"):
        idx   = g.index.to_numpy()
        dates = pd.to_datetime(g["dates_recorded"], errors="coerce").to_numpy(dtype="datetime64[ns]")
        wts   = g["weight_lbs"].to_numpy(dtype="float64")

        gp_pct   = np.full(len(g), np.nan, float)
        gp_date  = np.array([pd.NaT]*len(g), dtype=object)
        gp_refwt = np.full(len(g), np.nan, float)
        gp_days  = np.full(len(g), np.nan, float)
        gp_dir   = np.array([pd.NA]*len(g), dtype=object)
        gp_maxabs = np.full(len(g), np.nan, float) if add_max_abs_30d else None

        for i, (d, w) in enumerate(zip(dates, wts)):
            if np.isnat(d) or pd.isna(w):
                continue

            diffs   = d - dates
            inwin   = (diffs > np.timedelta64(0, "D")) & (diffs <= np.timedelta64(max_days, "D"))
            cidx    = np.where(inwin)[0]
            if cidx.size:
                refw = wts[cidx]
                ok   = (~np.isnan(refw)) & (refw != 0)
                if ok.any():
                    refw   = refw[ok]
                    refd   = dates[cidx][ok]
                    pcts   = (w - refw) / refw * 100.0
                    trig   = np.abs(pcts) >= threshold_pct
                    if trig.any():
                        deltas = (d - refd)[trig]
                        k      = int(np.argmin(deltas))
                        gp_pct[i]   = float(pcts[trig][k])
                        gp_date[i]  = pd.to_datetime(refd[trig][k])
                        gp_refwt[i] = float(refw[trig][k])
                        gp_days[i]  = float(deltas[k] / np.timedelta64(1, "D"))
                        gp_dir[i]   = "loss" if gp_pct[i] < 0 else "gain"

            if add_max_abs_30d:
                w30   = (diffs > np.timedelta64(0, "D")) & (diffs <= np.timedelta64(30, "D"))
                c30   = np.where(w30)[0]
                if c30.size:
                    refw30 = wts[c30]
                    ok30   = (~np.isnan(refw30)) & (refw30 != 0)
                    if ok30.any():
                        p30 = np.abs((w - refw30[ok30]) / refw30[ok30] * 100.0)
                        if p30.size:
                            gp_maxabs[i] = float(np.nanmax(p30))

        df.loc[idx, pct_col]   = gp_pct
        df.loc[idx, date_col]  = pd.to_datetime(gp_date)
        df.loc[idx, refwt_col] = gp_refwt
        df.loc[idx, days_col]  = gp_days
        df.loc[idx, dir_col]   = gp_dir
        if add_max_abs_30d:
            df.loc[idx, maxabs_col] = gp_maxabs

    return df

# Unified event columns
def add_unified_event_column(df):
    d = df.copy()
    v30 = d["pct_30d_thresh"]
    v180 = d["pct_180d_thresh"]
    m30 = v30.abs() >= 5
    m180 = v180.abs() >= 10
    both = m30 & m180

    evt = pd.Series(np.nan, index=d.index, dtype="float64")
    evt[both] = np.where(v30[both].abs() >= v180[both].abs(), v30[both], v180[both])
    evt[m30 & ~m180] = v30[m30 & ~m180]
    evt[m180 & ~m30] = v180[m180 & ~m30]

    d["threshold_event"] = evt
    d["is_event"] = d["threshold_event"].notna()
    d["event_direction"] = np.where(
        d["threshold_event"] >= 0, "gain",
        np.where(d["threshold_event"] < 0, "loss", pd.NA)
    )
    return d

# comment Suppress events < min_gap apart
def apply_min_gap(df, days_col, pct_col, min_gap: int = 7):
    df = df.copy()
    for _, g in df.groupby("resident_id"):
        idx = g.index
        mask = (g[days_col] < min_gap) & (g[pct_col].notna())
        df.loc[idx[mask], [pct_col, days_col]] = np.nan
    return df

# Prepare analysis table from raw Weight sheet (unchanged logic)
def analysis_prep(df):
    df = df.copy()
    for col in ["dates_recorded", "weight_lbs"]:
        df[col] = df[col].apply(to_list_cell)
    df = explode_aligned_columns(df, ["dates_recorded", "weight_lbs"])

    df["dates_recorded"] = pd.to_datetime(df["dates_recorded"], errors="coerce").dt.tz_localize(None)
    df["weight_lbs"] = pd.to_numeric(df["weight_lbs"], errors="coerce")

    df = (df
          .sort_values(["resident_id", "dates_recorded"], ascending=[True, False])
          .assign(date_only=lambda d: d["dates_recorded"].dt.date)
          .drop_duplicates(subset=["resident_id", "date_only"], keep="last")
          .drop(columns="date_only")
          .reset_index(drop=True)
          .query("70 <= weight_lbs <= 450"))

    df = df.sort_values(["resident_id", "dates_recorded"]).reset_index(drop=True)

    df["percent_change"] = df.groupby("resident_id")["weight_lbs"].pct_change() * 100.0
    df["date_diff"] = df.groupby("resident_id")["dates_recorded"].diff().dt.days

    df = add_threshold_within_window(df, max_days=40, threshold_pct=5.0, prefix="30d", add_max_abs_30d=True)
    df = add_threshold_within_window(df, max_days=200, threshold_pct=10.0, prefix="180d")

    df = apply_min_gap(df, "days_30d_thresh", "pct_30d_thresh", min_gap=7)
    df = apply_min_gap(df, "days_180d_thresh", "pct_180d_thresh", min_gap=7)

    df = add_unified_event_column(df)
    return df
