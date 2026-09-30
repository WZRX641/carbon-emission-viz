# 集成测试报告（集成与测试模块）

- 测试日期：2026-09-04
- 测试环境：Windows 11 / Python 3.13 / pandas 2.3 / scikit-learn 1.7 / Streamlit 1.5
- 执行人：E（系统集成）
- 结论：**31 个测试全部通过**；端到端管线在真实数据上复现成功，输出与 A-D 原交付逐位一致。

## 1. 测试范围

| 测试文件 | 数量 | 覆盖内容 |
|---|---|---|
| `tests/test_data_quality.py` | 4 | 字段检查（缺列拒绝）、空值处理（空 city/value/非法日期丢弃、去重、去首尾空格）、时间派生字段、真实清洗数据质量 |
| `tests/test_statistics.py` | 5 | B 统计结果非空（9 个文件）、城市排名降序、部门占比合计 100%、页面 load_b_data 读齐全部文件、真实 results/ 非空 |
| `tests/test_app_functions.py` | 9 | C 页面 13 个绘图函数、app 聚合口径复算（总排放=按日求和、日均=总量/天数）、45 城坐标/中文名/国家映射完整性、真实结果下聚类地图与预测曲线冒烟 |
| `tests/test_data_cleaning.py`（A 原有） | 2 | A 清洗逻辑基础测试 |
| `tests/test_mining.py`（D 原有） | 5 | 特征 schema、K 选择、聚类确定性、画像命名、预测冒烟 |
| `tests/test_integration.py`（D 原有） | 6 | D 交付物存在性、schema 契约、行数一致、预测文件、可重复性 |
| 合计 | **31** | |

## 2. 端到端复现测试

命令：`python run_pipeline.py`（原始数据 `data/raw/carbonmonitor-cities_datas_2026-09-03.csv`）

结果：
- 全流程约 80 秒完成，退出码 0；
- A：623,025 行清洗输出，45 城 × 5 部门，2019-01-01 ~ 2026-07-31；
- B：9 个统计文件全部生成；
- D：K=3（轮廓系数 0.502 最大），45 城聚类 + 5 城预测；
- 完整性校验：页面所需 14 个文件全部生成 ✔。

**一致性核对**（重新生成 vs A-D 原交付包）：
- `city_ranking.csv`：与 B 原交付**逐位一致**（如 Shanghai 4,020,667.31 / Tokyo 1,420,267.04）；
- `city_clusters.csv`：与 D 原交付**逐位一致**（如 Amsterdam level=35.6778, cluster=0）；
- `forecast_metrics.csv`：与 D 原交付一致（Los Angeles RF R²=0.9937）。

## 3. 页面人工验收

`streamlit run app.py` 启动后逐区检查（截图见 `screenshots/`）：

| 区域 | 结果 |
|---|---|
| 关键指标卡（5 项） | ✔ 正常显示，数值与统计结果一致 |
| 地图 / 趋势 / 排名 / 箱线图 | ✔ 正常渲染 |
| 热力图 / 部门结构 / 国家结构 | ✔ 正常渲染 |
| 统计分析任务包结果（4 图 + 2 表 + 质量报告） | ✔ 9 个文件全部接入提示正常 |
| 挖掘分析任务包聚类地图（3 类着色） | ✔ 正常渲染 |
| 挖掘分析任务包预测曲线 + 模型 R² | ✔ 侧栏平均 R² 正常，预测城市下拉仅含 5 个有数据城市 |
| 侧边栏筛选（城市/国家/部门/年份/指标） | ✔ 联动正常 |

## 4. 发现的接口问题与处理

| # | 问题 | 处理 |
|---|---|---|
| 1 | A 的 `data_cleaning.py` 用扁平导入 `from data_loader import load_many`，放入统一 src 包后导入失败 | 改为 try 相对导入 / 回退扁平导入，两种运行方式均兼容 |
| 2 | B 的 `statistics_analysis.py` 写死 `../data`、`../results` 相对路径，只能在 src/ 目录下运行 | 重构为参数化模块（`--input/--output/--docs`），统计逻辑与输出文件名零改动 |
| 3 | D 的 `ingest_a.py` 默认输入指向项目外部目录（A 交付包平级位置），新环境不存在 | 默认输入改为统一管线产物 `data/carbonmonitor_clean.csv` |
| 4 | 页面从 `results/quality_summary.csv` 读取质量摘要，但 A 清洗输出到 `data/` | run_pipeline.py 显式桥接复制，并在 README/代码注释中说明口径 |
| 5 | 可视化模块的 `src/config.py` 末尾存在挖掘分析路径的重复定义（写死 `results/`） | 清理重复块，统一跟随 `RESULTS_DIR`（支持环境变量覆盖） |
| 6 | 城市→国家映射表在 D 原包位于 `data/processed/`，E 统一放 `data/` 根 | utils.py 兼容两个位置，优先 `data/city_country_map.csv` |

## 5. 失败项记录

| 日期 | 现象 | 原因 | 处理 | 状态 |
|---|---|---|---|---|
| 2026-09-04 | `test_clean_handles_nulls_and_invalid` 断言 `rows_after==2` 失败（实际 3） | E 编写测试时对样例无效行数计算有误：5 行样例中仅 2 行无效（空城市行、非法日期行），并非 3 行 | 修正测试断言为 `rows_after==3, dropped_rows==2`；**被测代码（A 清洗逻辑）无问题**，用例数据本身验证了正确行为 | 已修复，复测通过 |

## 6. 遗留风险

- Streamlit/Plotly 大版本升级可能改变 DOM 结构，但不影响数据链路；
- 预测为统计外推（测试集 R² 0.57~0.99），不可作为政策依据（D 文档已声明）；
- `data/raw/` 原始数据约 28 MB，按提交要求不打包，评分环境需按 README 自行下载（官网数据会滚动更新，若文件名/覆盖期变化，管线仍可运行，结论数值可能随数据更新略变）。
