# D → C 结果对接说明（可视化专用）

> 给 C（可视化）看：D 的全部产物都落在 `results/`，C 直接读取即可作图，无需重算。
> 本文档与 `src/mining_analysis.py` 的输出保持一致；D 每次运行会自动更新 `results/` 下的 CSV，
> 接口列名固定，C 可放心依赖。

## 0. 前置：D 未运行时的友好提示
若 `results/city_clusters.csv` 不存在，说明 D 尚未产出结果。C 应在对应展示区显示：
"聚类/预测结果尚未生成（挖掘分析待运行）"，而不是报错或留白。
可检测 `results/city_clusters.csv` 是否存在来决定是否渲染该区块。

## 1. 文件清单与字段契约

### 1.1 `results/city_clusters.csv`（每城市聚类标签 + 关键特征）
| 列 | 含义 | 用途 |
|----|------|------|
| `city` | 城市名 | 与地图/其他表关联键 |
| `country` | 国家 | 地图/筛选 |
| `cluster` | 聚类编号（0,1,2…） | **上色分组键** |
| `cluster_name` | 类别画像名（中文，如"高排放-稳波动-弱季节-增长型"） | 图例/ tooltip |
| `level` | 平均月排放（万吨CO₂/月） | 散点大小/颜色、排序 |
| `volatility` | 变异系数 CV（无量纲） | 坐标轴 |
| `seasonality` | 季节振幅（无量纲） | 坐标轴 |
| `growth` | 年增长率（%/年） | 坐标轴 |
| `total_emission` | 全期总排放 | 排序 |

**建议图**：① 世界地图按 `cluster` 着色（或按 `level` 着色 + `cluster` 叠加）；
② `level` vs `volatility` 散点，点色=`cluster`；③ 各类城市数柱状图（按 `cluster` 计数）。

### 1.2 `results/cluster_profiles.csv`（每类特征均值 = 类别画像）
| 列 | 含义 |
|----|------|
| `cluster` | 类别编号 |
| `level` / `volatility` / `seasonality` / `growth` | 该类在四个特征上的均值 |
| `n_cities` | 该类城市数 |
| `cluster_name` | 类别名 |

**建议图**：雷达图（4 个特征为轴，每类一条线）或分组柱状图，直观对比类别差异。

### 1.3 `results/cluster_evaluation.csv`（K 值选择依据）
| 列 | 含义 |
|----|------|
| `k` | 候选聚类数 |
| `inertia` | 肘部指标（越小越好） |
| `silhouette` | 轮廓系数（越大越好，D 默认用它选 K） |
| `calinski_harabasz` | CH 指标（越大越好） |

**建议图**：双轴折线（inertia + silhouette vs k），标出最终选定的 K。

### 1.4 `results/forecast_results.csv`（预测结果，仅 `--forecast` 时生成）
| 列 | 含义 |
|----|------|
| `city` | 城市 |
| `date` | 月份 |
| `split` | `test`（已发生、有真值）/ `future`（外推、无真值） |
| `y_true` | 真实值（future 行为空） |
| `y_pred` | 预测值 |

**建议图**：每个代表城市一条时序线，实线=真实（train+test），虚线=预测，竖向虚线分隔 train/test。

### 1.5 `results/forecast_metrics.csv`（预测测试集指标，仅 `--forecast` 时生成）
| 列 | 含义 |
|----|------|
| `city` | 城市 |
| `model` | 模型（RandomForest / LinearRegression 基线） |
| `n_train` / `n_test` | 训练/测试样本数 |
| `MAE` / `RMSE` / `R2` / `MAPE` | 测试集误差指标 |

**展示**：在预测图旁以表格或指标卡呈现，并注明"测试集 = 最后 N 年，按时间切分"。

### 1.6 参考图（D 已生成，C 可直接复用或重绘）
- `results/cluster_selection.png`：K 选择曲线
- `results/cluster_profiles.png`：类别画像热力图

## 2. 关键约定（避免对接出错）
- **关联键**：城市名 `city` 与 A/B 使用同一字段，C 做地图时若用经纬度需自行维护 city→经纬度映射（D 不提供坐标）。
- **列名稳定**：以上列名由 `config.yaml` 的 `outputs` 固定，D 不会随意改名。
- **单位一致**：排放单位与 A 统一（万吨CO₂）；聚类特征多为无量纲，作图标题务必标注"已标准化/无量纲"。
- **未运行处理**：所有以"仅 --forecast"标注的文件缺失属正常，C 不应对其报错。
