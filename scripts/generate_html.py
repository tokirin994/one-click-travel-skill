#!/usr/bin/env python3
"""Render a one-click-travel HTML page from normalized trip JSON."""

from __future__ import annotations

import argparse
import html
import json
import math
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = ROOT / "assets" / "html-template" / "template.html"


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def tags_html(tags: list[str], class_name: str = "feature-tag") -> str:
    return "".join(f"<span class=\"{class_name}\">{esc(tag)}</span>" for tag in tags)


def link_button(url: str, label: str, class_name: str = "button") -> str:
    if not url:
        return ""
    return f"<a class=\"{class_name}\" href=\"{esc(url)}\" target=\"_blank\" rel=\"noopener\">{esc(label)}</a>"


DAY_COLORS = ["#667eea", "#f59e0b", "#10b981"]


def has_coords(item: dict[str, Any]) -> bool:
    return item.get("lng") not in (None, "") and item.get("lat") not in (None, "")


BEIJING_STATIONS = {
    "故宫博物院": "1号线天安门东站/天安门西站",
    "天安门广场": "1号线天安门东站/天安门西站",
    "颐和园": "4号线北宫门站",
    "天坛公园": "5号线天坛东门站",
    "八达岭长城": "清河站乘市郊铁路/高铁至八达岭长城站",
    "什刹海": "8号线什刹海站",
    "国家博物馆": "1号线天安门东站",
    "恭王府": "6号线北海北站",
    "南锣鼓巷": "6号线/8号线南锣鼓巷站",
    "景山公园": "8号线中国美术馆站或6号线南锣鼓巷站后步行/打车",
}


def nearest_station(item: dict[str, Any]) -> str:
    if item.get("nearest_station"):
        return str(item["nearest_station"])
    return BEIJING_STATIONS.get(str(item.get("name", "")), "")


def transport_detail(item: dict[str, Any], transport: str | None, is_far: bool = False) -> str:
    station = nearest_station(item)
    if transport == "train":
        return f"建议从市区乘市郊铁路/高铁到 {station or '景区附近站点'}，再接驳景区交通；具体班次以实时平台为准。"
    if transport == "metro":
        return f"建议地铁优先，坐到{station}后步行或短途打车；具体线路以实时导航为准。" if station else "建议地铁优先，按实时导航选择最近站点后步行。"
    if transport == "walk":
        return "相邻点位距离较近，建议步行或骑行串联，雨天可改短途打车。"
    if transport == "taxi":
        return "返程建议打车或按实时导航选择地铁，晚高峰预留更长时间。"
    return "按实时导航选择合适交通方式。"


def transport_duration(transport: str | None, is_far: bool = False) -> str:
    if transport == "train" or is_far:
        return "约1.5-2.5小时"
    if transport == "metro":
        return "约30-60分钟"
    if transport == "walk":
        return "约10-25分钟"
    if transport == "taxi":
        return "约20-45分钟"
    return ""


def route_tip(item: dict[str, Any], point_type: str, is_far: bool = False) -> str:
    name = str(item.get("name", ""))
    if point_type == "start":
        return "出发前确认预约、身份证件和当天交通状态。"
    if point_type == "end":
        return "返程前确认末班车或打车排队情况。"
    if is_far:
        return "远郊点建议单独安排半天到一天，提前订票并预留返程时间。"
    if "故宫" in name or "博物馆" in name or "天安门" in name:
        return "热门预约点建议提前确认预约、安检和入场时间。"
    return "现场开放、票价和排队情况以实时平台为准。"


def route_description(item: dict[str, Any], point_type: str) -> str:
    if point_type == "start":
        return "从酒店出发，先确认当天预约、证件和交通状态。"
    if point_type == "end":
        return "结束当天行程后返回酒店休息。"
    return str(item.get("summary") or "按路线顺序游览，现场开放状态以实时平台为准。")


def time_window(index: int, is_far: bool = False) -> str:
    if is_far:
        return "09:00-15:30"
    windows = ["09:00-11:00", "11:00-12:00", "13:00-15:00", "15:00-17:00", "17:00-18:30"]
    return windows[index] if index < len(windows) else "傍晚"


