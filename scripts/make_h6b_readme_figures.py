"""Generate the H6B README figures from the committed package export.

Run with an ephemeral seaborn environment so the project lockfile is untouched:

    uv run --with seaborn --no-project python scripts/make_h6b_readme_figures.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from matplotlib.colors import ListedColormap

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "studies/HIST_VNEXT/packages/H6B/exports/local-data/package.json"
OUT = ROOT / "docs/figures"

CHECK_LABELS = {
    "schema_valid": "schema",
    "experiment_declared": "declared",
    "paired_control": "paired",
    "first_stage_checked": "first stage",
    "accounting_checked": "accounting",
    "negative_control": "negative",
    "metrics_generated": "metrics",
    "sensitivity_or_reason_not_run": "sensitivity",
    "historical_evidence_grade": "historical",
    "counterevidence": "counter",
    "reproduction_bundle": "replay",
}
STATUS_VALUE = {"PASS": 2, "BLOCKED": 1, "NOT_RUN": 0}
STATUS_LABEL = {"PASS": "P", "BLOCKED": "B", "NOT_RUN": "N"}


def load_package() -> dict:
    return json.loads(PACKAGE.read_text(encoding="utf-8"))


def card_matrix(package: dict) -> None:
    cards = package["cards"]
    ids = list(cards)
    checks = list(next(iter(cards.values()))["checks"])
    values = [
        [STATUS_VALUE[cards[card]["checks"][check]["status"]] for check in checks]
        for card in ids
    ]
    labels = [
        [STATUS_LABEL[cards[card]["checks"][check]["status"]] for check in checks]
        for card in ids
    ]
    fig, ax = plt.subplots(figsize=(12.5, 6.8))
    cmap = ListedColormap(["#d9d9d9", "#f0b429", "#2f8f5b"])
    sns.heatmap(
        pd.DataFrame(values, index=ids, columns=[CHECK_LABELS[c] for c in checks]),
        annot=labels,
        fmt="",
        cmap=cmap,
        vmin=-0.5,
        vmax=2.5,
        linewidths=0.6,
        linecolor="white",
        cbar_kws={"ticks": [0, 1, 2], "label": "0 = NOT_RUN, 1 = BLOCKED, 2 = PASS"},
        annot_kws={"fontsize": 8, "fontweight": "bold"},
        ax=ax,
    )
    ax.set_title(
        "H6B 11-card package contract: 3 complete / 8 blocked\n"
        "P = PASS, B = BLOCKED, N = NOT_RUN",
        loc="left",
        fontsize=13,
    )
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.tick_params(axis="x", rotation=35, labelsize=9)
    ax.tick_params(axis="y", rotation=0, labelsize=9)
    fig.tight_layout()
    fig.savefig(OUT / "h6b_card_matrix.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def key_results(package: dict) -> None:
    cards = package["cards"]
    sns.set_theme(style="whitegrid", context="notebook")
    fig, axes = plt.subplots(2, 2, figsize=(13.5, 9.0))

    # M01: the conditional carried-reference contrast, per seed.
    rows = []
    for item in cards["M01"]["study_metrics"]:
        if item["metric"].endswith("D_four_minus_one_spending_by_seed"):
            lever = item["selector"]["lever"].replace("_cut", "")
            if lever not in {"import", "income"}:
                continue
            rows.append(
                {
                    "lever": lever,
                    "seed": item["selector"]["seed"],
                    "delta_spending": item["value"],
                }
            )
    df = pd.DataFrame(rows)
    sns.barplot(
        data=df,
        x="lever",
        y="delta_spending",
        hue="seed",
        ax=axes[0, 0],
        palette="Blues_d",
    )
    axes[0, 0].axhline(0, color="black", linewidth=0.8)
    axes[0, 0].set_title(
        "M01: carried-history contrast by lever\n"
        "welfare lever is UNIDENTIFIED (not shown as a positive effect)"
    )
    axes[0, 0].set_ylabel("D = R(four_steps) - R(one_jump)\ncumulative spending")
    axes[0, 0].set_xlabel("")
    axes[0, 0].text(
        0.99,
        0.03,
        "welfare: UNIDENTIFIED (omitted)",
        transform=axes[0, 0].transAxes,
        ha="right",
        va="bottom",
        fontsize=9,
        style="italic",
    )

    # M02: soft-budget credit first stage, selected arms.
    selected = {
        "soft_low_base",
        "hard_low_base",
        "credit_cut_high_base",
        "rescue_cut_high_base",
    }
    rows = []
    for item in cards["M02"]["study_metrics"]:
        if item["metric"] != "credit_drawn_total":
            continue
        seed, arm = item["selector"]["arm_seed"].split("|", 1)
        if arm in selected:
            rows.append({"arm": arm, "seed": seed, "credit_drawn": item["value"]})
    df = pd.DataFrame(rows)
    sns.barplot(
        data=df,
        x="arm",
        y="credit_drawn",
        errorbar="sd",
        ax=axes[0, 1],
        color="#4c78a8",
    )
    axes[0, 1].set_title("M02: credit first stage by selected arm\n(3 seeds; mean ± s.d.)")
    axes[0, 1].set_ylabel("final-quarter credit drawn")
    axes[0, 1].tick_params(axis="x", rotation=20)

    # M04: tolerance arms and second-economy hours.
    rows = []
    for item in cards["M04"]["study_metrics"]:
        if item["metric"] == "second_hours_total":
            rows.append(
                {
                    "arm": {
                        "tolerance_0": "0.0",
                        "tolerance_05": "0.5",
                        "tolerance_1": "1.0",
                    }[item["selector"]["arm"]],
                    "seed": item["selector"]["seed"],
                    "second_hours": item["value"],
                }
            )
    df = pd.DataFrame(rows)
    sns.barplot(
        data=df,
        x="arm",
        y="second_hours",
        hue="arm",
        legend=False,
        errorbar="sd",
        ax=axes[1, 0],
        palette="Greens_d",
    )
    axes[1, 0].set_title("M04: second-economy hours by tolerance arm\n(3 seeds × 16 quarters; mean ± s.d.)")
    axes[1, 0].set_ylabel("second hours total")
    axes[1, 0].set_xlabel("second-economy tolerance")

    # M09: forecast error by arm.
    rows = []
    for item in cards["M09"]["study_metrics"]:
        if item["metric"] == "absolute_error":
            rows.append({"arm": item["selector"]["arm"], "error": item["value"]})
    df = pd.DataFrame(rows)
    sns.barplot(
        data=df,
        x="arm",
        y="error",
        errorbar="sd",
        ax=axes[1, 1],
        color="#b56576",
    )
    axes[1, 1].set_title("M09: forecast absolute error by arm\n(synthetic engineering profile; 3 seeds × 4 targets)")
    axes[1, 1].set_ylabel("absolute error")
    axes[1, 1].tick_params(axis="x", rotation=20)
    axes[1, 1].set_xlabel("")

    fig.suptitle(
        "H6B key quantitative results (local-data export; not historical estimates)",
        fontsize=14,
        y=1.01,
    )
    fig.tight_layout()
    fig.savefig(OUT / "h6b_key_results.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    package = load_package()
    card_matrix(package)
    key_results(package)
    print(f"wrote {OUT / 'h6b_card_matrix.png'}")
    print(f"wrote {OUT / 'h6b_key_results.png'}")


if __name__ == "__main__":
    main()
