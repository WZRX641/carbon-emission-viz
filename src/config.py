# src/config.py

import os
import pandas as pd

# ==========================================
# 全局路径配置
# ==========================================

# 数据清洗输出放 data/ 目录，统计分析 / 可视化 / 挖掘分析结果放 results/ 目录
# E 集成（2026-09-04）：支持环境变量覆盖，保证数据路径可配置：
#   CARBON_DATA_DIR    清洗数据目录（默认 data）
#   CARBON_RESULTS_DIR 统计/挖掘结果目录（默认 results）
DATA_DIR = os.environ.get('CARBON_DATA_DIR', 'data')
RESULTS_DIR = os.environ.get('CARBON_RESULTS_DIR', 'results')

# 数据清洗输出
CLEAN_CSV = os.path.join(DATA_DIR, 'carbonmonitor_clean.csv')

# ==========================================
# 统计分析 & 可视化配置 (原有配置保持不变)
# ==========================================
B_FILES = {
    'city_ranking': 'city_ranking.csv',
    'monthly_pattern': 'monthly_pattern.csv',
    'season_pattern': 'season_pattern.csv',
    'sector_structure': 'sector_structure.csv',
    'sector_yearly_trend': 'sector_yearly_trend.csv',
    'statistics_summary': 'statistics_summary.csv',
    'time_trend': 'time_trend.csv',
    'quality_summary': 'quality_summary.csv',
    'weekend_pattern': 'weekend_pattern.csv',
}

def load_b_data():
    """加载统计分析的全部统计结果。"""
    b_data = {}
    for key, fname in B_FILES.items():
        path = os.path.join(RESULTS_DIR, fname)
        try:
            b_data[key] = pd.read_csv(path)
        except (FileNotFoundError, pd.errors.EmptyDataError):
            b_data[key] = None
    return b_data

def get_b_metric(b_data, metric_name):
    """从 statistics_summary 中按名称取单个指标值"""
    df = b_data.get('statistics_summary')
    if df is None: return None
    hit = df.loc[df['metric'] == metric_name, 'value']
    return hit.iloc[0] if not hit.empty else None

# ==========================================
# 挖掘分析交付数据配置 (新增部分)
# ==========================================
# 城市聚类结果 (包含 lat, lon, cluster_name, total_emission)
D_CLUSTER_FILE = os.path.join(RESULTS_DIR, 'city_clusters.csv')

# 预测结果数据 (包含 date, city, split, y_true, y_pred)
D_FORECAST_FILE = os.path.join(RESULTS_DIR, 'forecast_results.csv')

# 聚类画像特征 (用于雷达图)
D_PROFILE_FILE = os.path.join(RESULTS_DIR, 'cluster_profiles.csv')

# 模型评估指标 (用于展示准确率)
D_METRICS_FILE = os.path.join(RESULTS_DIR, 'forecast_metrics.csv')

# ==========================================
# 视觉与单位规范 (保持不变)
# ==========================================
COLORS = {
    'primary': '#1f77b4',
    'secondary': '#ff7f0e',
    'background': '#f8f9fa',
    'card_bg': '#ffffff',
}

EMISSION_COLORSCALE = [
    [0, '#ffffcc'],
    [0.3, '#fd8d3c'],
    [1, '#e31a1c']
]

UNITS = {
    'total_emission': '千吨 CO₂ (kt CO₂)',
    'daily_avg': '千吨 CO₂/日',
    'percentage': '%',
}

SECTOR_NAME_CN = {
    'Aviation': '航空', 'Ground Transport': '地面交通', 'Industry': '工业',
    'Power': '电力', 'Residential': '居民部门',
}

SEASON_NAME_CN = {
    'Spring': '春季', 'Summer': '夏季', 'Autumn': '秋季', 'Winter': '冬季',
}

DAY_TYPE_NAME_CN = {
    'Weekday': '工作日', 'Weekend': '周末',
}