def stay_duration_text(item: dict[str, Any], point_type: str, is_far: bool = False) -> str:
    if point_type in ("start", "end"):
        return ""
    name = str(item.get("name", ""))
    if is_far:
        return "游玩约3.5-5小时"
    if "故宫" in name or "颐和园" in name or "博物馆" in name:
        return "游玩约2-3小时"
    if "广场" in name or "公园" in name or "胡同" in name or "巷" in name:
        return "游玩约1-2小时"
    return "游玩约1.5-2小时"


def route_point(
    item: dict[str, Any],
    day: int,
    point_type: str,
    transport: str | None = None,
    index: int = 0,
    is_far: bool = False,
) -> dict[str, Any]:
    return {
        "name": item.get("name", ""),
        "position": [item.get("lng"), item.get("lat")],
        "day": day,
        "transport": transport,
        "transport_detail": transport_detail(item, transport, is_far),
        "transport_duration": transport_duration(transport, is_far),
        "time": "08:30-09:00" if point_type == "start" else "返程" if point_type == "end" else time_window(index, is_far),
        "stay_duration": stay_duration_text(item, point_type, is_far),
        "description": route_description(item, point_type),
        "ticket_price": "" if point_type in ("start", "end") else str(item.get("price") or ""),
        "tip": route_tip(item, point_type, is_far),
        "nearest_station": nearest_station(item),
        "type": point_type,
    }


def chunk_items(items: list[dict[str, Any]], day_count: int) -> list[list[dict[str, Any]]]:
    if not items:
        return [[] for _ in range(day_count)]
    chunk_size = math.ceil(len(items) / day_count)
    chunks = [items[index : index + chunk_size] for index in range(0, len(items), chunk_size)]
    while len(chunks) < day_count:
        chunks.append([])
    return chunks[:day_count]


def coord_distance(a: dict[str, Any], b: dict[str, Any]) -> float:
    try:
        lng1, lat1 = float(a.get("lng")), float(a.get("lat"))
        lng2, lat2 = float(b.get("lng")), float(b.get("lat"))
    except (TypeError, ValueError):
        return 0.0
    return math.sqrt((lng1 - lng2) ** 2 + (lat1 - lat2) ** 2)


def default_route_title(destination: str, day: int) -> str:
    titles = [
        f"{destination}经典首日路线",
        f"{destination}深度漫游路线",
        f"{destination}轻松补充路线",
    ]
    return titles[day - 1] if day <= len(titles) else f"第 {day} 天路线"


def default_route_summary(points: list[dict[str, Any]]) -> str:
    stop_count = len([point for point in points if point.get("type") == "attraction"])
    if stop_count <= 2:
        return "低强度安排，适合把预约、交通和用餐时间留得更宽松。"
    if stop_count == 3:
        return "半日到一日节奏，适合首次到访和常规城市游。"
    return "点位较充实，建议提前预约热门景点并预留休息时间。"


def build_default_routes(data: dict[str, Any]) -> list[dict[str, Any]]:
    trip = data.get("trip", {})
    destination = trip.get("destination", "目的地")
    hotels = [item for item in data.get("hotels", []) if has_coords(item)]
    attractions = [item for item in data.get("attractions", []) if has_coords(item)]
    if not attractions:
        return []
    hotel = hotels[0] if hotels else None

    far_attractions: list[dict[str, Any]] = []
    city_attractions = attractions
    if hotel:
        far_attractions = [item for item in attractions if coord_distance(hotel, item) > 0.25]
        city_attractions = [item for item in attractions if item not in far_attractions]

    day_count = min(3, max(1, math.ceil(len(attractions) / 4)))
    if far_attractions and day_count > 1:
        chunks = chunk_items(city_attractions, day_count - 1)
        chunks.append(far_attractions)
    else:
        chunks = chunk_items(city_attractions, day_count)
    routes = []
    for day, stops in enumerate(chunks, start=1):
        points: list[dict[str, Any]] = []
        if hotel:
            points.append(route_point(hotel, day, "start", None, 0))
        for index, stop in enumerate(stops):
            is_far_stop = hotel is not None and coord_distance(hotel, stop) > 0.25
            transport = "train" if index == 0 and is_far_stop else "metro" if index == 0 else "walk"
            points.append(route_point(stop, day, "attraction", transport, index, is_far_stop))
        if hotel and stops:
            points.append(route_point(hotel, day, "end", "taxi", len(stops) + 1))
        if not points:
            continue
        routes.append(
            {
                "day": day,
                "title": default_route_title(destination, day),
                "summary": default_route_summary(points),
                "color": DAY_COLORS[(day - 1) % len(DAY_COLORS)],
                "points": points,
            }
        )
    return routes


