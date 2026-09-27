---
name: one-click-travel
description: Generate a travel guide HTML page from a user's destination, including attractions, hotel recommendations, map markers, app/web deep links, and optional EdgeOne deployment. Use when the user asks to create or plan a city travel guide, single-city itinerary, cross-city trip such as Shenzhen to Hong Kong, attraction list, hotel shortlist, or shareable HTML travel page. Requires meituan-travel and rednote-skill integrations for Meituan data and Xiaohongshu notes before generation.
---

# One Click Travel

Generate a self-contained, polished Chinese travel guide HTML page for a destination or cross-city trip. Treat `meituan-travel` and `rednote-skill` as hard dependencies for data collection.

## Bundled Resources

- `references/data-schema.md`: canonical JSON schema for collected data and generated page input.
- `optional-skills/meituan-travel/SKILL.md`: required Meituan integration adapter for hotel, attraction, price, rating, and purchase-link data.
- `optional-skills/rednote-skill/SKILL.md`: required Xiaohongshu integration adapter for notes, UGC highlights, route popularity, and note deep links.
- `scripts/collect_attractions.py`: normalize attraction data from specialist skill output, web research, or user-provided JSON.
- `scripts/collect_hotels.py`: normalize hotel data from specialist skill output, web research, or user-provided JSON.
- `scripts/collect_routes.py`: build default day-by-day route data from normalized hotel and attraction coordinates.
- `scripts/collect_weather.py`: fetch weather forecast from AMap Weather API and generate travel tips.
- `scripts/geocode_amap.py`: fill coordinates using AMap geocoding when a key is available.
- `scripts/generate_html.py`: render the final HTML page from normalized JSON and `assets/html-template/template.html`.
- `scripts/deploy_edgeone.py`: deploy a generated HTML page to EdgeOne Pages with the local EdgeOne CLI when the user wants a shareable EdgeOne preview URL.
- `references/edgeone-cli-deploy.md`: EdgeOne CLI setup, login, deployment, and troubleshooting guidance; read when deployment is requested or when the user asks about publishing.

## Inputs

Extract from the user request:

- `destination`: required destination city or region.
- `departure`: optional origin city for cross-city trips.
- `hotel_city`: lodging city; for cross-city trips infer from the request, otherwise ask only when lodging choice affects the result.
- `budget`: hotel budget; default to "300元左右" when not specified.
- `hotel_checkin_date`: default to tomorrow in the user's timezone.
- `hotel_checkout_date`: default to the day after `hotel_checkin_date` for a 1-night stay unless the user specifies nights/dates.
- `hotel_count`: default 4.
- `attraction_count`: default 10.
- `route_count` / `trip_days`: optional; default to 2-3 days based on available attractions.
- `route_style`: optional; infer conservatively from the request when present, otherwise default to a first-visit practical route.
- `amap_key` and optional `amap_security_js_code`: required by default for the live map experience. Ask the user for these before HTML generation unless they explicitly choose to skip the live map.
- `amap_weather_key`: optional, a separate AMap Web Service API key for weather data. If not provided, the skill will attempt to use the main `amap_key` if it supports Web Service APIs.
- Deployment preference: return the local HTML file by default, then ask whether to publish it to EdgeOne Pages with the local EdgeOne CLI. Do not require GitHub.

Ask the user only for missing information that blocks the intended result. Missing `meituan-travel`, `rednote-skill`, Meituan Token, or Xiaohongshu login blocks generation until resolved.

For ordinary travel-guide requests, treat the map as part of the intended result. If AMap credentials are missing, pause after extracting the destination and ask:

```text
要生成带实时高德地图的攻略页，请提供高德 Web JS API Key；如果你的应用开启了安全密钥，也请一起提供 securityJsCode。
如果还没有 Key，可以在高德开放平台创建应用并添加 Web端(JS API) Key：
https://console.amap.com/dev/key/app
准备说明：
https://lbs.amap.com/api/javascript-api-v2/guide/abc/prepare
也可以回复"跳过地图"，我会先生成静态坐标版。
```

Continue without credentials only when the user says to skip, says they do not have a key, or explicitly asks for a draft/static version.

## Weather Integration

The skill automatically fetches weather forecasts for the destination using AMap Weather API. This requires a **Web Service API key** (different from the JS API key used for maps).

If the user provides an `amap_key` that only supports JS API, the weather fetch will fail with `USERKEY_PLAT_NOMATCH`. In this case:
1. Ask the user to create a separate Web Service key at https://console.amap.com/dev/key/app
2. Or skip weather integration if the user prefers

