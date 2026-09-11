# benchmark_metrics.py
from pathlib import Path
import pandas as pd
from typing import Optional
from typing import Dict, Any
import numpy as np
from matplotlib.transforms import blended_transform_factory as btf
import matplotlib.pyplot as plt


def med_or_nan(s: pd.Series) -> float:
    # Return median of numeric series or NaN if empty.
    if s is None or len(s) == 0:
        return np.nan
    vals = pd.to_numeric(s, errors="coerce").values
    vals = vals[~np.isnan(vals)]
    return float(np.nanmedian(vals)) if len(vals) else np.nan

def _label_right_of_hline(ax, y, text, color, x_offset=1.005):
    # Place a label just outside the right edge at data-height y.
    trans = btf(ax.transAxes, ax.transData)  # x in axes coords, y in data coords
    ax.text(x_offset, y, text, transform=trans,
            ha="left", va="center", fontsize=9, color=color, clip_on=False)

def community_snapshot(df):
    d = df.copy()

    if "threshold_event" not in d.columns:
        d["threshold_event"] = pd.NA

    ev = d[d["is_event"]].copy()
    ev["abs_change"] = pd.to_numeric(ev["threshold_event"], errors="coerce").abs()
    d["dates_recorded"] = pd.to_datetime(d["dates_recorded"], errors="coerce")
    
    anchor = d["dates_recorded"].max()

    # Compute median Interval Days at resident- and community-level
    res_med = (d.groupby(["community","resident_id"])["dates_recorded"]
                 .apply(lambda s: s.diff().dt.days.median())
                 .reset_index(name="median_interval_days"))

    cadence = (res_med.groupby("community")
               .agg(median_interval_days=("median_interval_days","median"),
                    residents_sparse=("median_interval_days", lambda x: (x > 30).mean() * 100)))

    base = d.groupby("community").agg(
        n_residents=("resident_id","nunique"),
        n_records=("dates_recorded","size")
    )

    ev_agg = (ev.groupby("community").agg(
        n_events=("threshold_event","size"),
        residents_with_event=("resident_id","nunique"),
        median_abs_change=("abs_change","median"),
        share_loss=("event_direction", lambda s: (s == "loss").mean() * 100),
        share_gain=("event_direction", lambda s: (s == "gain").mean() * 100),
        top_magnitude=("abs_change","max"),
        last_event_date=("dates_recorded","max"),
    ) if not ev.empty else pd.DataFrame(columns=[
        "n_events","residents_with_event","median_abs_change",
        "share_loss","share_gain","top_magnitude","last_event_date"
    ]))

    out = (base.join(ev_agg, how="left")
            .fillna({"n_events":0, "residents_with_event":0,
                        "median_abs_change":np.nan, "share_loss":0,
                        "share_gain":0, "top_magnitude":np.nan})
            .infer_objects(copy=False)
            .join(cadence, how="left")
            .assign(
                pct_residents_with_event=lambda x: (x["residents_with_event"]/x["n_residents"]*100).round(1),
                events_per_resident=lambda x: x["n_events"] / x["n_residents"],
                net_dir_imbalance=lambda x: (x["share_gain"] - x["share_loss"]).round(1)
            ))

    out = out.reset_index()

    # Compute days_since_last_event safely
    if pd.notna(anchor) and "last_event_date" in out.columns:
        out["days_since_last_event"] = (anchor - out["last_event_date"]).dt.days
    else:
        out["days_since_last_event"] = pd.NA

    out["community_id"] = out["community"]
    return out

