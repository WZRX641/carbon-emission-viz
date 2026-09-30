import os
import streamlit as st
import pandas as pd

from src.config import (
    CITY_LAT_LON, CITY_NAME_CN, CITY_COUNTRY, SECTOR_NAME_CN, UNITS,
    CLEAN_CSV, B_FILES, load_b_data,
)
from src.visualization import (
    create_map, create_trend, create_ranking,
    create_distribution, create_heatmap, create_pie,
    create_monthly_pattern, create_season_pattern, create_sector_yearly_trend,
    create_weekend_pattern, create_cluster_map, create_forecast_trend
)
# from src.visualization_blocks import create_global_blocks_map  # noqa: F401  (备用区块图，需 geopandas；页面用静态图时可不启用)
from src.config import D_CLUSTER_FILE, D_METRICS_FILE, D_FORECAST_FILE 

# 世界地图静态图路径 (与 app.py 同级)
_MAP_IMG = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'global_city_admin_map.png')
# 城市聚类分布静态图路径
_CLUSTER_MAP_IMG = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'global_cluster_map.png')
# ===== 页面设置 =====
st.set_page_config(page_title='全球城市碳排放分析', layout='wide')

st.title('全球城市碳排放分析仪表板')


# ===== 数据加载 =====
@st.cache_data
def load_clean_data():
    """加载清洗后的碳排放数据 (carbonmonitor_clean.csv)"""
    df = pd.read_csv(CLEAN_CSV)
    df['date'] = pd.to_datetime(df['date'])
    return df


df = load_clean_data()

# 兼容：第二轮补齐的清洗数据不含 country 列（上一版含），用城市到国家映射兜底
if 'country' not in df.columns:
    df['country'] = df['city'].map(CITY_COUNTRY).fillna('未知')
b_data = load_b_data()

# 页面副标题：数据规模与口径
q = b_data.get('quality_summary')
if q is not None:
    qr = q.iloc[0]
    st.caption(
        f'数据来源: Carbon Monitor Cities | {int(qr["cities"])}个城市 × {int(qr["sectors"])}个部门 | '
        f'{qr["date_min"]} ~ {qr["date_max"]} | 全部数据已接入'
    )
else:
    st.caption('数据来源: Carbon Monitor Cities | 全部数据已接入')

# ===== 侧边栏筛选 =====
city_name_en_map = {v: k for k, v in CITY_NAME_CN.items()}

with st.sidebar:
    st.header('筛选控制')

    # 1) 国家/区域 (大范围)
    all_countries = sorted(df['country'].unique())
    selected_countries = st.multiselect('国家 / 区域（留空 = 全部）', all_countries)

    # 2) 城市 (小范围, 受已选国家级联限制)
    if selected_countries:
        city_pool = df[df['country'].isin(selected_countries)]['city'].unique()
    else:
        city_pool = df['city'].unique()
    all_cities_cn = sorted(CITY_NAME_CN.get(c, c) for c in city_pool)
    selected_cities_cn = st.multiselect('城市（留空 = 全部）', all_cities_cn)
    selected_cities = [city_name_en_map.get(c, c) for c in selected_cities_cn]

    # 3) 部门
    all_sectors = sorted(df['sector'].unique())
    selected_sectors = st.multiselect(
        '部门（留空 = 全部5部门）', all_sectors,
        format_func=lambda s: SECTOR_NAME_CN.get(s, s),
    )

    y_min, y_max = int(df['year'].min()), int(df['year'].max())
    year_range = st.slider('年份范围', y_min, y_max, (y_min, y_max))

    metric_selected = st.selectbox('指标', ['总排放量', '日均排放'])
    metric_col = 'daily_avg' if metric_selected == '日均排放' else 'total_emission'

    st.divider()
    
    st.caption('提示：选择多个城市可对比趋势')

    missing = [B_FILES[k] for k in B_FILES if b_data.get(k) is None]
    if missing:
        st.warning('部分统计文件缺失: ' + ', '.join(missing))
    else:
        st.success(f'{len(B_FILES)}个统计文件已全部接入')
    st.divider() # 加个分割线好看点

# ===== 数据分析控制区 =====
st.sidebar.header("分析控制")

# 预测城市下拉框：只列出预测结果文件里真实存在的 5 个城市，
# 避免选到华盛顿、阿姆斯特丹等没有预测数据的城市
selected_city = None
try:
    forecast_cities = pd.read_csv(D_FORECAST_FILE)['city'].unique().tolist()
    selected_city = st.sidebar.selectbox(
        "选择预测城市",
        forecast_cities,
        format_func=lambda c: CITY_NAME_CN.get(c, c),  # 显示中文名
    )
except Exception as e:
    st.sidebar.warning(f"预测数据加载失败：{e}")