def normalized_routes(data: dict[str, Any]) -> list[dict[str, Any]]:
    routes = data.get("routes") or data.get("itinerary") or []
    if routes:
        return routes
    return build_default_routes(data)


def transport_label(value: Any) -> str:
    labels = {
        "metro": "地铁",
        "walk": "步行",
        "ferry": "轮渡",
        "tram": "电车",
        "bus": "公交",
        "taxi": "打车",
        "train": "铁路",
    }
    return labels.get(str(value or ""), "")


def point_type_label(value: Any) -> str:
    labels = {
        "start": "出发",
        "end": "返回",
        "transit": "换乘",
        "attraction": "游览",
    }
    return labels.get(str(value or ""), "停靠")


def routes_timeline_html(routes: list[dict[str, Any]], weather_data: dict[str, Any] | None = None) -> str:
    if not routes:
        return "<div class=\"route-empty\">暂无可视化路线。补充酒店和景点坐标后会自动生成。</div>"
    
    weather_icons = {
        "晴": "☀️", "多云": "⛅", "阴": "☁️",
        "小雨": "🌦️", "中雨": "🌧️", "大雨": "🌧️", "暴雨": "⛈️",
        "雷阵雨": "⛈️", "阵雨": "🌦️",
        "小雪": "🌨️", "中雪": "🌨️", "大雪": "❄️",
        "雾": "🌫️", "霾": "😷",
    }
    forecasts = (weather_data or {}).get("forecasts", [])
    
    blocks = []
    for route in routes:
        day = int(route.get("day") or len(blocks) + 1)
        points = route.get("points") or []
        
        # 获取当天天气
        weather_line = ""
        if day - 1 < len(forecasts):
            fc = forecasts[day - 1]
            icon = weather_icons.get(fc.get("day_weather", ""), "🌤️")
            temp = f"{fc.get('night_temp', '')}°C ~ {fc.get('day_temp', '')}°C"
            weather_line = f'<div class="route-day-weather">{icon} {esc(fc.get("day_weather", ""))} {esc(temp)}</div>'
        
        items = []
        for index, point in enumerate(points, start=1):
            transport = transport_label(point.get("transport"))
            transport_html = (
                f"""
                <div class="timeline-transport">
                  <div class="transport-label">出行方式</div>
                  <div class="transport-detail"><strong>{esc(transport)}</strong>{esc(' · ' + point.get('transport_duration') if point.get('transport_duration') else '')}</div>
                  <div class="transport-note">{esc(point.get('transport_detail') or '')}</div>
                </div>
                """
                if transport
                else ""
            )
            station = point.get("nearest_station")
            station_html = f"<span>邻近站点：{esc(station)}</span>" if station else ""
            stay = point.get("stay_duration")
            stay_html = f"<span>{esc(stay)}</span>" if stay else ""
            price = point.get("ticket_price")
            price_text = price or point.get("tip")
            price_html = (
                f"""
                <div class="timeline-price">
                  <span class="timeline-price-icon">💡</span>
                  <span>{esc(price_text)}</span>
                </div>
                """
                if price_text and point.get("type") == "attraction"
                else ""
            )
            tip = point.get("tip")
            tip_html = f"<div class=\"timeline-tip\">{esc(tip)}</div>" if tip and point.get("type") != "attraction" else ""
            items.append(
                f"""
                <div class="timeline-item {esc(point.get('type') or 'attraction')}">
                  <div class="timeline-marker">{index}</div>
                  <div class="timeline-card">
                    <div class="timeline-time">⏰ {esc(point.get('time') or f'第 {index} 站')}</div>
                    <h3 class="timeline-title">{esc(point.get('name'))}</h3>
                    <p class="timeline-description">{esc(point.get('description') or '')}</p>
                    <div class="timeline-meta">{stay_html}{station_html}</div>
                    {transport_html}
                    {tip_html}
                    {price_html}
                  </div>
                </div>
                """
            )
        blocks.append(
            f"""
            <section class="route-day-section day{day}">
              <div class="route-day-title">Day {day}：{esc(route.get('title') or f'Day {day}')}</div>
              {weather_line}
              <div class="route-day-summary">{esc(route.get('summary') or '')}</div>
              <div class="route-timeline">{"".join(items)}</div>
            </section>
            """
        )
    return "\n".join(blocks)


