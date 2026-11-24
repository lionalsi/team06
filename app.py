import streamlit as st
import streamlit.components.v1 as components
import folium
import csv
import io
import json
import urllib.request
from collections import defaultdict

st.set_page_config(page_title="방한 외국인 세계지도 및 목적 시각화", layout="wide")
st.title("🗺️ 방한 외국인 현황 시각화 (국가별 지도 & 방문 목적)")

# 전 세계 GeoJSON 데이터 캐싱 로드 (Pandas/Numpy 배제)
@st.cache_data
def load_world_geojson():
    url = "https://raw.githubusercontent.com/python-visualization/folium/master/examples/data/world-countries.json"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode('utf-8'))

# 한글 국명 -> GeoJSON 영문 국명 매핑
KOR_TO_ENG = {
    "중국": "China", "일본": "Japan", "대만": "Taiwan", "미국": "United States of America",
    "홍콩": "Hong Kong", "필리핀": "Philippines", "베트남": "Vietnam", "싱가포르": "Singapore",
    "인도네시아": "Indonesia", "태국": "Thailand", "말레이시아": "Malaysia", "캐나다": "Canada",
    "호주": "Australia", "러시아": "Russia", "인도": "India", "영국": "United Kingdom",
    "프랑스": "France", "독일": "Germany", "몽골": "Mongolia", "미얀마": "Myanmar",
    "이탈리아": "Italy", "멕시코": "Mexico", "튀르키예": "Turkey", "우즈베키스탄": "Uzbekistan",
    "카자흐스탄": "Kazakhstan", "네덜란드": "Netherlands", "스페인": "Spain", "폴란드": "Poland",
    "네팔": "Nepal", "캄보디아": "Cambodia", "브라질": "Brazil", "뉴질랜드": "New Zealand",
    "라오스": "Laos", "스위스": "Switzerland", "스웨덴": "Sweden", "방글라데시": "Bangladesh",
    "이스라엘": "Israel", "스리랑카": "Sri Lanka", "우크라이나": "Ukraine", "벨기에": "Belgium",
    "덴마크": "Denmark", "루마니아": "Romania", "포르투갈": "Portugal", "남아프리카공화국": "South Africa",
    "노르웨이": "Norway", "오스트리아": "Austria", "콜롬비아": "Colombia", "사우디아라비아": "Saudi Arabia",
    "핀란드": "Finland", "아일랜드": "Ireland", "체코": "Czech Republic", "파키스탄": "Pakistan",
    "그리스": "Greece", "아르헨티나": "Argentina", "헝가리": "Hungary", "에티오피아": "Ethiopia",
    "칠레": "Chile", "페루": "Peru", "아랍에미리트": "United Arab Emirates", "이집트": "Egypt"
}

def get_color(value, max_val):
    if value <= 0 or max_val <= 0:
        return "#f1f3f5"
    ratio = value / max_val
    if ratio > 0.5:
        return "#08306b"
    elif ratio > 0.2:
        return "#08519c"
    elif ratio > 0.08:
        return "#2171b5"
    elif ratio > 0.03:
        return "#4292c6"
    elif ratio > 0.01:
        return "#6baed6"
    elif ratio > 0.002:
        return "#9ecae1"
    else:
        return "#c6dbef"

def render_preview_table(rows, headers, max_rows=5):
    table_html = """
    <table style='width:100%; border-collapse: collapse; font-family: sans-serif; font-size: 13px; margin-bottom: 12px;'>
        <tr style='background-color: #f1f3f5; color: #212529;'>
    """
    for h in headers:
        table_html += f"<th style='border: 1px solid #dee2e6; padding: 7px; text-align: left;'>{h}</th>"
    table_html += "</tr>"

    for row in rows[:max_rows]:
        table_html += "<tr>"
        for h in headers:
            table_html += f"<td style='border: 1px solid #dee2e6; padding: 7px;'>{row.get(h, '')}</td>"
        table_html += "</tr>"
    table_html += "</table>"
    st.markdown(table_html, unsafe_allow_html=True)

