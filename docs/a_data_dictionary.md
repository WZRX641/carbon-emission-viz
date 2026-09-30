# 数据字典

| 字段 | 类型 | 含义 | 处理方式 |
|---|---|---|---|
| `city` | string | 城市名称 | 去除首尾空格，保留英文原名 |
| `date` | datetime | 观测日期 | 原始格式为 `DD/MM/YYYY`，统一为 `YYYY-MM-DD` |
| `year` | int | 年份 | 从 `date` 派生 |
| `month` | int | 月份 | 从 `date` 派生，范围1-12 |
| `day` | int | 月内日期 | 从 `date` 派生，范围1-31 |
| `sector` | string | 排放部门 | 去除首尾空格，保留原分类 |
| `value` | float | 碳排放观测值 | 转为数值型，单位沿用原始数据说明 |

## 观测单位
`value` 的单位沿用 Carbon Monitor Cities 原始数据。当前文件包含45个城市、5个部门，日期范围覆盖 2019-01-01 至 2026-07-31。

## 原始字段说明
原始CSV还包含 `Unnamed: 4`，该列全为空，是导出产生的空白列，清洗时删除。

## 分类值
当前文件包含45个城市和5个部门：Aviation、Ground Transport、Industry、Power、Residential。