def weekly_event_rates(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["dates_recorded"] = pd.to_datetime(d["dates_recorded"], errors="coerce")

    weeks = d["dates_recorded"].dt.to_period("W")
    d["week"] = weeks.dt.start_time
    d = d.dropna(subset=["week"])

    weekly_res = d.groupby(["community","week"])["resident_id"].nunique().rename("n_residents_week")
    weekly_evt = d[d["is_event"]].groupby(["community","week"])["is_event"].size().rename("n_events_week")

    out = (weekly_res.to_frame()
           .join(weekly_evt, how="left").fillna({"n_events_week":0})
           .assign(resident_weeks=lambda x: x["n_residents_week"],
                   events_per_100_resident_weeks=lambda x: (x["n_events_week"]/x["resident_weeks"])*100)
           .reset_index())
    return out

def _compute_benchmark_series(df: pd.DataFrame):
    """
    Returns dict of the four benchmark Series indexed by community.
      v1: % residents with ≥1 event
      v2: events per 100 residents
      v3_true: median(days between weigh-ins) at resident level, then median across residents in community
      v3_plot: v3_true with NaNs filled to 0 for plotting
      v4: % residents who ever have >30-day interval
    """

    df = df.loc[:, ["community", "resident_id", "date_diff", "is_event"]].copy()

    if df["community"].dtype != "category":
        df["community"] = df["community"].astype("category")
    if df["resident_id"].dtype != "category":
        df["resident_id"] = df["resident_id"].astype("category")

    # Make sure these are numeric/bool
    df["date_diff"] = pd.to_numeric(df["date_diff"], errors="coerce")
    df["is_event"]  = df["is_event"].astype(bool)

    # Stable community index (all communities present in this slice)
    communities_idx = df["community"].cat.categories
    # Resident census per community
    census = df.groupby("community", observed=True)["resident_id"].nunique()

    # % residents with ≥1 event
    any_event_by_res = (
        df.groupby(["community", "resident_id"], observed=True)["is_event"]
          .any()
    )  # MultiIndex (community,resident_id)
    v1 = (any_event_by_res.groupby(level=0).mean()).reindex(communities_idx, fill_value=0) * 100

    # Events per 100 residents
    event_counts = df.loc[df["is_event"]].groupby("community", observed=True).size()
    denom = census.reindex(communities_idx).replace(0, pd.NA)
    v2 = (event_counts.reindex(communities_idx, fill_value=0) / denom.astype("Float64") * 100).fillna(0)

    # Median days between per resident
    res_meds = (
        df.loc[df["date_diff"].notna()]
          .groupby(["community", "resident_id"], observed=True)["date_diff"]
          .median()
    )  # MultiIndex -> float
    v3_true = res_meds.groupby(level=0).median().reindex(communities_idx)
    v3_plot = v3_true.fillna(0)

    # % residents with >30 days between weigh-ins (vectorized any over boolean)
    gt30_by_res = (
        df["date_diff"].gt(30)
          .groupby([df["community"], df["resident_id"]], observed=True)
          .any()
    )
    v4 = (gt30_by_res.groupby(level=0).mean()).reindex(communities_idx, fill_value=0) * 100

    return {"v1": v1.astype(float),
            "v2": v2.astype(float),
            "v3_true": v3_true.astype(float),
            "v3_plot": v3_plot.astype(float),
            "v4": v4.astype(float)}

def create_benchmark_summary_and_visuals(
    weights_df: pd.DataFrame,
    out_dir: Path,
    timestamp: str,
    timeframe_label: str = ""
) -> pd.DataFrame:
    """
    Benchmarks (one visual each), computed from resident-level data.

    For WEIGHTS:
      1) % residents with ≥1 event
      2) Events per 100 residents
      3) Median days between events  (resident-median → community-median)
      4) % residents with >30 days between events

    For INCIDENTS (falls), we now report GLOBAL metrics:
      1) % of fallers with a repeat fall <30 days (global among fallers)
      2) Falls per 100 residents (global)
      3) Median days between falls (resident-median → global median)

    timeframe_label (optional): appears in titles/CSV (e.g., "2024Q1" or "2024Q1–2024Q2").
    """

    out_dir.mkdir(parents=True, exist_ok=True)
    d = weights_df.copy()

    # Compute per-community metrics (used for weights, may be partially reused)
    S = _compute_benchmark_series(d)

    # auto-detect kind from output directory
    kind = "incidents" if "incident" in str(out_dir).lower() else "weights"

    # ----- INCIDENTS: compute GLOBAL falls-only metrics -----
    global_metrics = {}
    if kind == "incidents" and "is_fall" in d.columns:
        # Restrict to falls
        falls = d[d["is_fall"]].copy()
        total_residents = d["resident_id"].nunique()
        total_falls = len(falls)

        # % of fallers with repeat fall <30 days (global)

        if "fall_date_diff" in falls.columns:
            dd = pd.to_numeric(falls["fall_date_diff"], errors="coerce")
        else:
            dd = pd.to_numeric(falls["date_diff"], errors="coerce")

        falls = falls.assign(_gap_days=dd)

        # Min gap per resident
        gap_by_res = (
            falls.dropna(subset=["_gap_days"])
                 .groupby("resident_id")["_gap_days"]
                 .min()
        )
        num_fallers = falls["resident_id"].nunique()
        num_repeat = (gap_by_res <= 30).sum()

        pct_repeat_global = (num_repeat / num_fallers * 100.0) if num_fallers > 0 else np.nan

        # Falls per 100 residents (global)
        falls_per_100_global = (
            total_falls / total_residents * 100.0
            if total_residents > 0 else np.nan
        )

        # Median days between falls (resident-median → global median)
        falls = falls.sort_values(["resident_id", "dates_recorded"])
        med_gap_by_resident = (
            falls.groupby("resident_id")["dates_recorded"]
                 .apply(lambda s: s.diff().dt.days.median())
        )
        median_days_between_falls_global = med_gap_by_resident.median()

        global_metrics = {
            "v1": pct_repeat_global,
            "v2": falls_per_100_global,
            "v3_true": median_days_between_falls_global,
        }

    METRIC_ROWS = {
        "weights": [
            ("% Residents with ≥1 Event", "v1"),
            ("Events per 100 Residents", "v2"),
            ("Median Days Between Weigh-Ins (resident-median → community-median)", "v3_true"),
            ("% Residents with >30 Days Between Weigh-Ins", "v4"),
        ],
        "incidents": [
            ("% Residents with Repeat Fall <30 Days (Global Among Fallers)", "v1"),
            ("Falls per 100 Residents (Global)", "v2"),
            ("Median Days Between Falls (resident-median → global median)", "v3_true"),
        ],
    }

    rows = []

    overall_col = "Overall"

    for label, code in METRIC_ROWS[kind]:
        if kind == "incidents":
            # Use the GLOBAL falls metrics computed above
            val = global_metrics.get(code, np.nan)
        else:
            s = S[code]
            val = med_or_nan(s)

        rows.append({
            "Metric": label,
            overall_col: None if np.isnan(val) else round(val, 1),
            "Timeframe": timeframe_label,
        })

    summary = pd.DataFrame(rows)
    out_path = out_dir / f"benchmarks_summary_{timestamp}.csv"
    summary.to_csv(out_path, index=False)
    print(f"[summary] Wrote {kind} benchmark summary → {out_path}")

    return summary

def _pct_residents_with_repeat_fall_30d(df):
    """
    For each community, % of residents with ≥1 repeat fall <30 days,
    among residents who had at least one fall in this slice.
    """
    d = df.copy()
    if "is_fall" not in d.columns:
        return pd.Series(dtype="float64")

    if "fall_date_diff" in d.columns:
        dd = pd.to_numeric(d["fall_date_diff"], errors="coerce")
    else:
        dd = pd.to_numeric(d["date_diff"], errors="coerce")

    d["is_repeat_fall_30d"] = d.get("is_fall", False) & dd.le(30)

    # per-resident flags
    has_fall = (
        d.groupby(["community", "resident_id"], observed=True)["is_fall"]
          .any()
    )
    repeat_30 = (
        d.groupby(["community", "resident_id"], observed=True)["is_repeat_fall_30d"]
          .any()
    )

    # aggregate to community-level %
    has_fall_int = has_fall.astype(int)
    repeat_int   = repeat_30.astype(int)

    denom = has_fall_int.groupby(level=0).sum().astype("Float64")
    num   = repeat_int.groupby(level=0).sum().astype("Float64")

    pct = (num / denom.replace(0, pd.NA) * 100.0).fillna(0.0)
    pct.name = "pct_residents_with_repeat_fall_30d"
    return pct


def create_quarter_comparison_visuals(
    df_all: pd.DataFrame,
    qA: str,
    qB: str,
    out_dir: Path,
    timestamp: str
):
    """
    Produce combined charts for each benchmark metric.

    df_all must include: community, resident_id, date_diff, is_event, quarter
    """

    out_dir.mkdir(parents=True, exist_ok=True)

    # Slice quarters
    A = df_all.loc[df_all["quarter"] == qA].copy()
    B = df_all.loc[df_all["quarter"] == qB].copy()

    if A.empty or B.empty:
        print(f"[skip] Missing data for {qA} or {qB}")
        return

    # Per-quarter metrics
    SA = _compute_benchmark_series(A)
    SB = _compute_benchmark_series(B)

    # Pooled across the two quarters (for overall medians)
    AB = df_all.loc[df_all["quarter"].isin([qA, qB])].copy()
    S_pool = _compute_benchmark_series(AB)

    # Infer kind of event from output path
    kind = "incidents" if "incident" in str(out_dir).lower() else "weights"
    global_incidents_metrics: dict[str, float] = {}

    if kind == "incidents" and "is_fall" in A.columns:
        SA["v1"] = _pct_residents_with_repeat_fall_30d(A)
        SB["v1"] = _pct_residents_with_repeat_fall_30d(B)
        S_pool["v1"] = _pct_residents_with_repeat_fall_30d(AB)

    # Per-kind, per-metric chart parameters
    PARAMS: Dict[str, Dict[str, Dict[str, Any]]] = {
        "weights": {
            "v1":      {"target_top": 10.0, "target_bottom": 0.0,  "show_band": True,  "highlight_abs": 20.0},
            "v2":      {"target_top": 10.0, "target_bottom": 0.0,  "show_band": True,  "highlight_abs": 20.0},
            # v3_true is in days, not %
            "v3_true": {"target_top": 30.0, "target_bottom": None, "show_band": False, "highlight_abs": 5.0},
            "v4":      {"target_top": 50.0, "target_bottom": 0.0,  "show_band": True,  "highlight_abs": 0.0},
        },
        "incidents": {
            "v1":      {"target_top": 20.0, "target_bottom": 0.0,  "show_band": True,  "highlight_abs": 20.0},
            "v2":      {"target_top": 0.0, "target_bottom": 0.0,  "show_band": True,  "highlight_abs": 15.0},
            # v3_true (days between incidents)
            "v3_true": {"target_top": 0.0, "target_bottom": None, "show_band": False, "highlight_abs": 0.0},
            # no v4 by default for incidents
        },
    }

    TITLES = {
        "weights": {
            "v1": "% Residents with ≥1 Weight-Change Event by Community",
            "v2": "Weight-Change Events per 100 Residents by Community",
            "v3_true": "Median Days Between Weigh-Ins by Community",
            "v4": "% Residents with >30 Days Between Weigh-Ins by Community",
        },
        "incidents": {
            "v1": "% Residents with Repeat Fall <30 Days by Community",
            "v2": "Incidents per 100 Residents by Community",
            "v3_true": "Median Days Between Incidents by Community",

        },
    }

    IS_PERCENT = {
        "weights": {
            "v1": True,
            "v2": False,
            "v3_true": False,   # ← v3 is in days
            "v4": True,
        },
        "incidents": {
            "v1": True,
            "v2": False,
            "v3_true": False,   # ← v3 is in days
        },
    }

    # Metric keys and filename stubs we want to attempt
    metric_specs = [
        ("v1",      "combo_v1"),
        ("v2",      "combo_v2"),
        ("v3_true", "combo_v3"),
        ("v4",      "combo_v4"),  # will be skipped for incidents
    ]

    for key, fname_stub in metric_specs:
        # Skip metrics that don't exist for this kind (e.g., v4 for incidents)
        if key not in SA or key not in SB or key not in S_pool:
            continue
        if key not in TITLES.get(kind, {}) or key not in IS_PERCENT.get(kind, {}):
            continue

        params = PARAMS.get(kind, {}).get(
            key,
            {"target_top": None, "target_bottom": None,
             "show_band": False, "highlight_abs": 0.0},
        )

        out_path = out_dir / f"{fname_stub}_{timestamp}_{qA}_vs_{qB}.png"

        # Use global falls metrics for the top median line when plotting incidents
        # Hard-code incident medians for the top line (for now)
        if kind == "incidents":
            if key == "v1":
                # % Residents with Repeat Fall <30 Days
                top_override = 44.5
            elif key == "v2":
                # Falls per 100 Residents
                top_override = 222.0
            elif key == "v3_true":
                # Median Days Between Falls
                top_override = 22.2
            else:
                top_override = None
        else:
            top_override = None

        combined_metric_bars_and_delta(
            SA[key],
            SB[key],
            qA,
            qB,
            out_path,
            metric_name=TITLES[kind][key],
            is_percent_metric=IS_PERCENT[kind][key],
            sort_by_abs=True,
            target_top=params["target_top"],
            target_bottom=params["target_bottom"],
            show_band=params["show_band"],
            highlight_abs_threshold=params["highlight_abs"],
            show_top_median=True,
            show_bottom_median=True,
            overall_series_for_top_median=S_pool[key],
            top_median_override=top_override,
        )

    print(f"[OK] Saved combined quarter comparison charts to: {out_dir}")

def combined_metric_bars_and_delta(
    base_series: pd.Series,
    new_series: pd.Series,
    qA: str, qB: str,
    out_path: Path,
    *,
    metric_name: str,
    is_percent_metric: bool,
    sort_by_abs: bool = True,
    target_top: float = None,
    target_bottom: float = None,
    show_band: bool = True,
    highlight_abs_threshold: float = 20.0,
    show_top_median: bool = True,
    show_bottom_median: bool = True,
    top_median_override: Optional[float] = None,
    bottom_median_override: Optional[float] = None,
    overall_series_for_top_median: Optional[pd.Series] = None,
):

    # compute change and assign labels
    if is_percent_metric:
        delta = _sort_pct_change(base_series, new_series)     # Δ% relative to baseline
        y_label_top  = "%"
        delta_label  = "Δ % (relative to baseline)"
    else:
        delta = _abs_change(base_series, new_series)           # Δ absolute (days)
        y_label_top  = "Days"
        delta_label  = "Δ (absolute)"

        # Override for “per 100 residents” metrics
        if "per 100 Residents" in metric_name:
            y_label_top = "Events per 100 Residents"
            delta_label = "Δ (per 100 residents)"

    # --- order and align ---
    all_idx   = base_series.index.union(new_series.index)
    order_src = delta.reindex(all_idx)

    nan_idx     = order_src[order_src.isna()].index
    ordered_idx = order_src.dropna().abs().sort_values(ascending=False).index.append(nan_idx)
    idx = pd.Index(ordered_idx.unique())

    A = base_series.reindex(idx).fillna(0.0)
    B = new_series.reindex(idx).fillna(0.0)
    D = delta.reindex(idx)

    x = np.arange(len(idx)); w = 0.42
    fig, (ax_top, ax_bot) = plt.subplots(
        nrows=2, ncols=1, sharex=True, figsize=(14,8), dpi=150,
        gridspec_kw={'hspace': 0.25}   # a touch more separation
    )


    # Top: paired bars
    ax_top.bar(x - w/2, A.values, width=w, label=qA)
    ax_top.bar(x + w/2, B.values, width=w, label=qB)
    ax_top.set_title(f"{metric_name} ({qA} vs {qB})")
    ax_top.set_ylabel(y_label_top)
    
    # median & target (top)
    guide_h, guide_l = [], []
    text_x = (len(idx) - 0.25) if len(idx) else 0
    
    # TOP median selection
    if show_top_median and len(idx):
        if top_median_override is not None and np.isfinite(top_median_override):
            m_top = float(top_median_override)
        elif overall_series_for_top_median is not None:
            # use pooled per-community values aligned to idx, exclude NaNs from the calc
            pooled = overall_series_for_top_median.reindex(idx)
            m_top = float(np.nanmedian(pooled.dropna().values)) if pooled.notna().any() else np.nan
        else:
            # fallback: median across the two quarter series combined (your current behavior)
            valid_top = pd.concat([A, B]).dropna()
            m_top = float(np.nanmedian(valid_top.values)) if len(valid_top) else np.nan

        if np.isfinite(m_top):
            ax_top.axhline(m_top, color="gray", linestyle="--", linewidth=1.2, alpha=0.9)
            _label_right_of_hline(ax_top, m_top, f"Median = {m_top:.1f}{y_label_top}", color="gray")
        
    if target_top is not None and np.isfinite(target_top):
        ax_top.axhline(target_top, color="red", linestyle="--", linewidth=1.2, alpha=0.85)
        _label_right_of_hline(ax_top, target_top, f"Target = {target_top:.1f}{y_label_top}", color="red")

    if guide_h:
        h,l = ax_top.get_legend_handles_labels()
        ax_top.legend(h + guide_h, l + guide_l, ncol=1, loc="center left", bbox_to_anchor=(1.02, 0.5))

    # Bottom: Δ bars (keep NaNs)
    dvals = D.values.astype(float)
    nanmask = ~np.isfinite(dvals)
    plot_vals = np.where(nanmask, 0.0, dvals)

    if is_percent_metric:
        colors = np.where(nanmask, "lightgray", np.where(plot_vals >= 0, "tab:red", "tab:blue"))
    else:
        colors = np.where(nanmask, "lightgray", np.where(plot_vals >= 0, "tab:orange", "tab:purple"))

    # Plot all communities
    xpos = np.arange(len(idx))
    ax_bot.bar(xpos, plot_vals, color=colors)

    # Band anchored to target_bottom
    if target_bottom is not None and np.isfinite(target_bottom):
        ax_bot.axhline(target_bottom, color="red", linestyle="--", linewidth=1.2, alpha=0.85)
        if show_band:
            ax_bot.axhspan(target_bottom - highlight_abs_threshold,
                        target_bottom + highlight_abs_threshold,
                        color="lightgray", alpha=0.2, zorder=0)
        _label_right_of_hline(ax_bot, target_bottom, f"Target = {target_bottom:.1f}{y_label_top}", color="red")
    
    # Annotate, skip NaNs
    for xi, val, is_na in zip(xpos, plot_vals, nanmask):
        if is_na:
            ax_bot.text(xi, 0, "NA", ha="center", va="bottom", fontsize=7, color="gray")
            continue
        thresh_ref = target_bottom if (target_bottom is not None and np.isfinite(target_bottom)) else 0.0
        if np.isfinite(val) and abs(val - thresh_ref) >= highlight_abs_threshold:
            ax_bot.text(
                xi, val, f"{val:+.0f}%" if is_percent_metric else f"{val:+.0f}",
                ha="center", va=("bottom" if val >= thresh_ref else "top"), fontsize=8
            )

    # median Δ (bottom) — compute from real (non-NaN) deltas
    if show_bottom_median:
        if bottom_median_override is not None and np.isfinite(bottom_median_override):
            m_delta = float(bottom_median_override)
        else:
            valid_bottom = D[~D.isna()].astype(float)
            m_delta = float(np.nanmedian(valid_bottom.values)) if not valid_bottom.empty else np.nan

        if np.isfinite(m_delta):
            ax_bot.axhline(m_delta, color="gray", linestyle="--", linewidth=1.2, alpha=0.9)
            unit_bottom = "%" if is_percent_metric else "Days"
            _label_right_of_hline(ax_bot, m_delta, f"Median = {m_delta:.1f}{unit_bottom}", color="gray")

    # Show x-axis
    ax_top.set_xticks(x)
    ax_top.set_xticklabels(idx, rotation=45, ha="right", fontsize=8)

    ax_bot.set_xticks(x)
    ax_bot.set_xticklabels(idx, rotation=45, ha="right", fontsize=8)

    # Enable bottom tick marks and labels on both plots
    ax_top.tick_params(axis="x", bottom=True, labelbottom=True)
    ax_bot.tick_params(axis="x", bottom=True, labelbottom=True)



    # Bottom axis & title
    ax_bot.set_ylabel(delta_label)
    ax_bot.set_title(f"Δ {metric_name} ({qA} → {qB})")

    # tighten layout
    fig.tight_layout(rect=[0, 0.05, 1, 0.95])
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)  # <-- close once


def _sort_pct_change(series_a, series_b):
    """Compute (b - a) / a * 100 safely, avoiding divide-by-zero and infinities."""
    result = (series_b - series_a) / series_a.replace(0, np.nan) * 100
    return result.replace([np.inf, -np.inf], np.nan)

def _abs_change(series_a: pd.Series, series_b: pd.Series) -> pd.Series:
    """Compute absolute change (b - a), preserving NaNs where a is NaN."""
    return (series_b - series_a).astype(float)