def routes_data(data: dict[str, Any]) -> str:
    return json.dumps(normalized_routes(data), ensure_ascii=False)


def attraction_card(item: dict[str, Any], index: int) -> str:
    image = item.get("image_url")
    image_html = (
        f"<img src=\"{esc(image)}\" alt=\"{esc(item.get('name'))}\" class=\"attraction-image\">"
        if image
        else f"<div class=\"attraction-image attraction-placeholder\">{esc(item.get('name') or '景点')}</div>"
    )
    note = ""
    if item.get("rednote_note_id"):
        note = f"<button class=\"attraction-link\" onclick=\"return openWithFallback('xiaohongshu://explore/{esc(item['rednote_note_id'])}', '{esc(item.get('rednote_url') or item.get('source_url'))}')\">查看小红书攻略</button>"
    elif item.get("rednote_url"):
        note = link_button(item["rednote_url"], "查看小红书攻略", "attraction-link")
    return f"""
    <article class="attraction-card">
      {image_html}
      <div class="attraction-content">
        <div class="attraction-header">
          <span class="attraction-rank">{index}</span>
          <h3 class="attraction-name">{esc(item.get('name'))}</h3>
          <span class="attraction-rating">{esc(item.get('rating') or '暂无评分')}</span>
        </div>
        <div class="attraction-location">{esc(item.get('address'))}</div>
        <div class="attraction-description">{esc(item.get('summary'))}</div>
        <div class="attraction-features">{tags_html(item.get('tags') or [], 'attraction-tag')}</div>
        <div class="attraction-price">价格：{esc(item.get('price') or '以平台实时信息为准')}</div>
        <div class="actions">{link_button(item.get('source_url', ''), '查看来源', 'source-link')}{note}</div>
      </div>
    </article>
    """


def hotel_card(item: dict[str, Any]) -> str:
    meituan = ""
    if item.get("meituan_url"):
        meituan = f"<button class=\"hotel-detail-btn\" onclick=\"return openWithFallback('imeituan://www.meituan.com', '{esc(item['meituan_url'])}')\">打开美团</button>"
    return f"""
    <article class="hotel-card">
      <h3 class="hotel-name">{esc(item.get('name'))}</h3>
      <p class="hotel-address">{esc(item.get('address'))}</p>
      <p class="hotel-summary">{esc(item.get('summary'))}</p>
      <div class="hotel-info">
        <span class="hotel-rating">{esc(item.get('rating') or '美团评分暂无')}</span>
        <span class="hotel-price">{esc(item.get('price') or '以平台实时信息为准')}</span>
      </div>
      <div class="hotel-features">{tags_html(item.get('tags') or [], 'feature-tag')}</div>
      <div class="actions">{meituan}{link_button(item.get('source_url', ''), '查看网页', 'hotel-detail-btn secondary')}</div>
    </article>
    """


