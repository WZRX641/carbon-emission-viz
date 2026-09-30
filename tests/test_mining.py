"""挖掘分析模块自测（unittest，无需额外依赖）。

运行：
    python -m unittest tests.test_mining -v
"""
import unittest

from src import sample_data
from src.mining_analysis import (
    FEATURE_DEFS, build_city_features, choose_best_k, profile_clusters,
    run_clustering, run_forecast, select_k,
)
from src.utils import PROJECT_ROOT, load_config, load_clean_data


class TestMining(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = load_config()
        cls.df = sample_data.generate(seed=cls.cfg["random_state"])
        cls.feat = build_city_features(cls.df)

    def test_feature_schema(self):
        for col in ["city", "country", "level", "volatility", "seasonality", "growth"]:
            self.assertIn(col, self.feat.columns)
        self.assertEqual(len(self.feat), self.df["city"].nunique())
        self.assertTrue((self.feat["volatility"] >= 0).all())

    def test_k_selection_runs(self):
        from sklearn.preprocessing import StandardScaler
        import numpy as np
        X = StandardScaler().fit_transform(self.feat[list(FEATURE_DEFS.keys())].to_numpy(float))
        ev = select_k(X, self.cfg["clustering"]["k_range"], self.cfg["random_state"])
        self.assertIn("k", ev.columns)
        self.assertIn("silhouette", ev.columns)
        self.assertTrue((ev["k"] >= 2).all())

    def test_clustering_deterministic(self):
        from sklearn.preprocessing import StandardScaler
        import numpy as np
        X = StandardScaler().fit_transform(self.feat[list(FEATURE_DEFS.keys())].to_numpy(float))
        k = choose_best_k(select_k(X, self.cfg["clustering"]["k_range"], 42), None)
        _, f1 = run_clustering(X, self.feat, k, 42)
        _, f2 = run_clustering(X, self.feat, k, 42)
        self.assertListEqual(f1["cluster"].tolist(), f2["cluster"].tolist())

    def test_profile_has_name(self):
        from sklearn.preprocessing import StandardScaler
        import numpy as np
        X = StandardScaler().fit_transform(self.feat[list(FEATURE_DEFS.keys())].to_numpy(float))
        k = choose_best_k(select_k(X, self.cfg["clustering"]["k_range"], 42), None)
        _, feat_lab = run_clustering(X, self.feat, k, 42)
        prof, names, _ = profile_clusters(feat_lab)
        self.assertEqual(len(prof), k)
        self.assertTrue(all(isinstance(v, str) and v for v in names.values()))

    def test_forecast_smoke(self):
        res, met = run_forecast(self.df, top_n=3, test_years=1,
                                random_state=self.cfg["random_state"])
        self.assertIn("y_pred", res.columns)
        self.assertIn("R2", met.columns)
        self.assertFalse(met.empty)


if __name__ == "__main__":
    unittest.main(verbosity=2)
