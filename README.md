# 全球城市碳排放分析与可视化

基于 Carbon Monitor Cities 公开数据（45 个全球城市 × 5 个排放部门 × 2019-01-01 ~ 2026-07-31，
共 623,025 条逐日记录）的清洗、统计分析、数据挖掘与交互式可视化一体化项目。

> 六人团队课程项目，按六个任务包分工：数据清洗 / 统计分析 / 可视化 / 挖掘分析 /
> 集成与测试 / 文档与答辩。本仓库为集成与测试、文档与答辩两个任务包整合后的统一交付，
> 已合并数据清洗、统计分析、可视化、挖掘分析四个模块的全部成果。

## 一、项目结构

```
全球城市碳排放分析与可视化/
├── app.py                  # C: Streamlit 可视化页面入口（静态渐变地图版）
├── app_interactive.py      # C: 交互版页面（世界地图用 plotly 圆点图 + 渐变颜色条）
├── run_pipeline.py         # E: 一键全流程（A清洗 → B统计 → D挖掘/预测 → 完整性校验）
├── config.yaml             # E: 统一配置（所有数据路径可配置，无绝对路径）
├── requirements.txt        # E: 合并后的依赖清单
├── conftest.py             # E: pytest 根配置
├── global_city_admin_map.png  # 全球城市行政区区块地图（静态渐变颜色条）
├── global_cluster_map.png     # 全球城市聚类分布地图（3 类排放模式）
├── src/
│   ├── data_loader.py      # A: 原始数据读取与字段校验
│   ├── data_cleaning.py    # A: 数据清洗（空值/重复/非法值处理 + 质量摘要）
│   ├── statistics_analysis.py  # B: 基础统计（时间规律/城市排名/部门结构等 9 个结果文件）
│   ├── visualization.py    # C: Plotly 图表（13 个绘图函数）
│   ├── visualization_blocks.py  # C: 行政区区块地图生成（备用）
│   ├── config.py           # C: 页面配置（路径可环境变量覆盖 + 45 城坐标/中文映射）
│   ├── ingest_a.py         # D: A→D 数据对接桥（value→co2_emission、部门汇总、country 回填）
│   ├── mining_analysis.py  # D: K-Means 聚类 + RandomForest 预测
│   ├── sample_data.py      # D: 合成样例数据（无真实数据时的框架自测）
│   └── utils.py            # D: 配置加载、接口契约校验
├── data/
│   ├── raw/                # 原始数据（需自行下载，见 data/README.md，不打包）
│   ├── carbonmonitor_clean.csv      # A 清洗输出，已随包附带（页面开箱即用）
│   ├── processed/clean_data.csv     # D 统一输入（中间数据，不打包）
│   └── city_country_map.csv         # A 提供的城市→国家映射表
├── results/                # B/D 全部结果 CSV（可由 run_pipeline.py 重新生成）
├── docs/                   # 各模块文档 + E 集成测试报告
├── screenshots/            # 页面真实运行截图
└── tests/                  # 31 个测试（字段检查/空值处理/统计非空/页面核心函数/集成）
```

## 二、环境创建与依赖安装

要求 Python ≥ 3.10。

```bash
# 1) 创建并激活虚拟环境
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

# 2) 安装依赖
python -m pip install -r requirements.txt
```

## 三、数据下载与放置

数据源：**Carbon Monitor Cities**（https://cities.carbonmonitor.org/）

1. 进入官网 → Download → 下载城市日度排放 CSV（本组使用文件：
   `carbonmonitor-cities_datas_2026-09-03.csv`，下载日期 2026-09-03，
   覆盖 2019-01-01 ~ 2026-07-31，45 城 5 部门）；
2. 将下载的 CSV 放入项目 `data/raw/` 目录；
3. 也可以把文件放在任意位置，运行时用 `--input` 指定路径。

> 原始数据约 28 MB，按提交要求**不打包**在代码压缩包中，需按上述步骤自行下载。

## 四、运行命令

### 方式一：端到端一键运行（推荐）

```bash
python run_pipeline.py
```

该命令依次执行：

| 步骤 | 模块 | 输入 | 输出 |
|---|---|---|---|
| 1 | A 数据清洗 | `data/raw/` | `data/carbonmonitor_clean.csv`、`results/quality_summary.csv` |
| 2 | B 基础统计 | `data/raw/` | `results/` 下 9 个统计 CSV |
| 3 | D 数据对接 | `data/carbonmonitor_clean.csv` | `data/processed/clean_data.csv` |
| 4 | D 聚类+预测 | `data/processed/clean_data.csv` | `results/city_clusters.csv`、`forecast_results.csv` 等 |
| 5 | E 完整性校验 | — | 页面所需 14 个文件全部就绪 |

