import os
import pandas as pd
import geopandas as gpd
import folium
from folium.plugins import MarkerCluster
import streamlit as st
from streamlit_folium import folium_static

# 스트림릿 페이지 설정
st.set_page_config(page_title="사하구 경로당 현황", layout="wide")

# 한글 글꼴 설정
import matplotlib.pyplot as plt
plt.rc('font', family='Malgun Gothic')

# 데이터 로드 함수
def load_data(uploaded_file):
    df = pd.read_excel(uploaded_file)
    if '일자' in df.columns:
        df = df[df['일자'].notnull()]  # 일자 열의 NaN 값 제거
        df['일자'] = pd.to_datetime(df['일자'], errors='coerce')  # 일자 열을 datetime으로 변환
    return df

# 지오JSON 로드 함수
@st.cache_resource
def load_geojson():
    # GeoJSON 파일 경로 설정
    geojson_file_path = 'infile/HangJeongDong_ver20230701.geojson'
    gdf = gpd.read_file(geojson_file_path)
    saha_gu = gdf[gdf['sggnm'].str.contains('사하구')]
    saha_gu = saha_gu.to_crs(epsg=4326)
    return saha_gu

# 지오JSON 데이터 로드
saha_gu = load_geojson()

col_1, col_2 = st.columns(2)
with col_1:
    # 엑셀 파일 업로드 위젯
    uploaded_file = st.file_uploader("엑셀 파일 업로드", type=["xlsx"])

# 세션 상태에 파일 저장
if uploaded_file is not None:
    st.session_state['uploaded_file'] = uploaded_file

# 세션 상태에 파일이 저장되어 있으면 로드
if 'uploaded_file' in st.session_state:
    df = load_data(st.session_state['uploaded_file'])

    # 마커 클러스터링 여부 선택 옵션
    use_marker_cluster = st.sidebar.radio("마커 클러스터 사용 여부", ("사용", "사용 안 함"))

    st.sidebar.markdown("---")
    # Streamlit 옵션 설정
    st.sidebar.header("필터 옵션")
    new_filter_column = st.sidebar.selectbox("필터 컬럼명 추가", df.columns.tolist())
    if 'filters' not in st.session_state:
        st.session_state['filters'] = []

    if st.sidebar.button("필터 추가"):
        if new_filter_column and new_filter_column not in st.session_state['filters']:
            st.session_state['filters'].append(new_filter_column)
    
    # 동적 필터링 옵션
    selected_filters = {}
    for filter_col in st.session_state['filters']:
        unique_values = df[filter_col].dropna().unique()
        selected_values = st.sidebar.multiselect(f"{filter_col}", unique_values, default=unique_values)
        selected_filters[filter_col] = selected_values

    # 건축 연도 옵션
    if '일자' in df.columns:
        min_year = df['일자'].dt.year.min()
        max_year = df['일자'].dt.year.max()
        selected_year_range = st.sidebar.slider("건축 연도", min_year, max_year, (min_year, max_year))
        filtered_df = df[(df['일자'].dt.year >= selected_year_range[0]) & (df['일자'].dt.year <= selected_year_range[1])]
    else:
        filtered_df = df.copy()

    # 필터링
    for filter_col, selected_values in selected_filters.items():
        filtered_df = filtered_df[filtered_df[filter_col].isin(selected_values)]

    st.sidebar.markdown("---")
    st.sidebar.header("팝업 옵션")
    # 팝업에 표시할 필드 선택
    popup_fields = st.sidebar.multiselect("팝업에 표시할 필드 선택", df.columns.tolist(), default=["시설명", "주소"])

    if not filtered_df.empty:
        # 경로당 위치의 위도와 경도의 평균값 계산
        mean_lat = filtered_df['위도'].mean()
        mean_lon = filtered_df['경도'].mean()

        # Folium 지도 생성
        m = folium.Map(location=[mean_lat, mean_lon], zoom_start=12, tiles='cartodbpositron', attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors & <a href="https://cartodb.com/attributions">CartoDB</a>')

        # 사하구 경계 추가
        folium.GeoJson(
            saha_gu,
            name='geojson',
            style_function=lambda x: {'color': '#FF6347', 'weight': 2.5}
        ).add_to(m)

        # 마커 클러스터 사용 여부에 따라 마커 추가
        if use_marker_cluster == "사용":
            marker_cluster = MarkerCluster().add_to(m)

        # 필터링된 경로당 위치에 마커 추가
        for idx, row in filtered_df.iterrows():
            if not pd.isna(row['위도']) and not pd.isna(row['경도']):
                # 팝업 HTML 설정
                popup_html = f"<div style='width: 250px; height: auto;'>"
                for field in popup_fields:
                    value = row[field]
                    if isinstance(value, pd.Timestamp):
                        value = value.strftime('%Y-%m-%d')
                    popup_html += f"<p style='color: blue; font-size: 12px;'>{field}: {value}</p>"
                popup_html += "</div>"

                # 툴팁을 항상 보이도록 설정
                tooltip = folium.Tooltip(f"<b style='white-space: nowrap;'>{row['시설명']}</b>", permanent=True)
                
                marker = folium.Marker(
                    location=[row['위도'], row['경도']],
                    tooltip=tooltip,
                    popup=folium.Popup(popup_html, max_width=400)
                )

                if use_marker_cluster == "사용":
                    marker.add_to(marker_cluster)
                else:
                    marker.add_to(m)

        # Streamlit을 사용하여 지도 출력
        st.title("사하구 경로당 현황")
        st.markdown("아래 지도는 사하구의 경로당 위치와 정보를 보여줍니다.")

        # 지도 표시
        folium_static(m, width=1200, height=800)

        # 데이터프레임 전체 출력
        filtered_df['일자'] = filtered_df['일자'].dt.strftime('%Y-%m-%d')
        st.dataframe(filtered_df, width=1200)
    else:
        st.warning("선택된 필터에 맞는 데이터가 없습니다. 다른 필터를 선택해 주세요.")
else:
    col_1, col_2 = st.columns(2)
    with col_1:
        st.info("엑셀 파일을 업로드해 주세요.")
