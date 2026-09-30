"""集成与测试新增：页面（可视化模块）核心函数测试。

覆盖：
  1) C 的全部核心绘图函数在小样例数据上能返回 Figure（不抛异常）；
  2) app.py 的「城市×年份聚合」核心口径（总排放=按日求和、日均=总量/天数）复算一致；
  3) 45 城的城市坐标 / 国家映射常量完整（页面地图依赖）；
  4) B/D 结果文件存在时，聚类地图与预测曲线函数可正常出图（真实结果冒烟）。
"""
from pathlib import Path

import pandas as pd
import pytest

from src.config import CITY_LAT_LON, CITY_NAME_CN, CITY_COUNTRY
from src import visualization as vis

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def ann() -> pd.DataFrame:
    """与 app.py 中 ann 同结构的小样例：2 城 × 3 年。"""
    rows = []
    for city, base in [("Beijing", 100.0), ("London", 60.0)]:
        for year in [2022, 2023, 2024]:
            days = 365
            total = base * days * (1 + 0.1 * (year - 2022))
            lat, lon = CITY_LAT_LON[city]
            rows.append({
                "city": city, "year": year,
                "total_emission": total, "days": days,
                "daily_avg": total / days, "lat": lat, "lon": lon,
            })
    return pd.DataFrame(rows)


@pytest.fixture
def raw_sector_df() -> pd.DataFrame:
    """与 A 清洗输出同结构的小样例（部门粒度）。"""
    dates = pd.date_range("2024-01-01", "2024-02-28", freq="D")
    rows = []
    for city in ["Beijing", "London"]:
        for sector in ["Power", "Ground Transport"]:
            for d in dates:
                rows.append({"city": city, "date": d, "sector": sector,
                             "value": 1.0 + d.day * 0.01, "year": d.year,
                             "month": d.month, "day": d.day,
                             "country": CITY_COUNTRY[city]})
    return pd.DataFrame(rows)


def test_create_map(ann):
    fig = vis.create_map(ann, color_col="total_emission")
    assert fig is not None and len(fig.data) > 0


def test_create_trend(ann):
    fig = vis.create_trend(ann, ["Beijing"])
    assert fig is not None and len(fig.data) > 0


def test_create_ranking_and_distribution(ann):
    assert vis.create_ranking(ann, top_n=15) is not None
    assert vis.create_distribution(ann) is not None


def test_create_heatmap(ann):
    assert vis.create_heatmap(ann, None) is not None


def test_create_pie():
    df = pd.DataFrame({"name": ["电力", "交通"], "value": [60, 40]})
    assert vis.create_pie(df, "测试") is not None


def test_b_pattern_charts():
    """时间规律图：小样例（与统计分析输出同构）能出图。"""
    monthly = pd.DataFrame({"month": range(1, 13), "avg_daily_emissions": [10 + i for i in range(12)]})
    season = pd.DataFrame({"season": ["Spring", "Summer", "Autumn", "Winter"],
                           "value": [10, 12, 11, 13]})
    weekend = pd.DataFrame({"is_weekend": [0, 1], "value": [10.0, 9.5],
                            "day_type": ["Weekday", "Weekend"]})
    syt = pd.DataFrame({"year": [2023, 2023, 2024, 2024],
                        "sector": ["Power", "Ground Transport"] * 2,
                        "value": [100, 80, 110, 85]})
    assert vis.create_monthly_pattern(monthly) is not None
    assert vis.create_season_pattern(season) is not None
    assert vis.create_weekend_pattern(weekend) is not None
    assert vis.create_sector_yearly_trend(syt) is not None


def test_app_aggregation_semantics(raw_sector_df):
    """复算 app.py 的 ann 聚合口径：总排放=按日求和；日均=总量/有数据天数。"""
    sub = raw_sector_df
    ann = sub.groupby(["city", "year"]).agg(
        total_emission=("value", "sum"),
        days=("date", "nunique"),
    ).reset_index()
    ann["daily_avg"] = ann["total_emission"] / ann["days"]
    bj_2024 = ann[(ann["city"] == "Beijing") & (ann["year"] == 2024)].iloc[0]
    expected_total = sub[(sub["city"] == "Beijing")]["value"].sum()
    assert bj_2024["days"] == 59  # 2024-01-01 ~ 2024-02-28
    assert abs(bj_2024["total_emission"] - expected_total) < 1e-9
    assert abs(bj_2024["daily_avg"] - expected_total / 59) < 1e-9


def test_city_reference_tables_complete():
    """45 城的坐标、中文名、国家映射常量齐全且一一对应。"""
    cities = set(CITY_COUNTRY)
    assert len(cities) == 45
    assert set(CITY_LAT_LON) == cities
    assert set(CITY_NAME_CN) == cities
    # 坐标不能是缺省占位 [0, 0]
    for c, (lat, lon) in CITY_LAT_LON.items():
        assert (lat, lon) != (0, 0), f"{c} 坐标缺失"


def test_d_charts_smoke_with_real_results():
    """真实结果存在时，聚类地图与预测曲线（读 results/ 文件）可出图。"""
    cluster_file = PROJECT_ROOT / "results" / "city_clusters.csv"
    if not cluster_file.exists():
        pytest.skip("挖掘分析结果尚未生成，请先运行 python run_pipeline.py")
    fig = vis.create_cluster_map()
    assert not isinstance(fig, str), f"聚类地图出错: {fig}"
    forecast_cities = pd.read_csv(PROJECT_ROOT / "results" / "forecast_results.csv")["city"].unique()
    fig2 = vis.create_forecast_trend(forecast_cities[0])
    assert not isinstance(fig2, str), f"预测曲线出错: {fig2}"