def food_card(item: dict[str, Any]) -> str:
    """Generate HTML for a food recommendation card."""
    name = esc(item.get("name", ""))
    rating = esc(item.get("rating", ""))
    avg_price = esc(item.get("avg_price", ""))
    address = esc(item.get("address", ""))
    summary = esc(item.get("summary", ""))
    nearest_station = esc(item.get("nearest_station", ""))
    walk_time = esc(item.get("walk_time", ""))
    recommended_dishes = item.get("recommended_dishes", [])
    source_url = esc(item.get("source_url", ""))
    category = item.get("category", "restaurant")

    rating_html = f'<span class="food-rating">⭐ {rating}</span>' if rating else ""
    price_html = f'<span class="food-price">💰 人均 ¥{avg_price}</span>' if avg_price else ""

    summary_html = f'<div class="food-summary">{summary}</div>' if summary else ""
    station_html = ""
    if nearest_station:
        walk_info = f'<span class="food-walk-time">步行{walk_time}</span>' if walk_time else ""
        station_html = f'<span class="food-station">🚇 {nearest_station}</span>{walk_info}'

    dishes_html = ""
    if recommended_dishes:
        dishes_list = "".join(f"<span class=\"food-dish\">{esc(dish)}</span>" for dish in recommended_dishes[:6])
        dishes_html = f"<div class=\"food-dishes\"><span class=\"food-dishes-label\">推荐菜</span><div class=\"food-dishes-list\">{dishes_list}</div></div>"

    link_html = f'<a href="{source_url}" target="_blank" class="food-link">查看详情</a>' if source_url else ""

    return f"""
    <div class="food-card {esc(category)}">
      <div class="food-card-header">
        <h3 class="food-name">{name}</h3>
        {rating_html}
      </div>
      <div class="food-card-body">
        {summary_html}
        <div class="food-info">
          <div class="food-price-row">{price_html}</div>
          <div class="food-address">{address}</div>
          {f'<div class="food-station-row">{station_html}</div>' if station_html else ''}
        </div>
        {dishes_html}
        {link_html}
      </div>
    </div>
    """


def foods_html(data: dict[str, Any]) -> str:
    """Generate HTML for food sections split by category."""
    foods = data.get("foods", [])
    restaurants = [f for f in foods if f.get("category") != "snack"]
    snacks = [f for f in foods if f.get("category") == "snack"]

    parts = []
    if restaurants:
        parts.append('<h2 class="food-section-title">🍽️ 正餐推荐</h2>')
        parts.append(f'<div class="food-grid">{"".join(food_card(f) for f in restaurants)}</div>')
    if snacks:
        parts.append('<h2 class="food-section-title snack">🍜 小吃推荐</h2>')
        parts.append(f'<div class="food-grid">{"".join(food_card(f) for f in snacks)}</div>')
    if not parts:
        parts.append('<p style="color:#667085;text-align:center;padding:40px 0;">暂无美食推荐数据</p>')
    return "\n".join(parts)


def food_map_data(data: dict[str, Any]) -> str:
    """Generate map data for food recommendations."""
    foods = data.get("foods", [])
    points = []
    for food in foods:
        if food.get("lng") and food.get("lat"):
            points.append({
                "type": "美食",
                "name": food.get("name", ""),
                "lng": food.get("lng"),
                "lat": food.get("lat"),
                "address": food.get("address", ""),
                "rating": food.get("rating", ""),
                "avg_price": food.get("avg_price", ""),
            })
    return json.dumps(points, ensure_ascii=False)


def map_data(data: dict[str, Any]) -> str:
    points = []
    for kind, items in (("景点", data.get("attractions", [])), ("酒店", data.get("hotels", [])), ("交通", data.get("transit", []))):
        for item in items:
            if item.get("lng") not in (None, "") and item.get("lat") not in (None, ""):
                points.append({"type": kind, "name": item.get("name"), "lng": item.get("lng"), "lat": item.get("lat"), "address": item.get("address", "")})
    return json.dumps(points, ensure_ascii=False)


def trip_notes_html(notes: list[str]) -> str:
    return "".join(f"<li>{esc(note)}</li>" for note in notes)