Weather data includes:
- 3-day forecast (date, weather condition, temperature range, wind)
- Automatic travel tips based on weather (e.g., "bring umbrella for rainy days")

The weather section appears in the generated HTML between the map and hotel recommendations.

## Dependency Policy

Before collecting data, inspect available skills/tools from current context.

Required specialist dependencies:

1. `meituan-travel` must be available and configured. Use it for attractions, hotels, prices, ratings, and purchase links.
2. `rednote-skill` must be available and logged in. Use it for Xiaohongshu notes, user-generated highlights, images, note URLs, route popularity, and attraction ordering.
3. Read the matching file under `optional-skills/` for query shapes and field mapping.

If a required dependency is missing or not configured, pause before data collection:

- Missing `meituan-travel`: tell the user the Meituan travel skill is required and ask them to install/enable it before continuing.
- Missing Meituan Token or authentication failure: ask for a Meituan Travel API Token and provide `https://developer.meituan.com/zh/v2/dev/token`; do not continue with public hotel sources as a substitute.
- Missing `rednote-skill`: tell the user the Rednote/Xiaohongshu skill is required and ask them to install/enable it before continuing.
- Missing or expired Xiaohongshu login: validate login through the rednote skill, run its manual login flow, and ask the user to complete browser login; do not continue with public snippets as a substitute.

General browsing/search remains useful only for verifying official facts such as addresses, coordinates, opening rules, reservation requirements, and transit context. It must not replace the required Meituan or Xiaohongshu collection steps.

For non-specialist gaps, degrade gracefully:
- Missing exact coordinates: geocode through AMap if possible; otherwise use city-level coordinates and mark items as "待定位".
- Missing images: use public image URLs only when source and license are acceptable; otherwise use CSS placeholders or ask the user for images.

## Data Collection

Use `references/data-schema.md` as the target shape. Prefer structured JSON between steps:

1. Gather raw candidate data with the required `meituan-travel` and `rednote-skill` integrations, then verify factual details with web research or user-provided links where needed.
2. Save or pass candidate JSON into `scripts/collect_attractions.py` and `scripts/collect_hotels.py`.
3. If `amap_key` is missing and the user has not explicitly skipped the live map, ask for it before rendering.
4. Run `scripts/geocode_amap.py` if coordinates are missing and an AMap key is available.
5. Build route data by default. If `routes` is missing, run `scripts/collect_routes.py` or let `scripts/generate_html.py` derive default routes from hotel and attraction coordinates.
6. Run `scripts/generate_html.py` with the normalized trip JSON.
7. After the HTML is generated and validated, ask whether to publish it to EdgeOne Pages unless the user already requested deployment.

Collect attractions:

- Name, area/address, coordinates if available.
- Rating/popularity when available.
- Price or "免费/以现场为准". Query `meituan-travel` for attraction ticket price, rating/popularity, and purchase link during attraction collection; preserve the exact Meituan returned price string and link instead of approximating it.
- Short reason to visit.
- Image URL when reliable.
- Source URL.
- Meituan ticket/source URL from `meituan-travel`.
- Xiaohongshu note ID/link from `rednote-skill`.
- Confidence: `high`, `medium`, or `low`.

Attraction recommendations must be Xiaohongshu-informed through `rednote-skill`:

- Search 3-6 Xiaohongshu notes for `{destination} 必去景点 攻略`, `{destination} 两日游/三日游`, and important neighborhoods.
- Extract note titles, route mentions, tags, and interaction counts.
- Use Xiaohongshu to decide route popularity, practical tips, and card copy.
- Use official/map sources to verify addresses, coordinates, ticket/opening/booking rules.
- Use Meituan for attraction ticket prices and purchase links, then verify reservation/opening rules with official/map sources.
- Render a `查看小红书攻略` link on attraction cards whenever a stable note URL is available.

Collect hotels:

- Name, area/address, coordinates if available.
- Tomorrow's check-in price by default. Use the exact Meituan returned price string; do not replace it with approximate text.
- Meituan rating by default. Do not show non-Meituan ratings as the primary hotel rating.
- Tags such as "近地铁", "连锁", "近口岸", "亲子", "高性价比".
- Booking/source URL.
- Meituan link from `meituan-travel`.
- Confidence.

For cross-city trips, also collect transit/port context when relevant, such as口岸、车站、机场、通关提示、首末班车 or estimated travel time. Use current sources if the detail may change.

Collect routes:

