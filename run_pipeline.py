"""统一运行入口：一键完成 A(清洗) → B(统计) → D(挖掘/预测) 全流程。

用法（项目根目录）：
    python run_pipeline.py                 # 按 config.yaml 默认路径运行全流程
    python run_pipeline.py --input data/raw   # 指定原始数据位置（文件或目录）
    python run_pipeline.py --skip-b          # 跳过 B 统计（调试用）
    python run_pipeline.py --no-forecast     # 关闭 D 预测（只跑聚类）

流程（每一步都可独立用 src/ 下对应模块重跑）：
    1) A  src.data_cleaning      data/raw → data/carbonmonitor_clean.csv (+质量摘要)
    2)   质量摘要桥接复制到 results/quality_summary.csv（页面读取口径）
    3) B  src.statistics_analysis data/raw → results/*.csv（9 个统计文件）
    4) D  src.ingest_a            data/carbonmonitor_clean.csv → data/processed/clean_data.csv
    5) D  src.mining_analysis     聚类 + 预测 → results/{city_clusters,forecast_*}.csv 等
    6) 校验 C 页面所需的全部文件是否存在

运行成功后执行 `streamlit run app.py` 即可启动可视化页面。
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src import data_cleaning as a_mod          # noqa: E402
from src import statistics_analysis as b_mod    # noqa: E402
from src import ingest_a, mining_analysis       # noqa: E402


def load_config() -> dict:
    cfg_path = PROJECT_ROOT / "config.yaml"
    with cfg_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def step_a(cfg: dict, raw_input: Path) -> None:
    """A：原始数据 → 清洗数据 + 质量摘要（输出到 data/）。"""
    print("\n" + "=" * 60)
    print("[1/5] 数据清洗模块")
    print("=" * 60)
    out_dir = PROJECT_ROOT / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = a_mod.run(raw_input, out_dir)
    # 桥接：A 的质量摘要复制到 results/（C 页面从 results/quality_summary.csv 读取）
    results_dir = PROJECT_ROOT / cfg["pipeline"]["results_dir"]
    results_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(out_dir / "quality_summary.csv", results_dir / "quality_summary.csv")
    print(f"清洗完成：{summary['rows_after']} 行, {summary['cities']} 城市, "
          f"{summary['sectors']} 部门, {summary['date_min']} ~ {summary['date_max']}")
    print("质量摘要已同步到 results/quality_summary.csv（页面口径）")


def step_b(cfg: dict, raw_input: Path) -> None:
    """B：原始数据 → 9 个统计结果文件（输出到 results/）。"""
    print("\n" + "=" * 60)
    print("[2/5] 统计分析模块")
    print("=" * 60)
    b_mod.run(
        raw_input,
        PROJECT_ROOT / cfg["pipeline"]["results_dir"],
        PROJECT_ROOT / cfg["pipeline"]["docs_dir"],
    )


def step_d_ingest(cfg: dict) -> None:
    """D 第一步：A 清洗输出 → D 统一输入（含 country 回填、部门汇总）。"""
    print("\n" + "=" * 60)
    print("[3/5] 挖掘分析模块：数据对接 (ingest_a)")
    print("=" * 60)
    rc = ingest_a.main([
        "--input", str(PROJECT_ROOT / cfg["pipeline"]["a_output_csv"]),
        "--output", str(PROJECT_ROOT / "data" / "processed" / "clean_data.csv"),
    ])
    if rc != 0:
        raise RuntimeError("ingest_a 运行失败，请检查 data/carbonmonitor_clean.csv 是否存在")


def step_d_mining(forecast: bool) -> None:
    """D 第二步：聚类（+ 可选预测）。"""
    print("\n" + "=" * 60)
    print("[4/5] 挖掘分析模块：聚类与预测 (mining_analysis)")
    print("=" * 60)
    args = ["--no-plots"] if not forecast else ["--no-plots", "--forecast"]
    rc = mining_analysis.main(args)
    if rc != 0:
        raise RuntimeError("mining_analysis 运行失败")


# C 页面所需的文件清单（app.py 读取口径）
APP_REQUIRED_FILES = [
    "data/carbonmonitor_clean.csv",
    "results/quality_summary.csv",
    "results/city_ranking.csv",
    "results/monthly_pattern.csv",
    "results/season_pattern.csv",
    "results/sector_structure.csv",
    "results/sector_yearly_trend.csv",
    "results/statistics_summary.csv",
    "results/time_trend.csv",
    "results/weekend_pattern.csv",
    "results/city_clusters.csv",
    "results/forecast_results.csv",
    "results/forecast_metrics.csv",
    "results/cluster_profiles.csv",
]


def verify_outputs() -> list[str]:
    """校验 C 页面所需文件全部生成，返回缺失清单。"""
    print("\n" + "=" * 60)
    print("[5/5] 交付物完整性校验")
    print("=" * 60)
    missing = [f for f in APP_REQUIRED_FILES if not (PROJECT_ROOT / f).exists()]
    if missing:
        print("缺失文件：")
        for f in missing:
            print(f"  - {f}")
    else:
        print(f"全部 {len(APP_REQUIRED_FILES)} 个页面所需文件均已生成 ✔")
    return missing


def main() -> int:
    parser = argparse.ArgumentParser(description="全球城市碳排放分析：A→B→D 一键全流程")
    parser.add_argument("--input", default=None, help="原始数据路径（文件或目录），默认取 config.yaml 的 raw_input")
    parser.add_argument("--skip-b", action="store_true", help="跳过 B 统计模块")
    parser.add_argument("--no-forecast", action="store_true", help="关闭 D 预测（仅聚类）")
    args = parser.parse_args()

    cfg = load_config()
    raw_input = Path(args.input) if args.input else PROJECT_ROOT / cfg["pipeline"]["raw_input"]
    if not raw_input.exists():
        print(f"[错误] 原始数据不存在: {raw_input}")
        print("请先按 README 下载数据并放入 data/raw/，或用 --input 指定路径。")
        return 1

    step_a(cfg, raw_input)
    if not args.skip_b:
        step_b(cfg, raw_input)
    step_d_ingest(cfg)
    step_d_mining(forecast=not args.no_forecast)
    missing = verify_outputs()

    print("\n" + "=" * 60)
    if missing:
        print(f"全流程完成，但有 {len(missing)} 个文件缺失（见上）。")
        return 2
    print("全流程完成 ✔  启动页面：streamlit run app.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
