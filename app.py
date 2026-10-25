import streamlit as st
import pandas as pd
import requests, re, sqlite3
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin, urlparse
from pathlib import Path
from io import BytesIO
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="贵州天气配送风险监控", layout="wide")
ROOT = Path(__file__).parent
DB = ROOT / "risk_history.db"
TRAFFIC_URL = "https://jt.guizhou.gov.cn/cxfw_0/lkxx_5948603/cxtsyj/"
WEATHER_URL = "https://app.gjzwfw.gov.cn/jmopen/webapp/html5/zhyjssxx/index.html"
API_URL = "https://www.weather.com.cn/wzfw/smart/weatherapi.shtml"

KEYWORDS = ("凝冻","结冰","大雾","浓雾","暴雨","大雨","雷电","大风","冰雹","暴雪","雨雪","积雪","管制","封闭","封路","交通管制","道路结冰","预警","施工","中断")

AREAS = [
    "贵阳","遵义","六盘水","安顺","毕节","铜仁","黔西南","黔东南","黔南",
    "清镇","仁怀","赤水","盘州","兴义","兴仁","福泉","都匀","凯里",
    "息烽","修文","开阳","桐梓","绥阳","正安","道真","务川","凤冈","湄潭","余庆","习水",
    "水城","西秀","平坝","普定","镇宁","关岭","紫云","大方","黔西","金沙","织金","纳雍","威宁","赫章",
    "江口","玉屏","石阡","思南","印江","德江","松桃","普安","晴隆","贞丰","望谟","册亨","安龙",
    "镇远","黄平","施秉","三穗","岑巩","天柱","锦屏","剑河","台江","黎平","榕江","从江","雷山","麻江","丹寨","三都",
    "荔波","贵定","瓮安","独山","平塘","罗甸","长顺","龙里"
]

DISTRICT_COORDS = {
    "南明区": (26.564, 106.713), "云岩区": (26.604, 106.716), "花溪区": (26.419, 106.671),
    "乌当区": (26.630, 106.752), "白云区": (26.682, 106.630), "观山湖区": (26.619, 106.626),
    "清镇市": (26.553, 106.468), "开阳县": (27.056, 106.969), "息烽县": (27.093, 106.740), "修文县": (26.837, 106.595),
    "红花岗区": (27.644, 106.894), "汇川区": (27.706, 106.923), "播州区": (27.532, 106.827),
    "赤水市": (28.589, 105.698), "仁怀市": (27.792, 106.401), "桐梓县": (28.138, 106.825),
    "绥阳县": (27.947, 107.190), "正安县": (28.551, 107.441), "道真县": (28.878, 107.610),
    "务川县": (28.522, 107.889), "凤冈县": (27.957, 107.716), "湄潭县": (27.767, 107.485),
    "余庆县": (27.220, 107.888), "习水县": (28.319, 106.213),
    "七星关区": (27.301, 105.286), "大方县": (27.143, 105.609), "黔西市": (27.024, 106.038),
    "金沙县": (27.459, 106.222), "织金县": (26.669, 105.768), "纳雍县": (26.777, 105.375),
    "威宁县": (26.858, 104.283), "赫章县": (27.119, 104.726),
    "钟山区": (26.591, 104.830), "水城区": (26.556, 104.958), "六枝特区": (26.201, 105.480), "盘州市": (25.711, 104.471),
    "西秀区": (26.253, 105.947), "平坝区": (26.405, 106.257), "普定县": (26.311, 105.743),
    "镇宁县": (26.055, 105.768), "关岭县": (25.942, 105.618), "紫云县": (25.753, 106.083),
    "碧江区": (27.718, 109.189), "万山区": (27.519, 109.212), "江口县": (27.691, 108.847),
    "玉屏县": (27.237, 108.917), "石阡县": (27.521, 108.229), "思南县": (27.941, 108.256),
    "印江县": (27.998, 108.406), "德江县": (28.225, 108.117), "松桃县": (28.165, 109.202),
    "兴义市": (25.096, 104.895), "兴仁市": (25.433, 105.187), "普安县": (25.786, 104.956),
    "晴隆县": (25.834, 105.218), "贞丰县": (25.384, 105.654), "望谟县": (25.170, 106.099),
    "凯里市": (26.583, 107.980), "黄平县": (26.896, 107.902), "施秉县": (27.034, 108.126),
    "三穗县": (26.960, 108.682), "镇远县": (27.050, 108.427), "黎平县": (26.231, 109.136),
    "榕江县": (25.932, 108.520), "从江县": (25.750, 108.903), "雷山县": (26.378, 108.078),
    "都匀市": (26.258, 107.518), "福泉市": (26.699, 107.517), "荔波县": (25.413, 107.885),
    "贵定县": (26.578, 107.236), "瓮安县": (27.068, 107.475), "独山县": (25.828, 107.541),
    "平塘县": (25.832, 107.325), "罗甸县": (25.426, 106.752), "长顺县": (26.023, 106.452), "龙里县": (26.451, 106.977)
}