- Route planning is enabled by default; do not require the user to ask for it explicitly.
- Store routes as structured data in `routes`, not only as rendered HTML or prose.
- Use route points shaped as `{ name, position: [lng, lat], day, transport, type, time, stay_duration, transport_detail, transport_duration, nearest_station, tip }`.
- `type` must be `start`, `end`, `transit`, or `attraction`.
- `transport` may be `metro`, `walk`, `ferry`, `tram`, `bus`, `taxi`, `train`, or `null`.
- Start from the first suitable hotel when coordinates are available, group nearby attractions into 2-3 day routes, and return to the hotel with an `end` point.
- Prefer fewer cross-city hops per day. Put far attractions into their own day when possible.
- Include practical time planning, stay duration, transport mode, approximate travel duration, nearest station when available, and short tips.
- Include attraction ticket price or ticket tip in route points, sourced from Meituan first and official/public sources second.
- Prefer concrete transport suggestions such as metro line/station, train station, taxi, or walking when verified or reasonably inferable.
- Do not invent exact transit lines, stations, or travel times without a source/API; when unknown, write that the user should follow real-time map navigation.

## Source Rules

- Keep a small source list in the generated page footer or metadata.
- Do not invent ratings, prices, coordinates, links, or note IDs.
- If sources disagree, prefer recent official/listing sources and mention "价格/开放状态以平台实时信息为准".
- Avoid scraping behind login walls. If Xiaohongshu requires login or `rednote-skill` is unavailable, pause and ask the user to complete login or enable the required skill.

## HTML Output

Create one HTML file named:

- `{destination}-travel.html` for single-city trips.
- `{departure}-{destination}-travel.html` for cross-city trips.

The page should include:

- Compact top navigation: 酒店 | 景点 | 路线规划 | 地图/交通贴士 when relevant. Place 路线规划 after 目的地景点.
- A default 路线规划 page in the top navigation.
- Route planning section:
  - Day-by-day timeline cards sourced from `routes`.
  - Live AMap route visualization when AMap is enabled.
  - Route markers by `type`: start hotel, end/return, transit, attraction.
  - Colored route lines per day, with `AMap.Polyline showDir: true` automatic direction arrows.
  - Traffic mode icons at route segment midpoints, using emoji such as 🚇🚶🚢🚡🚌🚗🚄 in white circular chips with colored borders.
  - Smooth route curves using 30-100 interpolated points, alternating curve direction by segment and applying sine-wave offsets.
  - Gray dashed return lines.
  - AMap toolbar, scale control, and automatic fit view.
  - Static route-order fallback when AMap is unavailable or skipped.
- Hero summary with destination, trip mode, budget, and last updated date.
- Hotel section with selectable cards and links.
- Attraction section with top items, images/placeholders, tags, source links, and Xiaohongshu links from `rednote-skill`.
- Map section:
  - Live AMap by default, using the user-provided API key.
  - Static fallback with coordinates/address list only when the user explicitly skips AMap or the key is unavailable after asking.
- Mobile-friendly deep-link buttons:
  - Meituan button only when a Meituan URL exists.
  - Xiaohongshu button only when a note ID or URL exists.
  - Web fallback always available when a source URL exists.
- Footer with data sources and "信息以平台实时页面为准". Do not display internal confidence labels in the generated page.

Keep styling self-contained in the HTML unless the project already has a build system. Prefer a clean, practical travel-planning UI over a marketing landing page.

Render with:

```bash
python scripts/generate_html.py --input trip-data.json --output output.html
```

If and only if the user explicitly skipped the live map:

```bash
python scripts/generate_html.py --input trip-data.json --output output.html --allow-static-map
```

## Deep Link Guidance

Use defensive fallbacks. Define `startTime` before mobile deep-link checks.

```javascript
function openWithFallback(deepLink, webUrl, timeout = 1800) {
  const isMobile = /Mobile|Android|iPhone/i.test(navigator.userAgent);
  if (!isMobile || !deepLink) {
    window.open(webUrl, "_blank");
    return false;
  }

  const startTime = Date.now();
  const iframe = document.createElement("iframe");
  iframe.style.display = "none";
  iframe.src = deepLink;
  document.body.appendChild(iframe);

  setTimeout(() => {
    iframe.remove();
    if (Date.now() - startTime < timeout + 500) {
      window.open(webUrl, "_blank");
    }
  }, timeout);

  return false;
}
```

For Xiaohongshu notes, use `xiaohongshu://explore/{noteId}` only when a valid `noteId` is known. Otherwise link to the public note/search URL.

## AMap Guidance

AMap credentials are required for the default live-map page. Before rendering, check whether `map.amap_key` is populated.

If `map.amap_key` is empty and the user has not opted out, stop and ask for a 高德 Web JS API Key. If the user says their AMap app has JS API security enabled, also request `securityJsCode`.

Use this wording:

```text
要生成带实时高德地图的攻略页，请提供高德 Web JS API Key；如果你的应用开启了安全密钥，也请一起提供 securityJsCode。
如果还没有 Key，可以在高德开放平台创建应用并添加 Web端(JS API) Key：
https://console.amap.com/dev/key/app
准备说明：
https://lbs.amap.com/api/javascript-api-v2/guide/abc/prepare
也可以回复“跳过地图”，我会先生成静态坐标版。
```

When the user provides AMap credentials, include:

```javascript
window._AMapSecurityConfig = {
  securityJsCode: "USER_SECURITY_JS_CODE"
};
```

Load the AMap script with the user's key. If the user explicitly skips credentials, do not include a broken script; render an address/coordinate list and a message that the map can be enabled after adding a key.

## Deployment

Use EdgeOne CLI local deployment when the user asks for a public/shareable URL or agrees to publish after generation. Do not require GitHub for deployment. EdgeOne Pages direct-upload deployments can return tokenized preview URLs; treat the full token URL as the shareable output.

After generating the HTML, if the user did not mention deployment, ask:

```text
攻略页已经生成。是否要发布到 EdgeOne Pages 获取可分享的预览链接？我可以用 EdgeOne CLI 从本地直接部署，不需要 GitHub。
```

If the user agrees, read `references/edgeone-cli-deploy.md`, then run:

```bash
python scripts/deploy_edgeone.py --html output.html --project-name destination-travel
```

Deployment behavior:

- Check whether the `edgeone` CLI is installed.
- If missing, guide the user to install it with `npm install -g edgeone`.
- If not logged in, guide the user to run `edgeone login` and complete the browser login.
- Copy the generated HTML into a temporary publish directory as `index.html`.
- Run `edgeone pages deploy <publish-dir> -n <project-name> -e production`.
- Return the full EdgeOne preview token URL only when the CLI reports a successful deployment. Prefer the exact `EDGEONE_DEPLOY_URL=...` value from CLI/script output, keep `eo_token` and `eo_time`, and do not replace it with the bare `edgeone.cool` root domain.
- When returning the link, note that it is a shareable preview URL and may expire; if visitors later see `401 UNAUTHORIZED`, generate a fresh Preview link from the EdgeOne console or redeploy.

If deployment is not requested or cannot be completed, save the HTML locally and tell the user the absolute path. Do not claim a shareable EdgeOne URL was deployed unless the deployment actually completed and returned a full token URL.

## Validation

Before finishing:

- Open or render the HTML when possible.
- Check that navigation, deep-link fallbacks, and map fallback do not throw JavaScript errors.
- Verify the route planning page is present by default, route data renders as a timeline, and route map/fallback does not throw JavaScript errors.
- Verify route polylines are not attempted for points without coordinates.
- Verify mobile layout does not overlap.
- Confirm every external link either exists in collected data or is omitted.

## Weather Module Optimizations

详见 `references/html-template-optimizations.md` for the full spec. Key enhancements applied to `assets/html-template/template.html`:

- **Dual data sources**: AMap (real-time + 4-day forecast via JSONP) + Open-Meteo (14-day forecast via fetch, no key required, CORS-friendly). Open-Meteo fills dates beyond AMap's 4-day window.
- **Per-day region query**: Each trip day queries weather by its main activity location's adcode (AMap) + lat/lng (Open-Meteo), not a single city-level query.
- **Past-date snapshot freeze**: Past dates' weather is saved to localStorage on first fetch and restored on subsequent loads; API calls are skipped for past dates. Enables post-trip review.
- **JSONP robustness**: onerror handler + 8s timeout + script cleanup + serial requests (avoids AMap QPS limit).
- **WMO code mapping**: Open-Meteo returns numeric WMO codes (0/1/51/80/95...) mapped to Chinese names + emoji.
- **5-Tab structure**: 行程(含地图) / 天气 / 美食 / 文娱活动 / 速查贴士. Map is embedded in the schedule tab, not a separate tab.
- **Card state machine**: past (frozen) / today (highlighted) / future-forecast / loading. Cards always render — no empty placeholders for future dates.
- **Auto refresh**: every 5 minutes via setInterval; manual refresh via button.
- **8s timeout fallback**: cards still in "加载中" after 8s show "暂未获取 · 点刷新".

The client-side enhancement script is injected before `</body>` in template.html (marked with `weather-enhance-injected` comment). It reads config from `window.AMAP_KEY`, `window.TRIP_DATES`, `window.DAY_ADCCODE`, `window.DAY_LATLNG`, `window.HOTEL_ADCODE` if the generated page exposes them; otherwise it degrades gracefully and only refreshes what it can.
