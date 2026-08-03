"""Export benchmark reports as paper-ready tables and figures.

The JSON report remains the canonical machine-readable output.  This module is
only a presentation layer: every value is read from the already pair-aware
``aggregate`` report, so a repeated run is never accidentally counted as a
second benchmark pair while rendering a table or a plot.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Iterable


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _number(value: Any, digits: int = 2) -> str:
    number = _finite(value)
    if number is None:
        return "--"
    return f"{number:.{digits}f}"


def _percent(value: Any, digits: int = 1) -> str:
    number = _finite(value)
    if number is None:
        return "--"
    return f"{number:.{digits}f}\\%"


def _pretty_name(value: Any) -> str:
    text = str(value)
    text = text.replace("Category1_", "Category 1: ")
    text = text.replace("Category2_", "Category 2: ")
    text = text.replace("Category3_", "Category 3: ")
    text = text.replace("Category4_", "Category 4: ")
    text = text.replace("Category5_", "Category 5: ")
    return text.replace("_", " ")


def _latex_text(value: Any) -> str:
    text = str(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in text)


def _write_table(
    path: Path,
    *,
    caption: str,
    label: str,
    headers: list[str],
    rows: Iterable[Iterable[Any]],
    numeric_columns: set[int] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    numeric_columns = numeric_columns or set()
    alignment = "".join("r" if index in numeric_columns else "l" for index in range(len(headers)))
    lines = [
        r"\begin{table*}[t]",
        r"\centering",
        r"\small",
        f"\\caption{{{_latex_text(caption)}}}",
        f"\\label{{{_latex_text(label)}}}",
        f"\\begin{{tabular}}{{{alignment}}}",
        r"\toprule",
        " & ".join(f"\\textbf{{{_latex_text(header)}}}" for header in headers) + r" \\ ",
        r"\midrule",
    ]
    for row in rows:
        rendered = []
        for index, value in enumerate(row):
            rendered.append(_latex_text(value) if index not in numeric_columns else str(value))
        lines.append(" & ".join(rendered) + r" \\ ")
    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table*}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def _group_rows(report: dict[str, Any], key: str) -> list[tuple[str, dict[str, Any]]]:
    groups = report.get(key) or {}
    return [(str(name), values) for name, values in sorted(groups.items())]


def _summary_row(name: str, values: dict[str, Any]) -> list[str]:
    tokens = values.get("tokens") or {}
    return [
        _pretty_name(name),
        str(int(values.get("pair_count", 0))),
        _percent(float(values.get("pass_rate", 0.0)) * 100.0),
        _number(values.get("score_mean")),
        _number(values.get("attempts_used_mean")),
        _number(values.get("best_code_tokens_mean"), 1),
        _number(tokens.get("mean_per_pair"), 0),
    ]


def _write_group_table(report: dict[str, Any], key: str, path: Path, caption: str, label: str) -> None:
    rows = [_summary_row(name, values) for name, values in _group_rows(report, key)]
    rows.append(_summary_row("Overall", report.get("metrics") or {}))
    _write_table(
        path,
        caption=caption,
        label=label,
        headers=["Group", "Pairs", "Pass rate", "Score", "Attempts", "Code tokens", "Tokens / pair"],
        rows=rows,
        numeric_columns={1, 2, 3, 4, 5, 6},
    )


def _write_main_table(report: dict[str, Any], path: Path) -> None:
    rows = [_summary_row(name, values) for name, values in _group_rows(report, "by_model")]
    rows.append(_summary_row("Overall", report.get("metrics") or {}))
    _write_table(
        path,
        caption="PACE-Bench results by model. Rates are aggregated over benchmark pairs; repeated runs are used for Pass@k and are not counted as additional pairs.",
        label="tab:pace_main_results",
        headers=["Model", "Pairs", "Pass rate", "Score", "Attempts", "Code tokens", "Tokens / pair"],
        rows=rows,
        numeric_columns={1, 2, 3, 4, 5, 6},
    )


def _write_overall_metrics(report: dict[str, Any], path: Path) -> None:
    metrics = report.get("metrics") or {}
    tokens = metrics.get("tokens") or {}
    rows: list[list[str]] = [
        ["Result trajectories", str(report.get("trajectory_count", 0))],
        ["Benchmark pairs", str(report.get("pair_count", 0))],
        ["Pass rate (any run)", _percent(float(report.get("pass_rate", 0.0)) * 100.0)],
        ["Mean best score", _number(report.get("mean_best_score"))],
        ["Best-score standard deviation", _number(report.get("best_score_std"))],
        ["Mean verified attempts", _number(report.get("mean_verified_attempts"))],
        ["Adaptation efficiency", _percent(float(metrics.get("adaptation_efficiency", 0.0)) * 100.0)],
        ["Mean best-code tokens", _number(metrics.get("best_code_tokens_mean"), 1)],
        ["Mean tokens per pair", _number(tokens.get("mean_per_pair"), 0)],
    ]
    for key, values in sorted((report.get("pass_at_k") or {}).items(), key=lambda item: int(item[0].split("@")[-1])):
        rows.append([key, _percent(float(values.get("rate", 0.0)) * 100.0)])
    _write_table(
        path,
        caption="Overall PACE-Bench metrics.",
        label="tab:pace_overall_metrics",
        headers=["Metric", "Value"],
        rows=rows,
        numeric_columns={1},
    )


def _write_error_table(report: dict[str, Any], path: Path) -> None:
    taxonomy = report.get("error_taxonomy") or {}
    counts = taxonomy.get("counts") or {}
    rates = taxonomy.get("rates") or {}
    failure_rates = taxonomy.get("failure_only_rates") or {}
    rows = [
        [
            _pretty_name(name),
            str(int(count)),
            _percent(float(rates.get(name, 0.0)) * 100.0),
            _percent(float(failure_rates[name]) * 100.0) if name in failure_rates else "--",
        ]
        for name, count in sorted(counts.items())
    ]
    _write_table(
        path,
        caption="Pair-level outcome and error taxonomy. The failure-only column excludes successful pairs.",
        label="tab:pace_error_taxonomy",
        headers=["Outcome / error", "Pairs", "All pairs", "Failed pairs"],
        rows=rows,
        numeric_columns={1, 2, 3},
    )


def _write_budget_table(report: dict[str, Any], path: Path) -> None:
    points = ((report.get("budget_sensitivity") or {}).get("overall") or {}).get("points") or {}
    rows = [
        [
            str(attempt),
            str(int(values.get("passed_pairs", 0))),
            str(int(values.get("pair_count", 0))),
            _percent(float(values.get("rate", 0.0)) * 100.0),
            _percent(float(values.get("saturation_of_final", 0.0)) * 100.0),
        ]
        for attempt, values in sorted(points.items(), key=lambda item: int(item[0]))
    ]
    _write_table(
        path,
        caption="Pass-rate saturation as the valid-attempt budget increases.",
        label="tab:pace_budget_sensitivity",
        headers=["Attempt budget", "Passed pairs", "Pairs", "Pass rate", "Saturation"],
        rows=rows,
        numeric_columns={0, 1, 2, 3, 4},
    )


def _write_model_category_table(report: dict[str, Any], path: Path) -> None:
    values = report.get("by_model_and_category") or {}
    models = sorted(values)
    categories = sorted({category for model in values.values() for category in model})
    rows = []
    for model in models:
        rows.append(
            [_pretty_name(model)]
            + [
                _percent(float((values.get(model, {}).get(category) or {}).get("pass_rate", 0.0)) * 100.0)
                if category in values.get(model, {})
                else "--"
                for category in categories
            ]
        )
    _write_table(
        path,
        caption="Pair-level pass rate by model and benchmark category.",
        label="tab:pace_model_category",
        headers=["Model"] + [_pretty_name(category) for category in categories],
        rows=rows,
        numeric_columns=set(range(1, len(categories) + 1)),
    )


def _load_matplotlib():
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    return plt


def _save_figure(plt: Any, fig: Any, directory: Path, name: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for extension in ("pdf", "png"):
        fig.savefig(
            directory / f"{name}.{extension}",
            facecolor="white",
            bbox_inches="tight",
            pad_inches=0.10,
            dpi=300 if extension == "png" else None,
        )
    plt.close(fig)


def _style_axes(ax: Any) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", color="#dddddd", linewidth=0.7)
    ax.set_axisbelow(True)


def _plot_group_bar(plt: Any, report: dict[str, Any], key: str, name: str, ylabel: str, filename: str) -> None:
    groups = _group_rows(report, key)
    if not groups:
        return
    labels = [_pretty_name(group) for group, _ in groups]
    values = [float(data.get("pass_rate", 0.0)) * 100.0 for _, data in groups]
    fig, ax = plt.subplots(figsize=(max(5.5, len(labels) * 1.35), 4.0))
    bars = ax.bar(range(len(labels)), values, color="#4472C4", width=0.68)
    ax.set_xticks(range(len(labels)), labels, rotation=25, ha="right")
    ax.set_ylabel(ylabel)
    ax.set_ylim(0, max(100.0, max(values, default=0.0) * 1.18))
    ax.set_title(name)
    _style_axes(ax)
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.0, f"{value:.1f}%", ha="center", va="bottom", fontsize=8)
    fig.tight_layout()
    _save_figure(plt, fig, Path(plt._pace_figure_directory), filename)


def _plot_attempt_curve(plt: Any, report: dict[str, Any], metric: str, filename: str, ylabel: str, title: str) -> None:
    metrics = report.get("metrics") or {}
    overall = metrics.get(metric) or {}
    x = sorted((int(key) for key in overall), key=int)
    if not x:
        return
    fig, ax = plt.subplots(figsize=(6.2, 4.0))
    if metric == "attempt_discovery":
        y = [float(overall[str(attempt)].get("rate", 0.0)) * 100.0 for attempt in x]
    else:
        y = [float(overall.get(str(attempt), 0.0)) for attempt in x]
    ax.plot(x, y, marker="o", linewidth=2.2, markersize=3.5, label="Overall", color="#4472C4")
    for category, values in _group_rows(report, "by_category"):
        curve = values.get(metric) or {}
        if not curve:
            continue
        if metric == "attempt_discovery":
            points = [(attempt, float(curve[str(attempt)].get("rate", 0.0)) * 100.0) for attempt in x if str(attempt) in curve]
        else:
            points = [(attempt, float(curve[str(attempt)])) for attempt in x if str(attempt) in curve]
        if points:
            ax.plot([p[0] for p in points], [p[1] for p in points], linewidth=1.2, alpha=0.85, label=_pretty_name(category))
    ax.set_xlabel("Verified attempt")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    _style_axes(ax)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    _save_figure(plt, fig, Path(plt._pace_figure_directory), filename)


def _plot_error_taxonomy(plt: Any, report: dict[str, Any], filename: str) -> None:
    taxonomy = report.get("error_taxonomy") or {}
    rates = taxonomy.get("rates") or {}
    if not rates:
        return
    labels = [_pretty_name(name) for name in sorted(rates)]
    values = [float(rates[name]) * 100.0 for name in sorted(rates)]
    colors = ["#70AD47" if name == "success" else "#C0504D" for name in sorted(rates)]
    fig, ax = plt.subplots(figsize=(max(6.0, len(labels) * 1.05), 4.0))
    bars = ax.bar(range(len(labels)), values, color=colors)
    ax.set_xticks(range(len(labels)), labels, rotation=30, ha="right")
    ax.set_ylabel("Pairs (%)")
    ax.set_title("Pair-level outcome and error taxonomy")
    ax.set_ylim(0, max(100.0, max(values, default=0.0) * 1.2))
    _style_axes(ax)
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.8, f"{value:.1f}%", ha="center", va="bottom", fontsize=8)
    fig.tight_layout()
    _save_figure(plt, fig, Path(plt._pace_figure_directory), filename)


def _plot_model_category_heatmap(plt: Any, report: dict[str, Any], filename: str) -> None:
    values = report.get("by_model_and_category") or {}
    models = sorted(values)
    categories = sorted({category for model in values.values() for category in model})
    if not models or not categories:
        return
    matrix = [
        [float((values.get(model, {}).get(category) or {}).get("pass_rate", 0.0)) * 100.0 for category in categories]
        for model in models
    ]
    fig, ax = plt.subplots(figsize=(max(5.5, len(categories) * 1.6), max(3.5, len(models) * 0.8)))
    image = ax.imshow(matrix, cmap="Blues", vmin=0, vmax=100, aspect="auto")
    ax.set_xticks(range(len(categories)), [_pretty_name(category) for category in categories], rotation=25, ha="right")
    ax.set_yticks(range(len(models)), [_pretty_name(model) for model in models])
    ax.set_title("Pair-level pass rate by model and category")
    for row_index, row in enumerate(matrix):
        for column_index, value in enumerate(row):
            ax.text(column_index, row_index, f"{value:.1f}%", ha="center", va="center", fontsize=8, color="black" if value < 65 else "white")
    fig.colorbar(image, ax=ax, label="Pass rate (%)", pad=0.02)
    fig.tight_layout()
    _save_figure(plt, fig, Path(plt._pace_figure_directory), filename)


def export_paper_artifacts(report: dict[str, Any], table_dir: Path, figure_dir: Path) -> dict[str, Any]:
    """Write LaTeX table fragments and PDF/PNG figures from an aggregate report."""

    table_dir = Path(table_dir)
    figure_dir = Path(figure_dir)
    table_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)

    _write_main_table(report, table_dir / "main_results.tex")
    _write_group_table(report, "by_category", table_dir / "category_results.tex", "PACE-Bench results by benchmark category.", "tab:pace_category_results")
    _write_group_table(report, "by_stage", table_dir / "stage_results.tex", "PACE-Bench results by target environment stage.", "tab:pace_stage_results")
    _write_overall_metrics(report, table_dir / "overall_metrics.tex")
    _write_error_table(report, table_dir / "error_taxonomy.tex")
    _write_budget_table(report, table_dir / "budget_sensitivity.tex")
    _write_model_category_table(report, table_dir / "model_category_pass_rate.tex")

    plt = _load_matplotlib()
    if plt is None:
        return {"tables": 7, "figures": 0, "figure_error": "matplotlib is not installed"}

    # Keep the output directory explicit without making it global process state.
    plt._pace_figure_directory = figure_dir
    _plot_group_bar(plt, report, "by_model", "Pass rate by model", "Pass rate (%)", "pass_rate_by_model")
    _plot_group_bar(plt, report, "by_category", "Pass rate by category", "Pass rate (%)", "pass_rate_by_category")
    _plot_group_bar(plt, report, "by_stage", "Pass rate by target stage", "Pass rate (%)", "pass_rate_by_stage")
    _plot_attempt_curve(plt, report, "attempt_discovery", "pass_rate_by_attempt", "Pass rate (%)", "Pass-rate discovery curve")
    _plot_attempt_curve(plt, report, "score_by_attempt", "score_by_attempt", "Mean score", "Score by verified attempt")
    _plot_error_taxonomy(plt, report, "error_taxonomy")
    _plot_model_category_heatmap(plt, report, "model_category_pass_rate")
    return {"tables": 7, "figures": len(list(figure_dir.glob("*.pdf")))}
