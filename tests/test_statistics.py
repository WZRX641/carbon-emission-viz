"""集成与测试新增：统计结果非空测试（统计分析模块输出 + 页面读取口径）。

覆盖：
  1) B 的 run() 在小样例数据上产出全部 9 个统计文件且非空（统计结果非空）；
  2) 统计数值合理（城市排名降序、部门占比合计≈100%）；
  3) C 页面的 load_b_data() 能完整读取 B 的 9 个文件（接口一致性）；
  4) 真实 results/（若已生成）下统计文件全部存在且非空。
"""
from pathlib import Path

import pandas as pd

from src import statistics_analysis as b_mod
from src.config import B_FILES

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def make_sample_raw() -> pd.DataFrame:
    """构造与 Carbon Monitor Cities 同结构的小样例（2 城 × 2 部门 × 若干天）。"""
    rows = []
    dates = pd.date_range("2019-01-01", "2019-03-31", freq="D")
    for i, city in enumerate(["Beijing", "London"]):
        for sector in ["Power", "Ground Transport"]:
            for d in dates:
                rows.append({
                    "city": city,
                    "date": d.strftime("%d/%m/%Y"),
                    "sector": sector,
                    "value": 10 + i * 5 + (1 if d.weekday() >= 5 else 0) + d.day * 0.1,
                })
    return pd.DataFrame(rows)


def test_b_outputs_non_empty(tmp_path, monkeypatch):
    """统计分析模块：小样例 → 9 个输出文件全部存在且非空。"""
    raw = tmp_path / "raw"
    raw.mkdir()
    make_sample_raw().to_csv(raw / "sample.csv", index=False)

    results = tmp_path / "results"
    docs = tmp_path / "docs"
    b_mod.run(raw, results, docs)

    expected = set(B_FILES.values()) - {"quality_summary.csv"}  # quality_summary 由 A 产出
    for fname in expected:
        f = results / fname
        assert f.exists(), f"缺少统计结果文件: {fname}"
        df = pd.read_csv(f)
        assert len(df) > 0, f"统计结果为空: {fname}"


def test_b_ranking_sorted(tmp_path):
    """城市排名：rank_by_total 与 total_emissions 降序一致。"""
    raw = tmp_path / "raw"
    raw.mkdir()
    make_sample_raw().to_csv(raw / "sample.csv", index=False)
    results = tmp_path / "results"
    b_mod.run(raw, results, tmp_path / "docs")

    cr = pd.read_csv(results / "city_ranking.csv")
    assert cr["total_emissions"].is_monotonic_decreasing
    assert cr["rank_by_total"].iloc[0] == 1
    assert int(cr["rank_by_total"].max()) == len(cr)


def test_b_sector_percentage_sums_to_100(tmp_path):
    """部门结构：percentage 合计约等于 100。"""
    raw = tmp_path / "raw"
    raw.mkdir()
    make_sample_raw().to_csv(raw / "sample.csv", index=False)
    results = tmp_path / "results"
    b_mod.run(raw, results, tmp_path / "docs")

    ss = pd.read_csv(results / "sector_structure.csv")
    assert abs(ss["percentage"].sum() - 100.0) < 1e-6


def test_load_b_data_reads_all_files(tmp_path, monkeypatch):
    """C 页面 load_b_data()：把工作目录切到 tmp_path，验证能读齐全部 B 文件。"""
    raw = tmp_path / "raw"
    raw.mkdir()
    make_sample_raw().to_csv(raw / "sample.csv", index=False)
    results = tmp_path / "results"
    b_mod.run(raw, results, tmp_path / "docs")
    # A 的质量摘要桥接文件（run_pipeline.py 会复制；测试里手工生成一个）
    pd.DataFrame([{"cities": 2, "sectors": 2, "date_min": "2019-01-01",
                   "date_max": "2019-03-31"}]).to_csv(
        results / "quality_summary.csv", index=False)

    monkeypatch.chdir(tmp_path)
    # 重新加载配置（路径基于工作目录）
    import importlib
    import src.config as cfg_mod
    importlib.reload(cfg_mod)
    b_data = cfg_mod.load_b_data()
    for key in B_FILES:
        assert b_data.get(key) is not None, f"页面未能读取统计分析文件: {key}"
    assert len(b_data) == len(B_FILES)


def test_real_results_non_empty():
    """真实 results/ 目录（若已生成）下统计文件全部存在且非空。"""
    results = PROJECT_ROOT / "results"
    if not (results / "statistics_summary.csv").exists():
        import pytest
        pytest.skip("真实统计结果尚未生成，请先运行 python run_pipeline.py")
    for fname in B_FILES.values():
        f = results / fname
        assert f.exists(), f"真实结果缺少: {fname}"
        df = pd.read_csv(f)
        assert len(df) > 0, f"真实结果为空: {fname}"
