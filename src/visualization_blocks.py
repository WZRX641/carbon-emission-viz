# ============================================================
# 全球城市"行政区边界块"地图 (plotly 交互版)
# 用真实行政区边界块, 浅色底+灰色国家, 颜色=排放分档。
# 不在图上固定标注城市名, 改为鼠标悬停(hover)才显示 城市名/排放量/日均。
# ============================================================
import os
import numpy as np
import geopandas as gpd
import pandas as pd
import plotly.graph_objects as go

from src.config import CITY_NAME_CN, UNITS

_BASE = os.path.join(os.path.dirname(__file__), '..')
_BLOCK_FILE = os.path.join(_BASE, 'data', 'global_city_blocks.geojson')
_WORLD_FILE = os.path.join(_BASE, 'data', 'world.geojson')

_blocks_cache = None
_world_cache = None


def _load_blocks():
    global _blocks_cache
    if _blocks_cache is None:
        _blocks_cache = gpd.read_file(_BLOCK_FILE)
    return _blocks_cache


def _load_world():
    global _world_cache
    if _world_cache is None:
        _world_cache = gpd.read_file(_WORLD_FILE)
    return _world_cache


# 分档色 (明黄 -> 深红), 与桌面成品图一致
_PALETTE = ['#fff3b0', '#ffd66b', '#ff9f3c', '#eb5e14', '#a81d00']


def create_global_blocks_map(ann, year, color_col='total_emission'):
    """全球城市行政区边界块地图 (plotly choropleth)。

    - 用真实行政区边界(global_city_blocks), 城市不瓜分世界
    - 不在图面固定标注城市名; 鼠标悬停显示 城市名/排放量/日均
    - 浅色底 + 灰色国家边界, 城市块颜色=排放量分档
    ann: 城市x年份聚合表, 需含 city, total_emission, daily_avg
    """
    blocks = _load_blocks()
    world = _load_world()

    # 每城排放值: 多年则按城市求和
    city_em = ann.groupby('city')['total_emission'].sum().to_dict() if 'total_emission' in ann.columns else {}
    city_daily = ann.groupby('city')['daily_avg'].mean().to_dict() if 'daily_avg' in ann.columns else {}

    # 按排放排序 (大排放后画, 盖上面更醒目) & 列出有数据的城市
    cities = [c for c in blocks['city']]
    z = [city_em.get(c, 0.0) for c in cities]

    # 分档颜色
    em_all = np.array([city_em.get(c, 0.0) for c in cities], dtype=float)
    if em_all.max() > 0:
        q = np.quantile(em_all[em_all > 0] if (em_all > 0).any() else em_all, [0.2, 0.4, 0.6, 0.8])
    else:
        q = np.array([0, 0, 0, 0])

    def bucket(v):
        if v <= q[0]: return 0
        if v <= q[1]: return 1
        if v <= q[2]: return 2
        if v <= q[3]: return 3
        return 4

    colors = [_PALETTE[bucket(v)] for v in z]

    # hover: 城市中文名 + 排放量 + 日均
    hover_names = [CITY_NAME_CN.get(c, c) for c in cities]
    hover_em = [city_em.get(c, 0.0) for c in cities]
    hover_daily = [city_daily.get(c, float('nan')) for c in cities]

    # 底图: 用 world.geojson 画灰色国家边界 (画成 scatter 线, 避免 choropleth 叠加问题)
    fig = go.Figure()

    # 世界底图
    for geom in world.geometry:
        if geom is None:
            continue
        gs = geom.geoms if geom.geom_type == 'MultiPolygon' else [geom]
        for poly in gs:
            xs, ys = poly.exterior.xy
            fig.add_trace(go.Scattergeo(
                lon=list(xs), lat=list(ys),
                mode='lines', line=dict(color='#9aa4b2', width=0.6),
                hoverinfo='skip', showlegend=False, opacity=0.6,
            ))

    # 城市行政区块 (choropleth)
    fig.add_trace(go.Choropleth(
        geojson=blocks.__geo_interface__,
        locations=cities,
        z=z,
        colorscale=[[i / 4.0, c] for i, c in enumerate(_PALETTE)],
        featureidkey='properties.city',
        customdata=list(zip(hover_names, hover_em, hover_daily)),
        hovertemplate=(
            '<b>%{customdata[0]}</b><br>'
            f'排放量：%{{customdata[1]:,.0f}} {UNITS["total_emission"]}<br>'
            '日均排放：%{customdata[2]:,.1f} 千吨 CO₂/日'
            '<extra></extra>'
        ),
        marker_line_color='white',
        marker_line_width=1.0,
        showscale=False,
        zmin=em_all.min() if em_all.size else 0,
        zmax=em_all.max() if em_all.size else 1,
    ))

    # 图例 (分档色块)
    for i, (c, lab) in enumerate(zip(_PALETTE, ['排放最低档', '较低档', '中档', '较高档', '最高档'])):
        fig.add_trace(go.Scattergeo(
            lon=[None], lat=[None],
            mode='markers', name=lab,
            marker=dict(size=0, color=c),
            hoverinfo='skip', showlegend=True,
        ))

    fig.update_geos(projection_type='natural earth')
    fig.update_layout(
        title=f'{year}年 全球城市碳排放分布（行政区边界块）',
        height=450,
        margin=dict(l=0, r=0, t=40, b=0),
        hovermode='closest',
        legend_title_text='排放量分档',
        geo=dict(bgcolor='#f2f4f7', showframe=False),
    )
    return fig
