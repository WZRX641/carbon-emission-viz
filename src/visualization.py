import plotly.express as px
import pandas as pd
import plotly.graph_objects as go
from src.config import D_CLUSTER_FILE, D_FORECAST_FILE, D_PROFILE_FILE, D_METRICS_FILE
from src.config import (
    EMISSION_COLORSCALE, CITY_NAME_CN, UNITS,
    SECTOR_NAME_CN, SEASON_NAME_CN, DAY_TYPE_NAME_CN,
)


# ===== 1. 地图 (plotly 点图 + 渐变颜色条 + 数值刻度) =====
def create_map(df, color_col='total_emission'):
    """生成全球城市排放地图（plotly 点图）。
    城市用原点点标记, 颜色=排放量(对数渐变: 浅黄->深红), 图例为渐变颜色条+数值刻度。
    """
    import numpy as np
    import plotly.graph_objects as go

    agg = df.groupby('city').agg(
        total_emission=('total_emission', 'sum'),
        daily_avg=('daily_avg', 'mean'),
        lat=('lat', 'first'),
        lon=('lon', 'first'),
    ).reset_index()
    if agg.empty:
        return None

    agg['city_display'] = agg['city'].map(CITY_NAME_CN)

    # 排放值 -> 对数映射 (拉开低值城市层次)
    vals = agg[color_col].astype(float).clip(lower=1.0)
    log_vals = np.log10(vals)

    # 渐变颜色条刻度数值 (真实排放量, 千吨)
    tick_real = np.array([1e4, 3e4, 1e5, 3e5, 1e6, 4e6])
    tick_real = tick_real[(tick_real >= vals.min()) & (tick_real <= vals.max())]
    tick_log = np.log10(tick_real)
    tick_text = [f'{t/1e4:.0f}万' if t >= 1e4 else f'{t:.0f}' for t in tick_real]

    fig = go.Figure(go.Scattergeo(
        lat=agg['lat'],
        lon=agg['lon'],
        mode='markers',
        text=agg['city_display'],
        customdata=agg[['daily_avg']],
        hovertemplate=(
            '<b>%{text}</b><br>'
            f'排放量：%{{marker.color:,.0f}} 千吨 CO₂<br>'
            '日均排放：%{customdata[0]:,.1f} 千吨 CO₂/日'
            '<extra></extra>'
        ),
        marker=dict(
            size=agg['total_emission'].pipe(lambda s: 6 + 34 * (s / s.max())),
            color=log_vals,
            colorscale=[
                [0.0, '#fff3b0'],
                [0.25, '#ffd66b'],
                [0.5, '#ff9f3c'],
                [0.75, '#eb5e14'],
                [1.0, '#a81d00'],
            ],
            showscale=True,
            colorbar=dict(
                title=f'排放量（{UNITS[color_col]}）',
                tickvals=list(tick_log),
                ticktext=tick_text,
                tickfont=dict(size=11),
                titlefont=dict(size=11),
                len=0.8,
                thickness=16,
            ),
        ),
    ))

    fig.update_geos(projection_type='natural earth')
    fig.update_layout(
        height=450,
        margin=dict(l=0, r=0, t=40, b=0),
        hovermode='closest',
    )
    return fig


# ===== 2. 趋势图（多城市对比）=====
def create_trend(df, cities=None):
    """生成时间趋势图，支持多城市对比；不传城市则画所选范围合计"""
    if cities and len(cities) > 0:
        df_plot = df[df['city'].isin(cities)].copy()
        df_plot['city_display'] = df_plot['city'].map(CITY_NAME_CN)
        title = '多城市排放趋势对比'
        color_col = 'city_display'
    else:
        df_plot = df.groupby('year')['total_emission'].sum().reset_index()
        df_plot['city_display'] = '所选城市合计'
        title = '总排放趋势（所选城市合计）'
        color_col = None

    if df_plot.empty:
        return None

    fig = px.line(
        df_plot,
        x='year',
        y='total_emission',
        color=color_col if color_col else None,
        title=title,
        labels={'total_emission': f'排放量（{UNITS["total_emission"]}）', 'year': '年份'},
        markers=True,
    )
    fig.update_layout(height=450, legend_title_text='城市')
    return fig