def weather_html(weather_data: dict[str, Any]) -> str:
    """Generate weather forecast HTML section."""
    if not weather_data or "error" in weather_data:
        return ""

    forecasts = weather_data.get("forecasts", [])
    if not forecasts:
        return ""

    city = weather_data.get("city", "")
    tips = weather_data.get("tips", [])

    # Weather icon mapping
    weather_icons = {
        "晴": "☀️", "多云": "⛅", "阴": "☁️",
        "小雨": "🌦️", "中雨": "🌧️", "大雨": "🌧️", "暴雨": "⛈️",
        "雷阵雨": "⛈️", "阵雨": "🌦️",
        "小雪": "🌨️", "中雪": "🌨️", "大雪": "❄️",
        "雾": "🌫️", "霾": "😷",
    }

    cards = []
    for day in forecasts:
        date = day.get("date", "")
        week = day.get("week", "")
        day_weather = day.get("day_weather", "")
        night_weather = day.get("night_weather", "")
        day_temp = day.get("day_temp", "")
        night_temp = day.get("night_temp", "")

        icon = weather_icons.get(day_weather, "🌤️")
        temp_range = f"{night_temp}°C ~ {day_temp}°C" if day_temp and night_temp else ""

        cards.append(f"""
        <div class="weather-card" data-date="{esc(date)}">
          <div class="weather-date">
            <div class="weather-date-text">{esc(date)}</div>
            <div class="weather-week">{esc(week)}</div>
          </div>
          <div class="weather-icon" data-w-icon>{icon}</div>
          <div class="weather-info">
            <div class="weather-condition" data-w-cond>{esc(day_weather)} / {esc(night_weather)}</div>
            <div class="weather-temp" data-w-temp>{esc(temp_range)}</div>
          </div>
        </div>
        """)

    tips_html = ""
    if tips:
        tips_html = f"""
        <div class="weather-tips">
          <div class="weather-tips-title">🎯 出行建议</div>
          <ul class="weather-tips-list">
            {"".join(f"<li>{esc(tip)}</li>" for tip in tips)}
          </ul>
        </div>
        """

    return f"""
    <div class="weather-section" data-w-now>
      <div class="weather-header">
        <h2 class="weather-title">🌤️ {esc(city)}天气预报</h2>
        <div class="weather-now-inline">
          <span class="wn-temp" data-w-now-temp>--°</span>
          <span class="wn-desc" data-w-now-desc>加载中...</span>
        </div>
      </div>
      <div class="weather-cards">
        {"".join(cards)}
      </div>
      {tips_html}
    </div>
    """


def route_weather_html(data: dict[str, Any]) -> str:
    """Generate per-day weather summary for the route planning page."""
    weather_data = data.get("weather", {})
    if not weather_data or "error" in weather_data:
        return ""
    forecasts = weather_data.get("forecasts", [])
    if not forecasts:
        return ""
    routes = normalized_routes(data)
    if not routes:
        return ""

    weather_icons = {
        "晴": "☀️", "多云": "⛅", "阴": "☁️",
        "小雨": "🌦️", "中雨": "🌧️", "大雨": "🌧️", "暴雨": "⛈️",
        "雷阵雨": "⛈️", "阵雨": "🌦️",
        "小雪": "🌨️", "中雪": "🌨️", "大雪": "❄️",
        "雾": "🌫️", "霾": "😷",
    }

    rain_keywords = ["雨", "雷", "阵雨", "小雨", "中雨", "大雨", "暴雨"]

    day_bars = []
    for index, route in enumerate(routes):
        day = int(route.get("day") or index + 1)
        title = route.get("title") or f"Day {day}"
        color = route.get("color") or DAY_COLORS[(day - 1) % len(DAY_COLORS)]

        if index < len(forecasts):
            fc = forecasts[index]
            day_weather = fc.get("day_weather", "")
            night_weather = fc.get("night_weather", "")
            day_temp = fc.get("day_temp", "")
            night_temp = fc.get("night_temp", "")
            icon = weather_icons.get(day_weather, "🌤️")
            temp_range = f"{night_temp}°C ~ {day_temp}°C" if day_temp and night_temp else ""
            is_rainy = any(kw in day_weather or kw in night_weather for kw in rain_keywords)

            try:
                temp_val = int(day_temp)
            except (ValueError, TypeError):
                temp_val = 20

            if is_rainy:
                weather_advice = "有雨，建议携带雨具，优先安排室内景点"
            elif temp_val >= 35:
                weather_advice = "气温较高，注意防晒补水"
            elif temp_val <= 5:
                weather_advice = "气温较低，注意保暖"
            else:
                weather_advice = "天气适宜户外活动"

            bar = f"""
            <div class="route-weather-day" style="border-left-color: {esc(color)};">
              <div class="route-weather-day-header">
                <span class="route-weather-day-label">Day {day}</span>
                <span class="route-weather-day-title">{esc(title)}</span>
              </div>
              <div class="route-weather-day-body">
                <span class="route-weather-icon">{icon}</span>
                <span class="route-weather-condition">{esc(day_weather)} / {esc(night_weather)}</span>
                <span class="route-weather-temp">{esc(temp_range)}</span>
                <span class="route-weather-advice">{esc(weather_advice)}</span>
              </div>
            </div>
            """
        else:
            bar = f"""
            <div class="route-weather-day" style="border-left-color: {esc(color)};">
              <div class="route-weather-day-header">
                <span class="route-weather-day-label">Day {day}</span>
                <span class="route-weather-day-title">{esc(title)}</span>
              </div>
              <div class="route-weather-day-body">
                <span class="route-weather-condition">暂无天气数据</span>
              </div>
            </div>
            """
        day_bars.append(bar)

    return f"""
    <div class="route-weather-section">
      <div class="route-weather-title">🌤️ 各日天气概览</div>
      <div class="route-weather-days">
        {"".join(day_bars)}
      </div>
    </div>
    """


