# data/ 目录说明

## 原始数据（data/raw/，不打包，需自行下载）

- 数据源：Carbon Monitor Cities
- 官网：https://cities.carbonmonitor.org/
- 下载路径：官网 → Download → 城市级日度排放数据
- 本组使用文件：`carbonmonitor-cities_datas_2026-09-03.csv`
- 下载日期：2026-09-03
- 文件规模：623,025 行（表头 1 行 + 数据 623,025 行）
- 覆盖范围：45 个全球城市 × 5 个排放部门 × 2019-01-01 ~ 2026-07-31 逐日数据
- 字段：`city, date, sector, value`（value 单位：千吨 CO₂/日，部门粒度）

下载后直接把 CSV 放入本目录（`data/raw/`），或运行时用
`python run_pipeline.py --input 你的路径` 指定。

## 清洗数据（中间产物，可重新生成）

| 文件 | 生成者 | 说明 |
|---|---|---|
| `carbonmonitor_clean.csv` | A（`src/data_cleaning.py`） | 规范化清洗输出：`city,date,sector,value,year,month,day` |
| `processed/clean_data.csv` | D（`src/ingest_a.py`） | D 挖掘统一输入：`city,country,date,year,month,co2_emission`（城市日总量） |

这两个文件运行 `python run_pipeline.py` 即可再生。

> **本交付包说明**：为使用户能直接运行可视化页面（无需先跑完整 pipeline），
> `carbonmonitor_clean.csv`（约 29 MB，压缩后约 4 MB）**已随交付包一并打包**（符合提交要求 ≤30M）。
> `processed/clean_data.csv`（D 挖掘中间数据）**不打包**，需要时运行 `python run_pipeline.py` 重新生成。

## 映射表

| 文件 | 来源 | 说明 |
|---|---|---|
| `city_country_map.csv` | A 提供 | 城市 → 国家权威映射（45 城），A 清洗输出缺 country 列时由 D 的 ingest_a 用于回填 |

## 单位与口径说明

- `value` / `co2_emission`：单日排放量，单位千吨 CO₂（kt CO₂），与 Carbon Monitor Cities 官方口径一致；
- B 统计的"日均排放均值"为「单城市单部门单日」粒度均值；页面"日均排放"为「城市年总量 / 数据天数」，两口径不同，详见页面口径说明。