# ===== 3. 排名图 =====
def create_ranking(df, top_n=15, color_col='total_emission'):
    """生成城市排名图（基于所选年份范围聚合，支持总排放 / 日均排放切换）"""
    agg = df.groupby('city').agg(
        total_emission=('total_emission', 'sum'),
        daily_avg=('daily_avg', 'mean'),
    ).reset_index()
    if agg.empty:
        return None

    df_rank = agg.sort_values(color_col, ascending=False).head(top_n).copy()
    df_rank['city_display'] = df_rank['city'].map(CITY_NAME_CN)

    label_map = {
        'total_emission': f'排放量（{UNITS["total_emission"]}）',
        'daily_avg': f'日均排放（{UNITS["daily_avg"]}）',
    }
    kind = '日均排放' if color_col == 'daily_avg' else '排放'

    fig = px.bar(
        df_rank,
        x=color_col,
        y='city_display',
        orientation='h',
        title=f'城市{kind}排名（前{top_n} · 所选年份范围）',
        labels={color_col: label_map.get(color_col, color_col), 'city_display': '城市'},
        color=color_col,
        color_continuous_scale=EMISSION_COLORSCALE,
        text_auto=True,
    )
    fig.update_layout(height=450, margin=dict(l=0, r=0, t=40, b=0))
    return fig


# ===== 4. 分布图（箱线图）=====
def create_distribution(df):
    """生成城市排放分布箱线图（基于所选年份范围聚合）"""
    agg = df.groupby('city').agg(total_emission=('total_emission', 'sum')).reset_index()
    if agg.empty:
        return None

    fig = px.box(
        agg,
        y='total_emission',
        points='all',
        title='城市排放分布（所选年份范围）',
        labels={'total_emission': f'排放量（{UNITS["total_emission"]}）'},
        color_discrete_sequence=['#1f77b4'],
    )
    fig.update_layout(height=400)
    return fig


# ===== 5. 热力图（城市×年份）=====
def create_heatmap(df, cities=None, top_n=20):
    """生成城市×年份排放热力图；不传城市时取累计排放前N名"""
    if cities:
        df_plot = df[df['city'].isin(cities)].copy()
    else:
        top_cities = df.groupby('city')['total_emission'].sum().nlargest(top_n).index.tolist()
        df_plot = df[df['city'].isin(top_cities)].copy()

    if df_plot.empty:
        return None

    pivot = df_plot.pivot_table(
        index='city',
        columns='year',
        values='total_emission',
        aggfunc='sum',
    )
    pivot.index = [CITY_NAME_CN.get(c, c) for c in pivot.index]

    fig = px.imshow(
        pivot,
        title='城市×年份排放热力图',
        labels=dict(x='年份', y='城市', color=f'排放量（{UNITS["total_emission"]}）'),
        color_continuous_scale='Reds',
        aspect='auto',
    )
    fig.update_layout(height=500)
    return fig


