import streamlit as st
import streamlit.components.v1 as components
import folium
import csv
import io
import json
import urllib.request
from collections import defaultdict

st.set_page_config(page_title="방한 외국인 세계지도 시각화", layout="wide")
st.title("🗺️ 방한 외국인 국가별 현황 (세계 지도)")

# 전 세계 GeoJSON 데이터 캐싱 로드 (순수 urllib & json 사용, Pandas/Numpy 배제)
@st.cache_data
def load_world_geojson():
    url = "https://raw.githubusercontent.com/python-visualization/folium/master/examples/data/world-countries.json"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode('utf-8'))

# 한글 국명 -> GeoJSON 표준 영문 국명 매핑 테이블
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

# 방문객 수에 따른 파란색 진하기 계산 함수
def get_color(value, max_val):
    if value <= 0 or max_val <= 0:
        return "#f1f3f5"
    ratio = value / max_val
    if ratio > 0.5:
        return "#08306b"   # 매우 진한 파랑
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
        return "#c6dbef"   # 연한 파랑

# 1. 파일 업로드
uploaded_file = st.file_uploader("방한 외국인 CSV 파일을 업로드하세요", type=["csv"])

if uploaded_file is not None:
    content = uploaded_file.getvalue().decode('utf-8-sig')
    csv_reader = list(csv.DictReader(io.StringIO(content)))

    if not csv_reader:
        st.error("CSV 파일이 비어 있습니다.")
    else:
        # 2. 파일 내용 미리보기
        st.subheader("📋 데이터 미리보기")
        headers = list(csv_reader[0].keys())
        preview_rows = csv_reader[:6]

        table_html = """
        <table style='width:100%; border-collapse: collapse; font-family: sans-serif; font-size: 14px;'>
            <tr style='background-color: #f1f3f5;'>
        """
        for h in headers:
            table_html += f"<th style='border: 1px solid #dee2e6; padding: 8px; text-align: left;'>{h}</th>"
        table_html += "</tr>"

        for row in preview_rows:
            table_html += "<tr>"
            for h in headers:
                table_html += f"<td style='border: 1px solid #dee2e6; padding: 8px;'>{row.get(h, '')}</td>"
            table_html += "</tr>"
        table_html += "</table>"
        st.markdown(table_html, unsafe_allow_html=True)

        # 컬럼 자동 인식
        visitor_col = next((c for c in ['방한 외래관광객', '방문객수', '관광객', '방문자수'] if c in headers), None)
        country_col = next((c for c in ['국가', '국적', 'country'] if c in headers), None)
        purpose_col = next((c for c in ['방문목적', '목적', 'purpose'] if c in headers), None)

        # 데이터 집계
        country_data_map = {}
        original_country_map = {}
        total_list = []

        for row in csv_reader:
            c_name = row.get(country_col, '').strip() if country_col else ''
            if not c_name or c_name in ['총계', '합계', '전체']:
                continue

            raw_val = row.get(visitor_col, 0) if visitor_col else 0
            try:
                visitors = float(str(raw_val).replace(',', '').strip())
            except ValueError:
                visitors = 0

            eng_name = KOR_TO_ENG.get(c_name, c_name)
            country_data_map[eng_name] = country_data_map.get(eng_name, 0) + visitors
            original_country_map[eng_name] = c_name
            total_list.append((c_name, visitors))

        max_visitors = max(country_data_map.values()) if country_data_map else 1

        # 3. 시각화 영역
        st.subheader("📊 데이터 시각화")

        # (1) Folium 지도 (Numpy/Pandas를 우회하는 folium.GeoJson 사용)
        st.markdown("#### 🌍 국가별 방한 외국인 수")
        world_map = folium.Map(location=[25.0, 10.0], zoom_start=2, tiles="OpenStreetMap")

        try:
            geo_data = load_world_geojson()

            # GeoJSON의 각 feature 속성에 방문객 수 주입
            for feature in geo_data['features']:
                name = feature['properties']['name']
                v_count = country_data_map.get(name, 0)
                kor_name = original_country_map.get(name, name)
                feature['properties']['visitors'] = v_count
                feature['properties']['display_name'] = f"{kor_name} ({name})"
                feature['properties']['display_visitors'] = f"{int(v_count):,}명" if v_count > 0 else "집계 없음"

            # 순수 Python 스타일링 함수
            def style_fn(feature):
                cnt = feature['properties'].get('visitors', 0)
                return {
                    'fillColor': get_color(cnt, max_visitors),
                    'color': '#888888',
                    'weight': 0.6,
                    'fillOpacity': 0.75 if cnt > 0 else 0.15
                }

            # 툴팁 및 스타일 적용
            folium.GeoJson(
                geo_data,
                style_function=style_fn,
                tooltip=folium.GeoJsonTooltip(
                    fields=['display_name', 'display_visitors'],
                    aliases=['국가:', '방문객 수:'],
                    style="font-size: 13px; font-weight: bold;"
                )
            ).add_to(world_map)

        except Exception as e:
            st.error(f"지도 데이터를 로드하는 중 문제가 발생했습니다: {e}")

        # Streamlit HTML 컴포넌트로 지도 출력
        map_html = world_map.get_root().render()
        components.html(map_html, height=520, scrolling=False)

        # (2) 원 그래프 영역
        st.markdown("#### 🥧 방한 외국인 비율")

        if purpose_col:
            st.caption("방문 목적별 점유율 현황입니다.")
            purpose_counts = defaultdict(float)
            for row in csv_reader:
                p = row.get(purpose_col, '').strip()
                if p:
                    try:
                        v = float(str(row.get(visitor_col, 1)).replace(',', '').strip())
                    except ValueError:
                        v = 1.0
                    purpose_counts[p] += v
            chart_labels = list(purpose_counts.keys())
            chart_values = list(purpose_counts.values())
        else:
            # 방문목적 컬럼이 없으므로 상위 7개국 + 기타 국가로 도넛 차트 생성
            st.caption("※ 업로드된 데이터에 방문 목적 컬럼이 없어 **상위 국가별 점유율**을 원 그래프로 표시합니다.")
            sorted_data = sorted(total_list, key=lambda x: x[1], reverse=True)
            top_countries = sorted_data[:7]
            other_sum = sum(x[1] for x in sorted_data[7:])

            chart_labels = [c[0] for c in top_countries] + ["기타 국가"]
            chart_values = [int(c[1]) for c in top_countries] + [int(other_sum)]

        # Chart.js 도넛 차트 렌더링
        chart_html = f"""
        <div style="width: 480px; margin: auto;">
            <canvas id="touristChart"></canvas>
        </div>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <script>
            const ctx = document.getElementById('touristChart').getContext('2d');
            new Chart(ctx, {{
                type: 'doughnut',
                data: {{
                    labels: {json.dumps(chart_labels, ensure_ascii=False)},
                    datasets: [{{
                        data: {json.dumps(chart_values)},
                        backgroundColor: [
                            '#08306b', '#08519c', '#2171b5', '#4292c6', 
                            '#6baed6', '#9ecae1', '#c6dbef', '#e9ecef'
                        ],
                        borderColor: '#ffffff',
                        borderWidth: 2
                    }}]
                }},
                options: {{
                    responsive: true,
                    plugins: {{
                        legend: {{
                            position: 'right',
                            labels: {{ font: {{ size: 13 }} }}
                        }}
                    }}
                }}
            }});
        </script>
        """
        components.html(chart_html, height=360)