# 模型指标单独读取，任一文件出问题都不影响另一块
try:
    metrics_df = pd.read_csv(D_METRICS_FILE)
    if 'r2' in metrics_df.columns:
        st.sidebar.metric("模型平均准确率 (R²)", f"{metrics_df['r2'].mean():.2%}")
except Exception as e:
    st.sidebar.warning(f"模型指标加载失败：{e}")

# ===== 数据筛选与聚合 =====
mask = (df['year'] >= year_range[0]) & (df['year'] <= year_range[1])
if selected_cities:
    mask &= df['city'].isin(selected_cities)
if selected_countries:
    mask &= df['country'].isin(selected_countries)
if selected_sectors:
    mask &= df['sector'].isin(selected_sectors)
sub = df[mask]

if sub.empty:
    st.warning('当前筛选条件下无数据，请调整筛选项。')
    st.stop()

# 城市×年份聚合表（地图 / 趋势 / 排名 / 箱线图 / 热力图 共用）
ann = sub.groupby(['city', 'year']).agg(
    total_emission=('value', 'sum'),
    days=('date', 'nunique'),
).reset_index()
ann['daily_avg'] = ann['total_emission'] / ann['days']
ann['lat'] = ann['city'].map(lambda c: CITY_LAT_LON.get(c, [0, 0])[0])
ann['lon'] = ann['city'].map(lambda c: CITY_LAT_LON.get(c, [0, 0])[1])

# ===== 指标卡片 =====
st.subheader('关键指标')
col1, col2, col3, col4, col5 = st.columns(5)

city_count = int(ann['city'].nunique())
total_emission = float(ann['total_emission'].sum())
daily_avg_all = float(sub['value'].sum() / sub['date'].nunique())
yearly_sum = ann.groupby('year')['total_emission'].sum()
peak_year = int(yearly_sum.idxmax())
max_city = ann.groupby('city')['total_emission'].sum().idxmax()
max_city_cn = CITY_NAME_CN.get(max_city, max_city)

col1.metric('城市数', city_count)
col2.metric('总排放量', f'{total_emission:,.0f} {UNITS["total_emission"]}')
col3.metric('日均排放（整体）', f'{daily_avg_all:,.1f} {UNITS["daily_avg"]}')
col4.metric('排放峰值年', peak_year)
col5.metric('最大排放城市', max_city_cn)

# ===== 图表区 =====
st.subheader('数据可视化')


def show_chart(fig):
    """统一渲染：无数据时给出占位提示"""
    if fig is not None:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info('当前筛选条件下无数据')


# 第一行：地图 + 趋势
col_left, col_right = st.columns([3, 2])
with col_left:
    # 世界地图: 全球城市排放图 (plotly 点图, 颜色=排放, 渐变颜色条+数值刻度)
    show_chart(create_map(ann, color_col=metric_col))
    st.caption('全球45城真实位置; 圆点越大排放越高, 颜色深浅代表排放量; 悬停查看详情')
with col_right:
    show_chart(create_trend(ann, selected_cities if selected_cities else None))

# 第二行：排名 + 分布
col_left, col_right = st.columns(2)
with col_left:
    show_chart(create_ranking(ann, top_n=15, color_col=metric_col))
with col_right:
    show_chart(create_distribution(ann))

# 第三行：热力图 + 结构图
st.subheader('高级分析')
col_left, col_right = st.columns(2)

with col_left:
    show_chart(create_heatmap(ann, selected_cities if selected_cities else None))

with col_right:
    tab_sec, tab_cou = st.tabs(['部门结构', '国家 / 区域结构'])
    with tab_sec:
        sec = sub.groupby('sector')['value'].sum().reset_index()
        sec['name'] = sec['sector'].map(lambda s: SECTOR_NAME_CN.get(s, s))
        show_chart(create_pie(sec[['name', 'value']], '部门排放结构（当前所选范围）'))
    with tab_cou:
        cou = sub.groupby('country')['value'].sum().sort_values(ascending=False)
        if len(cou) > 8:
            other_val = cou.iloc[8:].sum()
            cou = cou.head(8)
            if other_val > 0:
                cou = pd.concat([cou, pd.Series({'其他': other_val})])
        cou_df = cou.reset_index()
        cou_df.columns = ['name', 'value']
        show_chart(create_pie(cou_df, '国家/区域排放结构（当前所选范围，前8+其他）'))

# ===== 时间规律与部门结构 =====
st.divider()
st.subheader('时间规律与部门结构')

# 四张规律图
charts_b = [
    ('monthly_pattern', create_monthly_pattern),
    ('season_pattern', create_season_pattern),
    ('weekend_pattern', create_weekend_pattern),
    ('sector_yearly_trend', create_sector_yearly_trend),
]
r1_left, r1_right = st.columns(2)
r2_left, r2_right = st.columns(2)
for col, (key, fn) in zip([r1_left, r1_right, r2_left, r2_right], charts_b):
    with col:
        df_b = b_data.get(key)
        if df_b is None:
            st.info(f'统计文件缺失: {B_FILES[key]}')
        else:
            show_chart(fn(df_b))