# ===== 6. 结构饼图（通用）=====
def create_pie(df_group, title):
    """通用结构饼图。df_group 需含两列：name（类别名）、value（排放量）。
    部门结构、国家/区域结构均可复用。"""
    if df_group is None or df_group.empty or df_group['value'].sum() <= 0:
        return None

    df_group = df_group.sort_values('value', ascending=False).copy()

    fig = px.pie(
        df_group,
        values='value',
        names='name',
        title=title,
        hole=0.3,
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig.update_traces(
        textinfo='percent+label',
        hovertemplate='%{label}: %{value:,.0f} (%{percent})<extra></extra>',
    )
    fig.update_layout(height=400)
    return fig


# ===== 7. 月度规律（统计分析 monthly_pattern.csv）=====
def create_monthly_pattern(df_month):
    """月度排放规律折线图"""
    if df_month is None or df_month.empty:
        return None

    df_plot = df_month.copy().sort_values('month')
    df_plot['月份'] = df_plot['month'].map(lambda m: f'{int(m)}月')

    fig = px.line(
        df_plot,
        x='月份',
        y='avg_daily_emissions',
        title='月度排放规律（全样本月均值）',
        labels={'avg_daily_emissions': '平均单日排放（千吨 CO₂）', '月份': '月份'},
        markers=True,
    )
    fig.update_layout(height=380)
    return fig


# ===== 8. 季节规律（统计分析 season_pattern.csv）=====
def create_season_pattern(df_season):
    """季节排放规律柱状图"""
    if df_season is None or df_season.empty:
        return None

    df_plot = df_season.copy()
    df_plot['季节'] = df_plot['season'].map(lambda s: SEASON_NAME_CN.get(s, s))
    order = ['春季', '夏季', '秋季', '冬季']
    df_plot['季节'] = pd.Categorical(df_plot['季节'], categories=order, ordered=True)
    df_plot = df_plot.sort_values('季节')

    fig = px.bar(
        df_plot,
        x='季节',
        y='value',
        title='季节排放规律（全样本季均值）',
        labels={'value': '平均单日排放（千吨 CO₂）', '季节': '季节'},
        color='季节',
        color_discrete_sequence=['#66c2a5', '#fc8d62', '#8da0cb', '#e78ac3'],
        text_auto=True,
    )
    fig.update_layout(height=380, showlegend=False)
    return fig


# ===== 9. 部门年度趋势（统计分析 sector_yearly_trend.csv）=====
def create_sector_yearly_trend(df_syt):
    """部门分年趋势折线图"""
    if df_syt is None or df_syt.empty:
        return None

    df_plot = df_syt.copy()
    df_plot['部门'] = df_plot['sector'].map(lambda s: SECTOR_NAME_CN.get(s, s))

    fig = px.line(
        df_plot,
        x='year',
        y='value',
        color='部门',
        title='部门排放年度趋势',
        labels={'value': f'排放量（{UNITS["total_emission"]}）', 'year': '年份'},
        markers=True,
    )
    fig.update_layout(height=380)
    return fig


# ===== 10. 工作日/周末规律（统计分析 weekend_pattern.csv，第二轮补齐）=====
def create_weekend_pattern(df_wk):
    """工作日/周末排放规律柱状图。
    口径：单城市单部门单日排放的均值（与 statistics_summary 的日均排放均值同口径）。"""
    if df_wk is None or df_wk.empty:
        return None
    df_plot = df_wk.copy()
    df_plot['日类型'] = df_plot['day_type'].map(lambda d: DAY_TYPE_NAME_CN.get(d, d))
    order = ['工作日', '周末']
    df_plot['日类型'] = pd.Categorical(df_plot['日类型'], categories=order, ordered=True)
    df_plot = df_plot.sort_values('日类型')
    fig = px.bar(
        df_plot,
        x='日类型',
        y='value',
        title='工作日 vs 周末排放规律（全样本）',
        labels={'value': '平均单日排放（千吨 CO₂）', '日类型': '日类型'},
        color='日类型',
        color_discrete_sequence=['#4d79c9', '#f28e2b'],
        text_auto='.2f',
    )
    fig.update_layout(height=380, showlegend=False)
    return fig
def create_cluster_map():
    """
    挖掘分析结果：城市碳排放聚类地图
    安全版：使用向量化操作提取坐标，杜绝类型报错
    """
    try:
        df = pd.read_csv(D_CLUSTER_FILE)

        # --- 核心修复：内置城市坐标字典 ---
        city_coords = {
            "Beijing": (39.9042, 116.4074), "Shanghai": (31.2304, 121.4737), "Guangzhou": (23.1291, 113.2644),
            "Shenzhen": (22.5431, 114.0579), "Chengdu": (30.5728, 104.0668), "Wuhan": (30.5928, 114.3055),
            "Tokyo": (35.6762, 139.6503), "Osaka": (34.6937, 135.5023), "Seoul": (37.5665, 126.9780),
            "Delhi": (28.6139, 77.2090), "Mumbai": (19.0760, 72.8777), "Bangkok": (13.7563, 100.5018),
            "Jakarta": (-6.2088, 106.8456), "Singapore": (1.3521, 103.8198),
            "London": (51.5074, -0.1278), "Paris": (48.8566, 2.3522), "Berlin": (52.5200, 13.4050),
            "Moscow": (55.7558, 37.6173), "Madrid": (40.4168, -3.7038), "Rome": (41.9028, 12.4964),
            "New York": (40.7128, -74.0060), "Los Angeles": (34.0522, -118.2437), "Chicago": (41.8781, -87.6298),
            "Houston": (29.7604, -95.3698), "Toronto": (43.6510, -79.3470), "Mexico City": (19.4326, -99.1332),
            "Sao Paulo": (-23.5505, -46.6333), "Buenos Aires": (-34.6037, -58.3816),
            "Sydney": (-33.8688, 151.2093), "Melbourne": (-37.8136, 144.9631),
            "Cairo": (30.0444, 31.2357), "Lagos": (6.5244, 3.3792), "Johannesburg": (-26.2041, 28.0473)
        }

        # --- 关键修复逻辑 ---
        # 只有当 CSV 里没有 lat/lon 列时，才执行匹配
        if 'lat' not in df.columns or 'lon' not in df.columns:
            # 1. 尝试根据城市名匹配坐标元组 (lat, lon)
            matched = df['city'].map(city_coords)
            
            # 2. 过滤掉没匹配上的城市（NaN），防止报错
            valid_mask = matched.notna()
            
            # 3. 安全地拆分纬度和经度
            df.loc[valid_mask, 'lat'] = matched[valid_mask].apply(lambda x: x[0])
            df.loc[valid_mask, 'lon'] = matched[valid_mask].apply(lambda x: x[1])

        # --- 绘图逻辑 ---
        # 只画有坐标的点，避免 Plotly 报错
        plot_df = df.dropna(subset=['lat', 'lon'])

        if plot_df.empty:
            return "未找到可识别的城市坐标，请检查 CSV 中的城市名是否为英文（如 Beijing, Tokyo）。"

        fig = px.scatter_geo(
            plot_df, 
            lat="lat", 
            lon="lon", 
            color="cluster_name",    
            size="total_emission",   
            hover_name="city",       
            hover_data=["cluster_name", "growth"], 
            title="全球城市碳排放聚类分布",
            projection="natural earth" 
        )
        
        fig.update_layout(height=600, margin={"r":0,"t":50,"l":0,"b":0})
        
        return fig
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"读取聚类数据失败: {str(e)}"
def create_forecast_trend(selected_city=None):
    """
    挖掘分析结果：未来排放预测趋势图
    已完全适配 results/forecast_results.csv 的真实结构：
        列: city / date / split / y_true / y_pred
        split='test'   历史验证段（真实值 + 预测值都有）
        split='future' 未来预测段（只有预测值，y_true 为空）
        数据中仅包含 5 个城市：Shanghai / Tokyo / Beijing / Chongqing / Los Angeles
    """
    # 1. 读取数据（文件不存在 / 损坏时给出明确提示，不再直接崩溃）
    try:
        df = pd.read_csv(D_FORECAST_FILE)
    except FileNotFoundError:
        return ('找不到预测数据文件：' + str(D_FORECAST_FILE) +
                '。请确认 forecast_results.csv 放在项目根目录下的 results 文件夹中。')
    except Exception as e:
        return f'预测数据读取失败：{str(e)}'

    if df.empty:
        return '预测数据文件为空，请先运行挖掘分析（预测）流程生成结果。'

    df['date'] = pd.to_datetime(df['date'])

    # 2. 关键修复：下拉框传入的城市如果不在预测数据里（比如华盛顿、阿姆斯特丹），
    #    自动切换到数据里第一个有预测结果的城市，保证图表一定能显示
    available_cities = df['city'].dropna().unique().tolist()
    fallback_note = ''
    if selected_city not in available_cities:
        if selected_city:
            first_cn = CITY_NAME_CN.get(available_cities[0], available_cities[0])
            fallback_note = f'（{selected_city} 暂无预测数据，已自动切换为：{first_cn}）'
        selected_city = available_cities[0]

    plot_df = df[df['city'] == selected_city].sort_values('date')
    city_cn = CITY_NAME_CN.get(selected_city, selected_city)

    # 3. 绘图：蓝色实线 = 真实观测值，红色虚线 = 模型预测值
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=plot_df['date'],
        y=plot_df['y_true'],
        mode='lines+markers',
        name='真实观测值',
        line=dict(color='#1f77b4', width=2),
        marker=dict(size=5),
    ))

    fig.add_trace(go.Scatter(
        x=plot_df['date'],
        y=plot_df['y_pred'],
        mode='lines+markers',
        name='模型预测值',
        line=dict(color='#e31a1c', width=2, dash='dash'),
        marker=dict(size=5),
    ))

    fig.update_layout(
        title=f'{city_cn} - 碳排放预测趋势{fallback_note}',
        xaxis_title='时间',
        yaxis_title=f'碳排放量（{UNITS["total_emission"]}）',
        height=420,
        legend=dict(orientation='h', yanchor='bottom', y=1.02),
        hovermode='x unified',
    )
    return fig