def conn_db():
    c=sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS notices(url TEXT PRIMARY KEY,title TEXT,published TEXT,area TEXT,kind TEXT,road TEXT,status TEXT,publisher TEXT,body TEXT,verified TEXT,source TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS logs(checked TEXT,source TEXT,result TEXT,count INTEGER)""")
    c.commit()
    return c

def clean(s): return re.sub(r"\s+"," ",s or "").strip()

def fetch(url):
    r=requests.get(url,timeout=20,headers={"User-Agent":"Mozilla/5.0"})
    r.raise_for_status()
    r.encoding=r.apparent_encoding or "utf-8"
    return r.text

def infer_area(s):
    a=[x for x in AREAS if x in s]
    return "、".join(a) if a else "贵州全省/未识别"

def infer_kind(s):
    if any(x in s for x in ("暴雨","大雨","特大暴雨")): return "暴雨/强降水"
    if any(x in s for x in ("大雾","浓雾","强浓雾")): return "大雾/低能见度"
    if any(x in s for x in ("凝冻","结冰","道路结冰")): return "凝冻/道路结冰"
    if any(x in s for x in ("雷电","大风","冰雹")): return "雷暴大风/强对流"
    if any(x in s for x in ("管制","封闭","封路")): return "道路管制"
    if any(x in s for x in ("暴雪","雨雪","积雪")): return "雨雪/积雪"
    return "天气/交通提示"

def collect(n):
    checked=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    soup=BeautifulSoup(fetch(TRAFFIC_URL),"html.parser")
    items=[]; seen=set()
    for a in soup.find_all("a",href=True):
        title=clean(a.get_text(" ",strip=True) or a.get("title",""))
        raw_href=a["href"]
        url = raw_href if raw_href.startswith("http") else urljoin(TRAFFIC_URL, raw_href)
        if not title or not any(k in title for k in KEYWORDS): continue
        if url in seen: continue
        seen.add(url); items.append((title,url))
        if len(items)>=n: break
    c=conn_db(); saved=0
    for title,url in items:
        try:
            page=BeautifulSoup(fetch(url),"html.parser")
            for tag in page(["script","style","nav","footer"]): tag.decompose()
            body=clean(page.get_text(" ",strip=True))
            full=title+" "+body
            roads=re.findall(r"(?:\b[GS]\d{1,4}\b|[\u4e00-\u9fa5]{2,8}(?:高速|国道|省道|大道))[^。；;]{0,50}",body)
            road="；".join(dict.fromkeys(roads[:8])) if roads else "未自动识别，请人工核对原文"
            pub="贵州省交通运输厅"
            m=re.search(r"来源：([^ ]{2,40})",body)
            if m: pub=m.group(1)
            
            c.execute("""INSERT INTO notices VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(url) DO UPDATE SET
              title=excluded.title,published=excluded.published,
              area=excluded.area,kind=excluded.kind,road=excluded.road,publisher=excluded.publisher,
              body=excluded.body,verified=excluded.verified""",
              (url,title,today_str,infer_area(full),infer_kind(full),road,"待人工核验",pub,body[:12000],checked,"交通厅网页采集"))
            saved+=1
        except Exception: pass
    c.execute("INSERT INTO logs VALUES(?,?,?,?)",(checked,TRAFFIC_URL,f"候选 {len(items)} 篇；写入/更新 {saved} 条",saved))
    c.commit(); c.close()
    return len(items),saved,checked

def fetch_weather_warnings():
    checked = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    saved = 0
    try:
        url = "https://product.weather.com.cn/alarm/grelease_data/10126.html"
        r = requests.get(url, timeout=10)
        r.encoding = "utf-8"
        m_list = re.findall(r'"(https://www\.weather\.com\.cn/alarm/newalarmcontent\.shtml\?file=[^"]+)"', r.text)
        c = conn_db()
        for warn_url in m_list[:25]:
            try:
                w_html = fetch(warn_url)
                w_soup = BeautifulSoup(w_html, "html.parser")
                title = clean(w_soup.find("h2").text if w_soup.find("h2") else "贵州气象预警")
                body = clean(w_soup.find("p").text if w_soup.find("p") else title)
                full = title + " " + body
                
                c.execute("""INSERT INTO notices VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(url) DO UPDATE SET
                title=excluded.title, published=excluded.published, area=excluded.area, kind=excluded.kind, body=excluded.body, verified=excluded.verified""",
                (warn_url, title, today_str, infer_area(full), infer_kind(full), "气象预警，影响区域道路及配送", "待人工核验", "贵州省气象局预警中心", body[:5000], checked, "气象预警自动同步"))
                saved += 1
            except:
                pass
        c.commit(); c.close()
        return True, f"成功抓取气象预警 {saved} 条！"
    except Exception as e:
        return False, str(e)

def fetch_weather_api():
    district_items = list(DISTRICT_COORDS.items())
    lats = ",".join(str(lat) for _, (lat, _) in district_items)
    lons = ",".join(str(lon) for _, (_, lon) in district_items)
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lats}&longitude={lons}&current=temperature_2m,precipitation,weather_code"
    checked = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    saved = 0
    c = conn_db()
    try:
        r = requests.get(url, timeout=12)
        data = r.json()
        if isinstance(data, list):
            for idx, res in enumerate(data):
                district_name = district_items[idx][0]
                current = res.get("current", {})
                temp = current.get("temperature_2m", "未知")
                precip = current.get("precipitation", 0)
                
                if precip > 0:
                    title = f"【降水监测】{district_name} 正在下雨：气温 {temp}°C，降水 {precip}mm"
                    kind = "暴雨/强降水"
                else:
                    title = f"【日常气温监测】{district_name} 气温 {temp}°C，无降水 ({precip}mm)"
                    kind = "天气/交通提示"
                    
                body = f"通过 API 实时监控【{district_name}】：当前气温 {temp} 摄氏度，降水量 {precip} 毫米。"
                url_key = f"https://api.open-meteo.com/{district_name}_auto"
                
                c.execute("""INSERT INTO notices VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(url) DO UPDATE SET
                  title=excluded.title, body=excluded.body, verified=excluded.verified, kind=excluded.kind""",
                  (url_key, title, today_str, district_name, kind, f"{district_name}气象监控", "已核验生效", "区县级气象API", body, checked, "区县API自动同步"))
                saved += 1
        c.commit(); c.close()
        return True, f"成功完成全省 {saved} 个三级区县实时气温巡检！"
    except Exception as e:
        c.close()
        return False, str(e)

def get_df():
    c=conn_db()
    df=pd.read_sql_query("SELECT title AS 公告标题,published AS 发布时间,area AS 地区,kind AS 风险类型,road AS 道路或路段,status AS 当前状态,publisher AS 发布单位,body AS 原文摘要,url AS 官方链接,verified AS 最后核验时间,source AS 采集方式 FROM notices ORDER BY published DESC",c)
    c.close(); return df

def get_logs():
    c=conn_db(); d=pd.read_sql_query("SELECT checked AS 检查时间,source AS 数据源,result AS 结果,count AS 记录数 FROM logs ORDER BY checked DESC LIMIT 100",c); c.close(); return d

def export(df):
    b=BytesIO()
    with pd.ExcelWriter(b,engine="openpyxl") as w:
        df.to_excel(w,index=False,sheet_name="风险公告")
        get_logs().to_excel(w,index=False,sheet_name="采集日志")
    return b.getvalue()

def save_weather(title, pubdate, area, kind, level, body, url):
    checked = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # 如果用户没有填发布时间，默认采用当前系统时间
    final_pubdate = pubdate.strip() if pubdate and pubdate.strip() else checked
    
    matched_area = area
    for district in DISTRICT_COORDS.keys():
        if area in district or district.replace("区","").replace("县","").replace("市","") == area:
            matched_area = district
            break
            
    c = conn_db()
    c.execute("""INSERT INTO notices VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(url) DO UPDATE SET
    title=excluded.title, published=excluded.published, area=excluded.area, kind=excluded.kind, body=excluded.body, verified=excluded.verified, status=excluded.status""",
    (url, title, final_pubdate, matched_area, f"{kind}（{level}）", "气象预警，影响区域道路及配送", "已核验生效", "以官方页面署名为准", body, checked, "人工核验录入"))
    c.commit(); c.close()

st.title("贵州天气与配送风险监控")
st.caption("V2 真实来源接入测试版（时间选填与强化反馈版）")

with st.sidebar:
    st.subheader("官方权威来源")
    st.markdown(f"[贵州交通出行提示预警]({TRAFFIC_URL})")
    st.markdown(f"[中国气象局灾害预警查询]({WEATHER_URL})")
    
    n = st.slider("每次最多检查公告数", 5, 40, 20, 5)
    st.divider()

    if st.button("🌧️ 【模拟测试】让指定区县开始下雨", use_container_width=True):
        c = conn_db()
        sim_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("""INSERT INTO notices VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(url) DO UPDATE SET
          title=excluded.title, body=excluded.body, kind=excluded.kind""",
          ("https://sim.rain/guiyang_test", "【模拟降雨测试】观山湖区突降暴雨，降水量达 25mm", sim_time, "观山湖区", "暴雨/强降水", "模拟降雨路段", "已核验生效", "模拟系统", "测试：观山湖区当前正在下大雨，道路湿滑，请注意配送安全。", sim_time, "模拟注入"))
        c.commit(); c.close()
        st.success("已成功在【观山湖区】注入一场模拟暴雨！")
        st.rerun()

    if st.button("一键完成三级区县天气巡检", use_container_width=True):
        with st.spinner("正在并发请求贵州全省所有三级区县气象数据……"):
            ok, msg = fetch_weather_api()
            if ok: st.success(msg); st.rerun()
            else: st.error(f"巡检失败：{msg}")

    if st.button("一键采集气象灾害预警(含大雾/暴雨)", use_container_width=True):
        with st.spinner("正在抓取官方大雾、暴雨等气象预警……"):
            ok, msg = fetch_weather_warnings()
            if ok: st.success(msg); st.rerun()
            else: st.error("抓取失败。")

    if st.button("采集交通管制与施工公告", use_container_width=True):
        try:
            with st.spinner("正在访问官方交通网页……"):
                found, saved, when = collect(n)
            st.success(f"候选公告 {found} 篇；新增/更新 {saved} 条。")
            st.rerun()
        except Exception as e:
            st.error(f"采集失败：{e}")

    st.divider()
    auto_inspect = st.checkbox("开启自动巡检（每隔 1 小时自动检查）", value=False)

if auto_inspect:
    logs_df = get_logs()
    should_auto_run = True
    if not logs_df.empty:
        try:
            last_dt = datetime.strptime(logs_df.iloc[0]["检查时间"], "%Y-%m-%d %H:%M:%S")
            if (datetime.now() - last_dt).total_seconds() < 3600: 
                should_auto_run = False
        except: 
            pass
    if should_auto_run:
        try: 
            collect(n)
            fetch_weather_api()
            fetch_weather_warnings()
        except: 
            pass

df = get_df(); logs = get_logs()
a, b, c = st.columns(3)
a.metric("已保存记录", len(df))
b.metric("待人工核验", int((df["当前状态"]=="待人工核验").sum()) if not df.empty else 0)
c.metric("采集日志", len(logs))

t1, t_map, t2, t3 = st.tabs(["风险清单", "🗺️ 三级区县联动风险地图", "录入气象预警", "采集日志"])

with t1:
    if df.empty:
        st.info("点击左侧按钮开始采集。")
    else:
        col1, col2 = st.columns([2, 1])
        with col1: q = st.text_input("搜索公告、地区或道路", placeholder="修文县、大方县、织金县、大雾", key="search_q")
        with col2: status_filter = st.selectbox("状态筛选", ["全部", "仅待人工核验", "仅已核验生效", "已作废/忽略"])
        
        v = df.copy()
        if status_filter == "仅待人工核验": v = v[v["当前状态"] == "待人工核验"]
        elif status_filter == "仅已核验生效": v = v[v["当前状态"] == "已核验生效"]
        elif status_filter == "已作废/忽略": v = v[v["当前状态"] == "已作废/忽略"]
        if q: v = v[v.astype(str).apply(lambda col: col.str.contains(q, case=False, regex=False)).any(axis=1)]

        st.dataframe(v, use_container_width=True, hide_index=True, column_config={"官方链接": st.column_config.LinkColumn("官方原文", display_text="🔗 点击打开官方原文")})
        
        with st.form("update_form"):
            selected_url = st.selectbox("选择要调整的公告（按官方链接）：", options=v["官方链接"].tolist() if not v.empty else [])
            new_status = st.radio("更改状态为：", ["待人工核验", "已核验生效", "已作废/忽略"], horizontal=True)
            if st.form_submit_button("更新状态") and selected_url:
                c = conn_db()
                c.execute("UPDATE notices SET status=? WHERE url=?", (new_status, selected_url))
                c.commit(); c.close()
                st.success("状态已更新！"); st.rerun()

# ── 🗺️ 矢量中文高德地图 + 优化排版（一段话一行） ──
with t_map:
    st.subheader("贵州省三级行政区（区县级）配送风险分布与多选联动分析")
    
    st.markdown("### 🔍 区县风险与天气多选联动检索")
    all_districts = list(DISTRICT_COORDS.keys())
    
    selected_districts = st.multiselect(
        "选择要重点关注的区县（支持多选，留空则默认展示全部受影响区县）：",
        options=all_districts,
        default=[]
    )
    
    map_df_filtered = pd.DataFrame()
    if not df.empty:
        valid_df = df[df["当前状态"] != "已作废/忽略"]
        if selected_districts:
            mask = valid_df["地区"].apply(lambda x: any(d in str(x) or str(x) in d for d in selected_districts))
            map_df_filtered = valid_df[mask]
        else:
            map_df_filtered = valid_df

    map_center = [26.8, 106.8]
    if selected_districts and selected_districts[0] in DISTRICT_COORDS:
        map_center = list(DISTRICT_COORDS[selected_districts[0]])

    m = folium.Map(
        location=map_center,
        zoom_start=8 if selected_districts else 7,
        tiles='https://webrd02.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}',
        attr='高德地图'
    )
    
    if not map_df_filtered.empty:
        district_grouped = {}
        for _, row in map_df_filtered.iterrows():
            area_str = str(row["地区"])
            for district_name, (lat, lon) in DISTRICT_COORDS.items():
                pure_name = district_name.replace("区","").replace("县","").replace("市","")
                if district_name in area_str or pure_name == area_str:
                    if district_name not in district_grouped:
                        district_grouped[district_name] = {"lat": lat, "lon": lon, "items": []}
                    district_grouped[district_name]["items"].append(row)

        for district_name, ddata in district_grouped.items():
            lat, lon = ddata["lat"], ddata["lon"]
            items = ddata["items"]
            
            has_fog_or_rain = any(any(k in str(it["风险类型"]) or k in str(it["公告标题"]) for k in ["大雾", "暴雨", "雷电", "冰雹"]) for it in items)
            has_traffic_block = any(any(k in str(it["风险类型"]) or k in str(it["公告标题"]) for k in ["管制", "封闭", "封路"]) for it in items)
            
            if has_fog_or_rain:
                color = "#0055FF"      
                fill_color = "#3399FF"
                icon_name = "cloud"    
                icon_color = "blue"
            elif has_traffic_block:
                color = "#E60000"      
                fill_color = "#FF3333"
                icon_name = "warning-sign"
                icon_color = "red"
            else:
                color = "#3388FF"      
                fill_color = "#66A3FF"
                icon_name = "info-sign"
                icon_color = "cadetblue"
            
            # 排版优化：一段话一行，表达清晰
            popup_html = f"<div style='width:240px;'><b>📍 【{district_name}】</b><br>当前包含 <b>{len(items)}</b> 条风险记录：<hr style='margin:4px 0;'>"
            for idx, it in enumerate(items, 1):
                popup_html += f"<b>{idx}. 类型：</b>{it['风险类型']}<br>"
                popup_html += f"<b>标题：</b>{it['公告标题']}<br>"
                popup_html += f"<b>时间：</b>{it['发布时间']}<br><br>"
            popup_html += "</div>"
            
            folium.Circle(
                location=[lat, lon],
                radius=14000,
                color=color,
                fill=True,
                fill_color=fill_color,
                fill_opacity=0.45,
                popup=folium.Popup(popup_html, max_width=300)
            ).add_to(m)
            
            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(popup_html, max_width=300),
                icon=folium.Icon(color=icon_color, icon=icon_name)
            ).add_to(m)
    
    st_data = st_folium(m, width=1200, height=500)
    
    st.markdown("---")
    st.markdown("### 📋 联动检索结果明细表（与上方多选地图实时对应）")
    if not map_df_filtered.empty:
        st.dataframe(
            map_df_filtered[["地区", "风险类型", "当前状态", "道路或路段", "公告标题", "发布时间", "最后核验时间"]],
            use_container_width=True,
            hide_index=True
        )
        st.download_button("导出当前联动筛选结果 Excel", export(map_df_filtered), file_name=f"贵州区县联动风险台账_{datetime.now():%Y%m%d_%H%M}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info("当前所选区县暂无匹配的风险或天气预警记录。")

# ── 💡 增强反馈与时间选填的录入表单 ──
with t2:
    st.markdown("先在官方页面核实预警仍然有效，再手工录入。**发布时间如不填写，将自动采用当前系统时间。**")
    with st.form("weather_form"):
        title = st.text_input("预警标题*")
        pubdate = st.text_input("发布时间（可选，留空则自动用当前系统时间）", placeholder="例如：2026-10-25 10:30")
        area = st.selectbox("地区*", ["贵州全省"] + AREAS + ["其他/区县"])
        kind = st.selectbox("预警类型*", ["暴雨", "大雾", "道路结冰", "暴雪", "寒潮", "大风", "雷电", "其他"])
        level = st.selectbox("等级*", ["蓝色", "黄色", "橙色", "红色", "未知"])
        body = st.text_area("官方原文和影响范围*")
        url = st.text_input("官方原文链接*")
        
        submitted = st.form_submit_button("保存已核验预警")
        if submitted:
            if not title.strip() or not body.strip() or not url.strip():
                st.error("❌ 保存失败：请完整填写必填项（预警标题、原文、官方链接）！")
            elif not url.startswith("https://") and not url.startswith("http://"):
                st.error("❌ 保存失败：官方原文链接必须以 http:// 或 https:// 开头！")
            else:
                save_weather(title.strip(), pubdate, area, kind, level, body.strip(), url.strip())
                st.success("✅ 预警保存成功！已自动同步至风险清单与地图中。")
                st.toast("预警保存成功！", icon="✅")

with t3:
    if logs.empty: st.info("暂无采集日志。")
    else: st.dataframe(logs, use_container_width=True, hide_index=True)

st.divider()
st.caption("后续步骤：配置微信/钉钉自动化通知推送。")