# 工作日/周末规律摘要
wk = b_data.get('weekend_pattern')
if wk is not None and {'is_weekend', 'value'} <= set(wk.columns) and len(wk) == 2:
    v_wd = float(wk.loc[wk['is_weekend'] == 0, 'value'].iloc[0])
    v_we = float(wk.loc[wk['is_weekend'] == 1, 'value'].iloc[0])
    pct = (v_we - v_wd) / v_wd * 100
    diff_word = '低' if pct <= 0 else '高'
    st.caption(
        f'工作日 vs 周末：工作日平均 {v_wd:.2f}，周末 {v_we:.2f}（千吨 CO₂），'
        f'周末较工作日{diff_word}约 {abs(pct):.1f}%（口径：单城市单部门单日排放均值）'
    )

# 排名表 + 关键统计
col_left, col_right = st.columns(2)

with col_left:
    st.markdown('**城市排放排名（按累计排放，前15）**')
    cr = b_data.get('city_ranking')
    if cr is None:
        st.info('统计文件缺失: city_ranking.csv')
    else:
        cr_show = cr.head(15).copy()
        cr_show['城市'] = cr_show['city'].map(lambda c: CITY_NAME_CN.get(c, c))
        cr_show = cr_show.rename(columns={
            'rank_by_total': '排名',
            'total_emissions': '累计排放',
            'avg_emissions': '单部门日均值',
            'peak_emissions': '峰值日排放',
            'volatility_cv': '波动系数',
        })
        cr_show['累计排放'] = cr_show['累计排放'].round(0)
        cr_show['单部门日均值'] = cr_show['单部门日均值'].round(2)
        cr_show['峰值日排放'] = cr_show['峰值日排放'].round(2)
        cr_show['波动系数'] = cr_show['波动系数'].round(2)
        cr_show = cr_show[['排名', '城市', '累计排放', '单部门日均值', '峰值日排放', '波动系数']]
        st.dataframe(cr_show, hide_index=True, use_container_width=True)
        st.caption('单位：千吨 CO₂；“单部门日均值”为该城市各部门单日排放的均值')

with col_right:
    st.markdown('**全局关键统计**')
    ss = b_data.get('statistics_summary')
    if ss is None:
        st.info('统计文件缺失: statistics_summary.csv')
    else:
        st.dataframe(ss, hide_index=True, use_container_width=True)

with st.expander('数据质量报告与口径说明'):
    qs = b_data.get('quality_summary')
    if qs is None:
        st.info('统计文件缺失: quality_summary.csv')
    else:
        qs_show = qs.T.reset_index()
        qs_show.columns = ['字段', '值']
        qs_show['值'] = qs_show['值'].astype(str)
        st.dataframe(qs_show, hide_index=True, use_container_width=True)
    st.caption(
        '口径说明：原始 value 为单日排放，单位千吨 CO₂（Carbon Monitor Cities 官方口径）；'
        '本页面“日均排放”= 城市年总量 / 数据天数，与排名表中的“单部门日均值”口径不同，请注意区分。'
        '月度/季节/周末规律图的数值为单城市单部门单日排放的均值（与关键统计的“日均排放均值”同口径）。'
    )

# ===== 聚类与预测区域 =====
st.divider()
st.subheader("聚类与预测")

# 使用 Tabs 分页展示内容
tab_cluster, tab_forecast = st.tabs(["🏙️ 城市聚类画像", "📈 未来排放预测"])

with tab_cluster:
    st.header("城市聚类分布")
    # plotly 点图: 城市在原点点标记, 颜色=聚类类别
    cluster_fig = create_cluster_map()
    if isinstance(cluster_fig, str):
        st.error(cluster_fig)
    else:
        st.plotly_chart(cluster_fig, use_container_width=True)
    st.info("💡 说明：不同颜色代表不同的排放模式聚类类别（蓝=低排放稳波动增长型, 橙=低排放高波动强季节, 红=高排放稳波动下降/平稳型）；圆点越大排放总量越高")

with tab_forecast:
    st.header("未来排放趋势")
    forecast_fig = create_forecast_trend(selected_city)
    if isinstance(forecast_fig, str):
        st.error(forecast_fig)
    else:
        st.plotly_chart(forecast_fig, use_container_width=True)
    
    st.caption(f"当前展示城市：{selected_city} | 红色虚线为模型预测值")

# ===== 页脚 =====
st.divider()
st.caption('全球城市碳排放数据分析及可视化 | 数据来源: Carbon Monitor Cities')