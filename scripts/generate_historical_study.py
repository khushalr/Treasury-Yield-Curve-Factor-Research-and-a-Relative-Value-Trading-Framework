#!/usr/bin/env python3
"""Historical fitted-yield research; NEVER historical executable investment returns."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from src.data.fed_curve_loader import load_fed_curve_data
from src.research.backtest import BacktestConfig, run_synthetic_backtest

TENORS = [1, 2, 3, 5, 7, 10, 20, 30]
PERIODS = [
    ("1990–1999", "1990-01-01", "1999-12-31"),
    ("2000–2007", "2000-01-01", "2007-12-31"),
    ("2008–2009", "2008-01-01", "2009-12-31"),
    ("2010–2019", "2010-01-01", "2019-12-31"),
    ("2020–2021", "2020-01-01", "2021-12-31"),
    ("2022 onward", "2022-01-01", "2099-12-31"),
]
COSTS = (0.0, 0.25, 0.5, 1.0, 2.0)


def run_study(path: Path, start: str = "1990-01-01") -> dict:
    full = load_fed_curve_data(path, TENORS)
    curve = full.loc[start:].dropna(subset=TENORS)
    if len(curve) < 800 or not curve.index.is_monotonic_increasing:
        raise ValueError("Not enough complete, chronologically sorted observations")
    changes = curve.diff().dropna()
    pca = PCA(n_components=3).fit(changes.values)
    loadings = pd.DataFrame(pca.components_.T, index=TENORS, columns=["PC1", "PC2", "PC3"])
    config = BacktestConfig(
        pca_window=252, z_window=126, entry_z=2.0,
        exit_z=0.5, cost_yield_bp=0.0, holdout_fraction=0.30
    )
    sim = run_synthetic_backtest(curve[[5, 7, 10]], config)
    daily = sim.daily.loc[sim.daily["eligible"]].copy()
    if daily.empty:
        raise ValueError("No post-warmup observations")
    daily["active"] = daily["executed_gross_dv01"] > 1e-9
    daily["net_025"] = daily["gross_pnl_per_unit_dv01"] - 0.25*daily["turnover_unit_dv01"]
    daily["net_100"] = daily["gross_pnl_per_unit_dv01"] - daily["turnover_unit_dv01"]

    eras = []
    for name, a, b in PERIODS:
        ch, trade = changes.loc[a:b], daily.loc[a:b]
        if ch.empty:
            continue
        era_pca = PCA(n_components=3).fit(ch.values)
        eras.append({
            "period": name, "pca_observations": len(ch),
            "pc1_pct": float(era_pca.explained_variance_ratio_[0]*100),
            "first3_pct": float(era_pca.explained_variance_ratio_[:3].sum()*100),
            "strategy_observations": len(trade),
            "active_pct": float(100*trade["active"].mean()) if len(trade) else 0.0,
            "entries": int(trade["new_entry"].sum()),
            "gross_sensitivity": float(trade["gross_pnl_per_unit_dv01"].sum()),
            "net_at_025": float(trade["net_025"].sum()),
            "net_at_100": float(trade["net_100"].sum()),
        })

    gross = daily["gross_pnl_per_unit_dv01"]
    turnover = daily["turnover_unit_dv01"]
    cost_rows = [{
        "assumed_yield_bp_cost": c, "gross_sensitivity": float(gross.sum()),
        "cost_sensitivity": float((c*turnover).sum()),
        "net_sensitivity": float((gross-c*turnover).sum())
    } for c in COSTS]
    metadata = {
        "csv_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "source_rows": len(full), "full_source_latest": str(full.index.max().date()),
        "analysis_first": str(curve.index.min().date()),
        "analysis_last": str(curve.index.max().date()),
        "complete_8_tenor_rows": len(curve), "changes": len(changes),
        "eligible_strategy_rows": len(daily),
        "active_rows": int(daily["active"].sum()),
        "entries": int(daily["new_entry"].sum()),
        "input_curve_tenors_years": TENORS,
        "strategy_tenors_years": [5,7,10],
        "strategy_pca_window": 252,
        "strategy_z_window": 126,
        "entry_z": 2.0, "exit_z": 0.5,
        "gross_risk_unit": "one hypothetical USD/bp gross DV01",
        "point_in_time_release_safe": False,
        "tradable_return_or_pnl": False,
    }
    return {
        "meta": metadata, "explained_variance": pca.explained_variance_ratio_.tolist(),
        "eras": eras, "costs": cost_rows,
        "loadings": loadings, "curve": curve, "daily": daily,
    }


def charts(result: dict, target: Path) -> list[Path]:
    out = target / "figures"
    out.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 9.5,
        "axes.spines.right": False, "axes.spines.top": False
    })
    paths = []

    def save(name: str) -> None:
        p = out / name
        plt.savefig(p, dpi=180, facecolor="white", bbox_inches="tight")
        plt.close()
        paths.append(p)

    curve, load, daily = result["curve"], result["loadings"], result["daily"]
    fig, ax = plt.subplots(figsize=(9.5,4))
    for tenor in (2,5,7,10,30):
        ax.plot(curve.index,curve[tenor],label=f"{tenor}Y",lw=1.1)
    ax.set(title="Federal Reserve nominal fitted-yield history",ylabel="Yield (%)")
    ax.legend(ncol=5,frameon=False)
    save("01_fitted_yields.png")

    fig, ax = plt.subplots(figsize=(9.5,4))
    for col in load:
        ax.plot(load.index,load[col],marker="o",label=col)
    ax.axhline(0,color="gray",lw=.7)
    ax.set(xlabel="Maturity (years)",ylabel="Loading (arbitrary sign)",
           title="Descriptive full-sample PCA of daily changes")
    ax.set_xticks(TENORS);ax.legend(frameon=False)
    save("02_pca_loadings.png")

    eras=result["eras"]; xs=np.arange(len(eras))
    fig, ax = plt.subplots(figsize=(9.5,4))
    ax.bar(xs-.18,[e["pc1_pct"] for e in eras],.35,label="PC1")
    ax.bar(xs+.18,[e["first3_pct"] for e in eras],.35,label="PC1+2+3")
    ax.set_xticks(xs,[e["period"] for e in eras],rotation=20,ha="right")
    ax.set_ylim(0,105);ax.set(ylabel="Explained variance (%)",title="Factor shares by predefined calendar period")
    ax.legend(frameon=False)
    save("03_explained_variance_by_era.png")

    gross=daily["gross_pnl_per_unit_dv01"]
    turnover=daily["turnover_unit_dv01"]
    fig, ax=plt.subplots(figsize=(9.5,4))
    ax.plot(daily.index,gross.cumsum(),label="No modeled costs",lw=1.4)
    ax.plot(daily.index,(gross-0.5*turnover).cumsum(),label="0.50 bp cost/turnover",lw=1.4)
    ax.axhline(0,color="gray",lw=.7)
    ax.set(ylabel="Modeled USD at $1/bp gross DV01",title="Retrospective synthetic sensitivity — NOT actual investment returns")
    ax.legend(frameon=False)
    save("04_synthetic_pnl_sensitivity.png")

    costs=result["costs"]
    fig, ax=plt.subplots(figsize=(9.5,4))
    ax.plot([x["assumed_yield_bp_cost"] for x in costs],
            [x["net_sensitivity"] for x in costs],marker="o")
    ax.axhline(0,color="gray",lw=.7)
    ax.set(xlabel="Assumed yield bp per unit of DV01 turnover",
           ylabel="Modeled USD at $1/bp gross DV01",
           title="Transaction-cost sensitivity — unchanged historical decisions")
    save("05_cost_sensitivity.png")
    return paths


def n(value: float | int, digits: int=2) -> str:
    return f"{value:,.{digits}f}"


def report(result: dict, target: Path) -> None:
    m=result["meta"];ev=result["explained_variance"];eras=result["eras"];costs=result["costs"]
    note=("**RESEARCH ONLY — NOT A TRADING BACKTEST.** The Federal Reserve daily-dated "
          "fitted yields are generally published weekly, typically on Tuesday through the "
          "previous Friday, and may be revised. The simulation delays daily observation "
          "rows, but does not reconstruct publication dates or data vintages. Consequently "
          "it cannot substantiate any investable return or live forecasting ability.")
    lines=[
        "# U.S. Treasury Yield-Curve Factor Research — Historical Study",
        "", "> "+note, "", "## Executive summary", "",
        f"- Dataset: {m['complete_8_tenor_rows']:,} complete eight-tenor records, from {m['analysis_first']} to {m['analysis_last']}.",
        f"- Full-sample daily-change PCA: PC1 {n(ev[0]*100,1)}%, PC2 {n(ev[1]*100,1)}%, PC3 {n(ev[2]*100,1)}%; combined {n(sum(ev)*100,1)}% explained variance.",
        f"- Synthetic risk-model eligible dates: {m['eligible_strategy_rows']:,}; dates with held exposure: {m['active_rows']:,}; entry events: {m['entries']:,}.",
        f"- Net modeled sensitivity at 0.25 bp cost per unit turnover: {n(costs[1]['net_sensitivity'])} USD per assumed $1/bp gross DV01. This is **not actual bond P&L**.",
        "",
        "## Source and fixed methodology", "",
        "Data are Federal Reserve Gürkaynak–Sack–Wright nominal **fitted zero-coupon yields**, not executable Treasury note prices.",
        f"- Source file: {m['source_rows']:,} observations through {m['full_source_latest']}. SHA-256: {m['csv_sha256']}.",
        "- Fixed sample begins 1990-01-01, dropping observations missing any of 1/2/3/5/7/10/20/30Y fitted points.",
        "- Descriptive PCA: three components on unscaled eight-maturity **daily yield changes** (percentage points); sign is arbitrary.",
        "- Synthetic scenario: separate 5Y–7Y–10Y rolling PCA minimum-variance fly constructed from prior daily observations.",
        "- Backtest settings fixed before results: 252-observation PCA, 126-observation z-history, |entry z|=2.0, |exit z|=0.5, gross risk of $1 per bp DV01.",
        "- All scenarios share the same positions; cost is a stylized bp-of-yield charge on modeled DV01 turnover.",
        "- The last 30% calendar slice in the underlying implementation is **not** treated as a genuinely untouched holdout.",
        "",
        "## Historical factors", "",
        "![Fitted yields](figures/01_fitted_yields.png)", "",
        "![PCA factor loadings](figures/02_pca_loadings.png)", "",
        "## Descriptive period comparisons", "",
        "| Period | PCA observations | PC1 % | PC1–3 % | Eligible days | Held % | Entries | Gross $ | Net $ @0.25bp | Net $ @1bp |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
    ]
    for e in eras:
        lines.append(f"| {e['period']} | {e['pca_observations']:,} | {n(e['pc1_pct'],1)} | {n(e['first3_pct'],1)} | {e['strategy_observations']:,} | {n(e['active_pct'],1)} | {e['entries']} | {n(e['gross_sensitivity'])} | {n(e['net_at_025'])} | {n(e['net_at_100'])} |")
    lines += [
        "",
        "Amounts are **synthetic modeled dollars** normalized to $1/bp gross DV01, NOT actual investment dollars, a percentage return, or tradable strategy performance.",
        "",
        "![Explained variance by period](figures/03_explained_variance_by_era.png)",
        "", "## Transaction cost sensitivity", "",
        "| Hypothetical cost (bp) | Gross sensitivity | Cost penalty | Net sensitivity |",
        "|---:|---:|---:|---:|",
    ]
    for e in costs:
        lines.append(f"| {n(e['assumed_yield_bp_cost'])} | {n(e['gross_sensitivity'])} | {n(e['cost_sensitivity'])} | {n(e['net_sensitivity'])} |")
    lines += [
        "", "![Model sensitivity](figures/04_synthetic_pnl_sensitivity.png)",
        "", "![Cost sweep](figures/05_cost_sensitivity.png)",
        "", "## What this does and does not establish", "",
        "1. The retrospective sample reveals covariance structure in U.S. Treasury fitted yields. PCA sign and shape can change across decades; its factors are not standalone alpha.",
        "2. The three-tenor hypothetical fly is not a portfolio of specified CUSIPs. Real bond prices, coupon carry, roll, financing, convexity, spreads, slippage, and borrow are excluded.",
        "3. **Crucial timing caveat:** Two observation rows of delay do not handle the Fed's weekly posting schedule or historical data revisions; the experiment is not point-in-time investable.",
        "4. Comparisons across fixed calendar eras are descriptive, not regime-causal claims; no test was pre-registered and no untouched out-of-sample confirmation is asserted.",
        "5. The transaction cost levels are **assumptions**, not empirically collected market quotes. Sensitivity is in hypothetical dollars normalized to $1/bp gross DV01, not Sharpe/ROI.",
        "", "## Reproduce", "",
        "~~~bash",
        "python -m pip install -r requirements-dev.txt",
        "python -m pip install matplotlib reportlab",
        "python -m scripts.generate_historical_study --data feds200628.csv --output research/historical_study",
        "~~~",
        "",
        "This command recreates this report, the figures, results.json, modeled daily sensitivity and REPORT.pdf without accessing a broker.",
        "", "### Primary source",
        "",
        "- Federal Reserve Board, [Nominal Yield Curve](https://www.federalreserve.gov/data/nominal-yield-curve.htm): methods, fitted-data vintage and weekly publication FAQ.",
        "- Gürkaynak, Sack and Wright, *The U.S. Treasury Yield Curve: 1961 to the Present* (FEDS 2006-28).",
        ""
    ]
    (target/"REPORT.md").write_text("\n".join(lines),encoding="utf-8")


def pdf(result: dict, figs: list[Path], target: Path) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from PIL import Image as PILImage
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Image, Table, TableStyle, KeepTogether
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name="H1Research",parent=styles["Title"],fontSize=18,leading=23,spaceAfter=12))
    styles.add(ParagraphStyle(name="BodyResearch",parent=styles["BodyText"],fontSize=8.5,leading=12,spaceAfter=9))
    styles.add(ParagraphStyle(name="SubResearch",parent=styles["Heading2"],fontSize=12,leading=15,spaceBefore=8,spaceAfter=8))
    doc=SimpleDocTemplate(str(target/"REPORT.pdf"),pagesize=A4,
                          leftMargin=16*mm,rightMargin=16*mm,topMargin=16*mm,bottomMargin=18*mm)
    S=[]
    add=lambda s,kind="BodyResearch":S.append(Paragraph(s,styles[kind]))
    m=result["meta"];ev=result["explained_variance"]
    add("U.S. Treasury Yield-Curve Factor Research","H1Research")
    add("Historical factor decomposition, calendar regime comparisons and transaction-cost sensitivity")
    add("<b>RESEARCH ONLY:</b> Fed fitted-yield observations are generally published weekly and may be revised. These results do not reconstruct the information available on historical trading dates. They are not executable returns.")
    add("Executive findings","SubResearch")
    add(f"Complete records: {m['complete_8_tenor_rows']:,}, {m['analysis_first']} to {m['analysis_last']}. "
        f"PC1: {n(ev[0]*100,1)}% of daily-change variance; PCs 1–3 jointly: {n(sum(ev)*100,1)}%.")
    add(f"Model observations: {m['eligible_strategy_rows']:,} after warm-up; active modeled dates: {m['active_rows']:,}; entry events: {m['entries']:,}. All sensitivity units are hypothetical dollars per assumed $1/bp gross DV01.")
    def fig(path,caption):
        with PILImage.open(path) as raster:
            pixel_width, pixel_height = raster.size
        page_width = 165 * mm
        im = Image(str(path), width=page_width, height=page_width*pixel_height/pixel_width)
        S.append(KeepTogether([im,Paragraph(caption,styles["BodyResearch"])]))
    add("Observed fitted yields and factor loadings","SubResearch")
    fig(figs[0],"Figure 1. Model-derived nominal fitted yields, not cash-bond executable quotes.")
    fig(figs[1],"Figure 2. Descriptive PCA loadings; mathematical signs are arbitrary.")
    fig(figs[2],"Figure 3. Variance share by predefined historical interval.")
    add("Hypothetical sensitivity and assumed costs","SubResearch")
    add("A separate rolling 5Y–7Y–10Y minimum-variance fly model uses a 252-row PCA window, 126-row z-history, entry threshold 2.0 and exit threshold 0.5. Signals are shifted in observation rows; actual public-release availability is not modeled.")
    rows=[["Assumed cost (bp)","Gross $","Cost $","Net $"]]
    for e in result["costs"]:
        rows.append([n(e["assumed_yield_bp_cost"]),n(e["gross_sensitivity"]),n(e["cost_sensitivity"]),n(e["net_sensitivity"])])
    tab=Table(rows,colWidths=[43*mm,42*mm,42*mm,42*mm],repeatRows=1)
    tab.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#E6EDF7")),
        ("GRID",(0,0),(-1,-1),.25,colors.HexColor("#C8CFDB")),
        ("FONTSIZE",(0,0),(-1,-1),8),("ALIGN",(1,1),(-1,-1),"RIGHT"),
        ("BOTTOMPADDING",(0,0),(-1,-1),6)]))
    S.append(tab)
    fig(figs[3],"Figure 4. Retrospective synthetic cumulative sensitivity; NOT a real-bond P&L series.")
    fig(figs[4],"Figure 5. Net sensitivity under different hypothetical unit-turnover costs.")
    add("Limitations and sources","SubResearch")
    add("Data are current-vintage Fed fitted nominal yields. No historical release timestamps, live bond CUSIPs, coupon carry, financing, executable bid/ask, or investment capital are modeled. Cross-era summaries are descriptive, not out-of-sample validation.")
    add(f"CSV SHA-256: {m['csv_sha256']}")
    add("Source: https://www.federalreserve.gov/data/nominal-yield-curve.htm")
    def foot(canvas,doc):
        canvas.saveState();canvas.setFont("Helvetica",8)
        canvas.setFillColor(colors.HexColor("#667788"))
        canvas.drawString(16*mm,10*mm,"Research only — not investment performance")
        canvas.drawRightString(192*mm,10*mm,f"Page {doc.page}")
        canvas.restoreState()
    doc.build(S,onFirstPage=foot,onLaterPages=foot)


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data",type=Path,default=Path("feds200628.csv"))
    p.add_argument("--output",type=Path,default=Path("research/historical_study"))
    p.add_argument("--start",default="1990-01-01")
    args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    result=run_study(args.data,args.start)
    figures=charts(result,args.output)
    report(result,args.output)
    pdf(result,figures,args.output)
    result["daily"].to_csv(args.output/"daily_synthetic_sensitivity.csv",index_label="date")
    summary={k:result[k] for k in ("meta","explained_variance","eras","costs")}
    (args.output/"results.json").write_text(json.dumps(summary,indent=2,allow_nan=False),encoding="utf-8")
    print("HISTORICAL_STUDY_SUMMARY="+json.dumps({
        "start":summary["meta"]["analysis_first"],
        "end":summary["meta"]["analysis_last"],
        "rows":summary["meta"]["complete_8_tenor_rows"],
        "explained_variance":summary["explained_variance"],
        "net_at_025_bp":summary["costs"][1]["net_sensitivity"]},allow_nan=False))
    print("HISTORICAL_STUDY_OUTPUT="+str(args.output))


if __name__=="__main__":
    main()