def render(data: dict[str, Any], template: str) -> str:
    trip = data.get("trip", {})
    destination = trip.get("destination", "目的地")
    departure = trip.get("departure", "")
    title = f"{departure}去{destination}旅行攻略" if departure else f"{destination}旅行攻略"
    updated_at = trip.get("updated_at") or date.today().isoformat()
    sources = data.get("sources", [])
    source_items = "".join(
        f"<li><a href=\"{esc(src.get('url'))}\" target=\"_blank\" rel=\"noopener\">{esc(src.get('name'))}</a> <span>{esc(src.get('used_for'))}</span></li>"
        for src in sources
        if src.get("url")
    )
    map_cfg = data.get("map", {})
    amap_key = map_cfg.get("amap_key", "")
    amap_security = map_cfg.get("amap_security_js_code", "")
    routes = normalized_routes(data)
    weather_section = weather_html(data.get("weather", {}))
    weather_data = data.get("weather", {})
    foods = data.get("foods", [])
    return (
        template.replace("{{TITLE}}", esc(title))
        .replace("{{DESTINATION}}", esc(destination))
        .replace("{{DEPARTURE}}", esc(departure))
        .replace("{{BUDGET}}", esc(trip.get("budget", "")))
        .replace("{{CHECKIN_DATE}}", esc(trip.get("hotel_checkin_date", "")))
        .replace("{{CHECKOUT_DATE}}", esc(trip.get("hotel_checkout_date", "")))
        .replace("{{UPDATED_AT}}", esc(updated_at))
        .replace("{{TRIP_NOTES}}", trip_notes_html(trip.get("notes") or []))
        .replace("{{ROUTE_TIMELINE}}", routes_timeline_html(routes, weather_data))
        .replace("{{ROUTES_JSON}}", html.escape(json.dumps(routes, ensure_ascii=False), quote=False))
        .replace("{{ATTRACTIONS}}", "\n".join(attraction_card(item, index) for index, item in enumerate(data.get("attractions", []), start=1)))
        .replace("{{HOTELS}}", "\n".join(hotel_card(item) for item in data.get("hotels", [])))
        .replace("{{FOODS}}", foods_html(data))
        .replace("{{FOODS_JSON}}", html.escape(json.dumps(foods, ensure_ascii=False), quote=False))
        .replace("{{SOURCES}}", source_items or "<li>未记录外部来源，页面内容需人工核验。</li>")
        .replace("{{MAP_POINTS_JSON}}", html.escape(map_data(data), quote=False))
        .replace("{{AMAP_KEY}}", esc(amap_key))
        .replace("{{AMAP_SECURITY_JS_CODE}}", esc(amap_security))
        .replace("{{WEATHER_SECTION}}", weather_section)
        .replace("{{ROUTE_WEATHER}}", route_weather_html(data))
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    parser.add_argument(
        "--allow-static-map",
        action="store_true",
        help="Allow rendering without an AMap key after the user explicitly skips the live map.",
    )
    args = parser.parse_args()

    data = json.loads(Path(args.input).read_text(encoding="utf-8-sig"))
    if not args.allow_static_map and not data.get("map", {}).get("amap_key"):
        raise SystemExit(
            "AMap key is required for the default live-map page. Ask the user for a 高德 Web JS API Key, "
            "or rerun with --allow-static-map only after the user explicitly skips the live map. "
            "Key creation: https://console.amap.com/dev/key/app ; "
            "prepare guide: https://lbs.amap.com/api/javascript-api-v2/guide/abc/prepare"
        )
    template = Path(args.template).read_text(encoding="utf-8")
    Path(args.output).write_text(render(data, template), encoding="utf-8")


if __name__ == "__main__":
    main()