def parse_csv(uploaded_file):
    raw_bytes = uploaded_file.getvalue()
    for enc in ['utf-8-sig', 'cp949', 'euc-kr']:
        try:
            content = raw_bytes.decode(enc)
            return list(csv.DictReader(io.StringIO(content)))
        except UnicodeDecodeError:
            continue
    return []

# ==========================================
# 1. 파일 업로드 영역 (국가별 / 목적별 분리)
# ==========================================
st.subheader("📁 1. 데이터 파일 업로드")
col1, col2 = st.columns(2)

with col1:
    country_file = st.file_uploader("🌍 국가별 방한 외국인 CSV 업로드", type=["csv"], key="country_csv")

with col2:
    purpose_file = st.file_uploader("🎯 방문 목적별 방한 외국인 CSV 업로드", type=["csv"], key="purpose_csv")

# ==========================================
# 2. 파일 내용 미리보기 영역
# ==========================================
if country_file is not None or purpose_file is not None:
    st.subheader("📋 2. 업로드 데이터 미리보기")
    p_col1, p_col2 = st.columns(2)

    country_rows = []
    purpose_rows = []

    if country_file is not None:
        country_rows = parse_csv(country_file)
        with p_col1:
            st.markdown("**[국가별 데이터 미리보기]**")
            if country_rows:
                render_preview_table(country_rows, list(country_rows[0].keys()))

    if purpose_file is not None:
        purpose_rows = parse_csv(purpose_file)
        with p_col2:
            st.markdown("**[방문 목적별 데이터 미리보기]**")
            if purpose_rows:
                render_preview_table(purpose_rows, list(purpose_rows[0].keys()))

    # ==========================================
    # 3. 시각화 영역
    # ==========================================
    st.subheader("📊 3. 데이터 시각화")

    # (1) 국가별 세계 지도 시각화
    if country_rows:
        st.markdown("#### 🌍 국가별 방한 외국인 수 (세계 지도)")
        c_headers = list(country_rows[0].keys())
        visitor_col = next((c for c in ['방한 외래관광객', '방문객수', '관광객', '방문자수', '인원'] if c in c_headers), None)
        country_col = next((c for c in ['국가', '국적', 'country'] if c in c_headers), None)

        country_data_map = {}
        original_country_map = {}

        for row in country_rows:
            c_name = row.get(country_col, '').strip() if country_col else ''
            if not c_name or c_name in ['총계', '합계', '전체']:
                continue
            try:
                visitors = float(str(row.get(visitor_col, 0)).replace(',', '').strip())
            except ValueError:
                visitors = 0

            eng_name = KOR_TO_ENG.get(c_name, c_name)
            country_data_map[eng_name] = country_data_map.get(eng_name, 0) + visitors
            original_country_map[eng_name] = c_name

        max_visitors = max(country_data_map.values()) if country_data_map else 1
        world_map = folium.Map(location=[25.0, 10.0], zoom_start=2, tiles="OpenStreetMap")

        try:
            geo_data = load_world_geojson()
            for feature in geo_data['features']:
                name = feature['properties']['name']
                v_count = country_data_map.get(name, 0)
                kor_name = original_country_map.get(name, name)
                feature['properties']['visitors'] = v_count
                feature['properties']['display_name'] = f"{kor_name} ({name})"
                feature['properties']['display_visitors'] = f"{int(v_count):,}명" if v_count > 0 else "집계 없음"

            folium.GeoJson(
                geo_data,
                style_function=lambda feature: {
                    'fillColor': get_color(feature['properties'].get('visitors', 0), max_visitors),
                    'color': '#888888',
                    'weight': 0.6,
                    'fillOpacity': 0.75 if feature['properties'].get('visitors', 0) > 0 else 0.15
                },
                tooltip=folium.GeoJsonTooltip(
                    fields=['display_name', 'display_visitors'],
                    aliases=['국가:', '방문객 수:'],
                    style="font-size: 13px; font-weight: bold;"
                )
            ).add_to(world_map)

            components.html(world_map.get_root().render(), height=500, scrolling=False)
        except Exception as e:
            st.error(f"지도 렌더링 오류: {e}")

    # (2) 방문 목적별 원 그래프 시각화 (수 & 비율 표시, 잘림 방지)
    if purpose_rows:
        st.markdown("#### 🎯 방한 외국인 방문 목적별 수 및 비율")
        p_headers = list(purpose_rows[0].keys())

        purpose_col = next((c for c in ['방문목적', '입국목적', '목적', '구분', '항목', 'purpose'] if c in p_headers), p_headers[0])
        p_visitor_col = next((c for c in ['방한 외래관광객', '방문객수', '관광객', '방문자수', '인원', '수'] if c in p_headers), None)

        if p_visitor_col is None:
            for h in p_headers:
                if h != purpose_col:
                    try:
                        float(str(purpose_rows[0][h]).replace(',', '').strip())
                        p_visitor_col = h
                        break
                    except ValueError:
                        continue

        purpose_counts = defaultdict(float)
        for row in purpose_rows:
            p_name = row.get(purpose_col, '').strip()
            if not p_name or p_name in ['총계', '합계', '전체']:
                continue
            try:
                val = float(str(row.get(p_visitor_col, 0)).replace(',', '').strip())
            except ValueError:
                val = 0
            purpose_counts[p_name] += val

        if purpose_counts:
            labels = list(purpose_counts.keys())
            values = [int(round(v)) for v in purpose_counts.values()]
            total_purpose = sum(values) if sum(values) > 0 else 1

            legend_labels = [
                f"{lbl}: {val:,}명 ({(val / total_purpose) * 100:.1f}%)"
                for lbl, val in zip(labels, values)
            ]

            chart_html = f"""
            <div style="width: 720px; height: 430px; margin: 0 auto; background-color: #ffffff; padding: 20px; border-radius: 12px; box-sizing: border-box;">
                <canvas id="purposePieChart"></canvas>
            </div>
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
            <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2"></script>
            <script>
                Chart.register(ChartDataLabels);
                const ctx = document.getElementById('purposePieChart').getContext('2d');
                const rawLabels = {json.dumps(labels, ensure_ascii=False)};
                const rawValues = {json.dumps(values)};
                const total = {total_purpose};

                new Chart(ctx, {{
                    type: 'pie',
                    data: {{
                        labels: {json.dumps(legend_labels, ensure_ascii=False)},
                        datasets: [{{
                            data: rawValues,
                            backgroundColor: [
                                '#08306b', '#08519c', '#2171b5', '#4292c6',
                                '#6baed6', '#9ecae1', '#c6dbef', '#dee2e6'
                            ],
                            borderColor: '#ffffff',
                            borderWidth: 2
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        layout: {{
                            padding: 10
                        }},
                        plugins: {{
                            legend: {{
                                position: 'right',
                                labels: {{
                                    color: '#212529',
                                    font: {{ size: 13, weight: '500' }},
                                    padding: 14
                                }}
                            }},
                            tooltip: {{
                                callbacks: {{
                                    label: function(context) {{
                                        const idx = context.dataIndex;
                                        const val = rawValues[idx];
                                        const pct = ((val / total) * 100).toFixed(1);
                                        return ` ${{rawLabels[idx]}}: ${{val.toLocaleString()}}명 (${{pct}}%)`;
                                    }}
                                }}
                            }},
                            datalabels: {{
                                color: '#ffffff',
                                font: {{ weight: 'bold', size: 12 }},
                                formatter: function(value, context) {{
                                    const pct = ((value / total) * 100).toFixed(1);
                                    if (pct < 4.0) return '';
                                    return pct + '%';
                                }}
                            }}
                        }}
                    }}
                }});
            </script>
            """
            components.html(chart_html, height=460, scrolling=False)
        else:
            st.warning("목적별 인원 데이터를 집계할 수 없습니다. CSV의 컬럼명을 확인해 주세요.")