CITY_NAME_CN = {
    'Amsterdam': '阿姆斯特丹', 'Bangkok': '曼谷', 'Barcelona': '巴塞罗那', 'Beijing': '北京',
    'Berlin': '柏林', 'Bogota': '波哥大', 'Cape Town': '开普敦', 'Chengdu': '成都',
    'Chicago': '芝加哥', 'Chongqing': '重庆', 'Copenhagen': '哥本哈根', 'Hangzhou': '杭州',
    'Helsinki': '赫尔辛基', 'Houston': '休斯顿', 'Istanbul': '伊斯坦布尔', 'Jinan': '济南',
    'London': '伦敦', 'Los Angeles': '洛杉矶', 'Lyon': '里昂', 'Madrid': '马德里',
    'Marseille': '马赛', 'Melbourne': '墨尔本', 'Mexico City': '墨西哥城', 'Miami': '迈阿密',
    'Milan': '米兰', 'Moscow': '莫斯科', 'Munich': '慕尼黑', 'Nanjing': '南京',
    'New Delhi': '新德里', 'New York': '纽约', 'Nice': '尼斯', 'Osaka': '大阪',
    'Oslo': '奥斯陆', 'Paris': '巴黎', 'Qingdao': '青岛', 'Rome': '罗马',
    'San Francisco': '旧金山', 'Santiago': '圣地亚哥', 'Seattle': '西雅图', 'Seoul': '首尔',
    'Shanghai': '上海', 'Stockholm': '斯德哥尔摩', 'Sydney': '悉尼', 'Tokyo': '东京',
    'Washington': '华盛顿',
}

CITY_LAT_LON = {
    'Amsterdam': [52.37, 4.89], 'Bangkok': [13.76, 100.50], 'Barcelona': [41.39, 2.16],
    'Beijing': [39.90, 116.40], 'Berlin': [52.52, 13.40], 'Bogota': [4.71, -74.07],
    'Cape Town': [-33.92, 18.42], 'Chengdu': [30.57, 104.07], 'Chicago': [41.88, -87.63],
    'Chongqing': [29.43, 106.91], 'Copenhagen': [55.68, 12.57], 'Hangzhou': [30.27, 120.15],
    'Helsinki': [60.17, 24.94], 'Houston': [29.76, -95.37], 'Istanbul': [41.01, 28.98],
    'Jinan': [36.65, 117.12], 'London': [51.51, -0.13], 'Los Angeles': [34.05, -118.24],
    'Lyon': [45.76, 4.84], 'Madrid': [40.42, -3.70], 'Marseille': [43.30, 5.37],
    'Melbourne': [-37.81, 144.96], 'Mexico City': [19.43, -99.13], 'Miami': [25.76, -80.19],
    'Milan': [45.46, 9.19], 'Moscow': [55.76, 37.62], 'Munich': [48.14, 11.58],
    'Nanjing': [32.06, 118.78], 'New Delhi': [28.61, 77.23], 'New York': [40.71, -74.01],
    'Nice': [43.71, 7.27], 'Osaka': [34.69, 135.50], 'Oslo': [59.91, 10.75],
    'Paris': [48.86, 2.35], 'Qingdao': [36.07, 120.38], 'Rome': [41.90, 12.50],
    'San Francisco': [37.77, -122.42], 'Santiago': [-33.45, -70.66], 'Seattle': [47.61, -122.33],
    'Seoul': [37.57, 126.98], 'Shanghai': [31.23, 121.47], 'Stockholm': [59.33, 18.07],
    'Sydney': [-33.87, 151.21], 'Tokyo': [35.68, 139.69], 'Washington': [38.91, -77.04],
}

CITY_COUNTRY = {
    'Amsterdam': 'Netherlands', 'Bangkok': 'Thailand', 'Barcelona': 'Spain', 'Beijing': 'China',
    'Berlin': 'Germany', 'Bogota': 'Colombia', 'Cape Town': 'South Africa', 'Chengdu': 'China',
    'Chicago': 'United States', 'Chongqing': 'China', 'Copenhagen': 'Denmark', 'Hangzhou': 'China',
    'Helsinki': 'Finland', 'Houston': 'United States', 'Istanbul': 'Turkey', 'Jinan': 'China',
    'London': 'United Kingdom', 'Los Angeles': 'United States', 'Lyon': 'France', 'Madrid': 'Spain',
    'Marseille': 'France', 'Melbourne': 'Australia', 'Mexico City': 'Mexico', 'Miami': 'United States',
    'Milan': 'Italy', 'Moscow': 'Russia', 'Munich': 'Germany', 'Nanjing': 'China',
    'New Delhi': 'India', 'New York': 'United States', 'Nice': 'France', 'Osaka': 'Japan',
    'Oslo': 'Norway', 'Paris': 'France', 'Qingdao': 'China', 'Rome': 'Italy',
    'San Francisco': 'United States', 'Santiago': 'Chile', 'Seattle': 'United States', 'Seoul': 'South Korea',
    'Shanghai': 'China', 'Stockholm': 'Sweden', 'Sydney': 'Australia', 'Tokyo': 'Japan',
    'Washington': 'United States',
}
# 注：挖掘分析文件路径统一定义在上方「挖掘分析交付数据配置」区块（跟随 RESULTS_DIR），
# 此处原重复定义已由集成与测试在整合时清理。