真实运行结果（2026-09-04，本机执行）：全流程约 80 秒完成，
输出「全部 14 个页面所需文件均已生成 ✔」。

常用参数：

```bash
python run_pipeline.py --input 路径/你的数据.csv   # 指定原始数据位置
python run_pipeline.py --no-forecast              # 关闭预测（仅聚类）
python run_pipeline.py --skip-b                   # 跳过 B 统计（调试用）
```

### 方式二：分模块单独运行

```bash
# A：数据清洗
python -m src.data_cleaning --input data/raw --output data

# B：基础统计
python -m src.statistics_analysis --input data/raw --output results --docs docs

# D：A→D 对接 + 挖掘
python -m src.ingest_a
python -m src.mining_analysis --forecast

# 页面
streamlit run app.py            # 静态版（世界地图：行政区区块图 + 渐变颜色条）
streamlit run app_interactive.py  # 交互版（世界地图：plotly 圆点图 + 渐变颜色条）
```

### 启动可视化页面

提供两个页面入口（内容一致，仅世界地图呈现方式不同）：

```bash
# 版本一：静态渐变地图版（推荐，无 geopandas 依赖）
streamlit run app.py

# 版本二：交互圆点地图版（plotly 圆点，点大小=排放量，悬停看城市详情）
streamlit run app_interactive.py
```

浏览器自动打开 `http://localhost:8501`（若 8501 被占用，Streamlit 会自动换端口）。页面包含：

- **关键指标卡**：城市数、总排放量、日均排放、排放峰值年、最大排放城市；
- **数据可视化**：全球碳排放地图（渐变颜色条，浅黄→深红按对数映射排放量）、总排放趋势折线、城市排放排名、分布箱线图；
- **高级分析（静态版）**：月度规律、季节规律、工作日/周末对比、部门年度趋势、城市×年份热力图、部门/国家结构饼图；
- **聚类与预测**：城市聚类地图（3 类排放模式）与 5 个代表城市的未来排放预测曲线（含模型 R²）。

> 页面用的行政区块地图/聚类分布图为项目预生成的 `.png`（`global_city_admin_map.png`、
> `global_cluster_map.png`），位于项目根目录，页面直接读取显示，无需额外依赖。

页面截图见 `screenshots/`（均为真实运行截图）。

## 五、数据路径配置

所有路径集中在根目录 `config.yaml`，支持两种覆盖方式：

1. 改 `config.yaml`（`pipeline.raw_input` 等）；
2. 页面运行时用环境变量：

```bash
CARBON_DATA_DIR=我的数据目录 CARBON_RESULTS_DIR=我的结果目录 streamlit run app.py
```

## 六、运行测试

```bash
python -m pytest tests/ -v
```

当前状态：**31 个测试全部通过**（2026-09-04），覆盖：

- 字段检查与空值处理（`test_data_quality.py`）
- 统计结果非空与口径正确（`test_statistics.py`）
- 页面核心函数（`test_app_functions.py`：13 个绘图函数 + 聚合口径 + 45 城映射完整性）
- A/D 原有测试（`test_data_cleaning.py`、`test_mining.py`、`test_integration.py`）

集成测试详情（含一次失败项的处理记录）见 `docs/integration_test_report.md`。

## 七、结果说明

主要结论（详见 `docs/` 各模块文档与期末报告）：

- **数据质量**：62.3 万条记录零缺失、零重复、零非法值；
- **城市排名**：累计排放 Top3 为上海、东京、北京，上海约为第 2 名的 2.8 倍；
- **时间规律**：冬季（34.6）> 秋季 > 春季 > 夏季（28.7）；周末较工作日低约 3.7%；
- **部门结构**：工业 52.1% > 电力 19.6% > 居民 15.4% > 地面交通 10.4% > 航空 2.5%；
- **聚类（K=3）**：①低排放-稳波动-弱季节-增长型（30 城）；②低排放-高波动-强季节-下降/平稳型（14 城，多为欧洲供暖型城市）；③高排放-稳波动型（上海单独成类）；
- **预测**：RandomForest 对 5 个代表城市未来 12 个月排放预测，R² 0.57~0.99（洛杉矶最佳），均优于线性回归基线。

## 八、团队分工

| 成员 | 模块 | 职责 |
|---|---|---|
| A | 数据获取与清洗 | 数据下载、字段规范、数据字典、质量报告 |
| B | 基础统计 | 时间规律、城市排名、部门结构等统计分析 |
| C | 可视化 | Streamlit + Plotly 交互式平台 |
| D | 数据挖掘 | K-Means 聚类、RandomForest 预测 |
| E | 系统集成 | 项目整合、统一入口、测试、README、报告、答辩 |
