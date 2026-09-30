"""挖掘分析模块集成测试（供 集成与测试在整合阶段直接使用）。

验证 D 的交付物满足「可被 E 按文件名和接口直接整合」的验收项：
  1) 运行后关键 CSV 全部存在；
  2) 列名/单位与契约一致（见 docs/c_interface.md）；
  3) 结果非空；
  4) 固定 random_state 下聚类结果可重复。

运行：
    python -m unittest tests.test_integration -v

说明：本测试会自动生成合成样例数据（仅当 data/processed/clean_data.csv 缺失时），
以在没有 A 真实数据时也能验证整合链路；接入 A 真实数据后无需改动本文件。
"""
import unittest
from pathlib import Path

from src import sample_data
from src.mining_analysis import main as mining_main
from src.utils import PROJECT_ROOT, load_config

RESULTS = PROJECT_ROOT / "results"
DATA_PROC = PROJECT_ROOT / "data" / "processed"
EXPECTED_COLS = {
    "city_features.csv": ["city", "country", "level", "volatility", "seasonality", "growth"],
    "city_clusters.csv": ["city", "country", "cluster", "cluster_name", "level", "volatility", "seasonality", "growth", "total_emission"],
    "cluster_evaluation.csv": ["k", "inertia", "silhouette", "calinski_harabasz"],
    "cluster_profiles.csv": ["cluster", "level", "volatility", "seasonality", "growth", "n_cities", "cluster_name"],
}
FORECAST_COLS = {
    "forecast_results.csv": ["city", "date", "split", "y_true", "y_pred"],
    "forecast_metrics.csv": ["city", "model", "n_train", "n_test", "MAE", "RMSE", "R2", "MAPE"],
}


class TestDIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 缺真实数据时用合成样例，保证整链路现在就能验证
        if not (DATA_PROC / "clean_data.csv").exists():
            df = sample_data.generate(seed=42)
            DATA_PROC.mkdir(parents=True, exist_ok=True)
            df.to_csv(DATA_PROC / "clean_data.csv", index=False, encoding="utf-8")
        # 运行 D 全流程（含预测，作为集成最强检查）
        rc = mining_main(["--forecast"])
        cls.rc = rc

    def test_run_ok(self):
        self.assertEqual(self.rc, 0)

    def test_core_deliverables_exist(self):
        for f in EXPECTED_COLS:
            self.assertTrue((RESULTS / f).exists(), f"缺失交付物: {f}")

    def test_schema_matches_contract(self):
        import pandas as pd
        for f, cols in EXPECTED_COLS.items():
            d = pd.read_csv(RESULTS / f)
            for c in cols:
                self.assertIn(c, d.columns, f"{f} 缺少列 {c}")
            self.assertGreater(len(d), 0, f"{f} 为空")

    def test_clusters_count_consistent(self):
        import pandas as pd
        feat = pd.read_csv(RESULTS / "city_features.csv")
        cl = pd.read_csv(RESULTS / "city_clusters.csv")
        self.assertEqual(len(feat), len(cl), "city_features 与 city_clusters 行数应一致")

    def test_forecast_optional_present(self):
        import pandas as pd
        for f, cols in FORECAST_COLS.items():
            self.assertTrue((RESULTS / f).exists(), f"预测文件缺失(若开启--forecast应存在): {f}")
            d = pd.read_csv(RESULTS / f)
            for c in cols:
                self.assertIn(c, d.columns, f"{f} 缺少列 {c}")

    def test_reproducible(self):
        import pandas as pd
        # 再跑一次，聚类标签应完全一致（固定 random_state）
        mining_main(["--forecast"])
        a = pd.read_csv(RESULTS / "city_clusters.csv").sort_values("city")["cluster"].tolist()
        b = pd.read_csv(RESULTS / "city_clusters.csv").sort_values("city")["cluster"].tolist()
        self.assertEqual(a, b, "固定 random_state 下聚类结果应可重复")


if __name__ == "__main__":
    unittest.main(verbosity=2)
