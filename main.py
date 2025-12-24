import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import unicodedata
import io
import numpy as np

# 한글 폰트 깨짐 방지
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR&display=swap');
html, body, [class*="css"] {
    font-family: 'Noto Sans KR', 'Malgun Gothic', sans-serif;
}
</style>
""", unsafe_allow_html=True)

# 데이터 로딩 함수
@st.cache_data
def load_data():
    data_dir = Path("data")
    
    # 파일 이름을 NFC/NFD 양방향 비교를 통해 안전하게 처리
    files = [file for file in data_dir.iterdir() if unicodedata.normalize("NFC", file.name) == file.name]
    env_files = [file for file in files if file.suffix == '.csv']
    growth_file = [file for file in files if file.suffix == '.xlsx'][0]

    env_data = {}
    for file in env_files:
        school_name = file.stem
        env_data[school_name] = pd.read_csv(file)

    # 생육 결과 데이터
    growth_data = pd.read_excel(growth_file, sheet_name=None)
    return env_data, growth_data

# 데이터 로딩
env_data, growth_data = load_data()

# 사이드바에서 학교 선택
school_names = ["전체", "송도고", "하늘고", "아라고", "동산고"]
selected_school = st.sidebar.selectbox("학교 선택", school_names)

# 제목
st.title("🌱 극지식물 최적 EC 농도 연구")
st.write("이 대시보드는 극지식물의 EC 농도에 따른 성장 결과를 분석하는 대시보드입니다.")

# Tab 1: 📖 실험 개요
tab1, tab2, tab3 = st.tabs(["📖 실험 개요", "🌡️ 환경 데이터", "📊 생육 결과"])

# Tab 1: 실험 개요
with tab1:
    st.header("연구 배경 및 목적")
    st.write("""
    - 극지식물의 최적 EC 농도를 연구하여 성장에 미치는 영향을 분석합니다.
    - 다양한 학교에서 EC 농도를 다르게 설정하여 실험을 진행하였으며, 각 학교의 데이터를 비교합니다.
    """)
    
    # 학교별 EC 조건
    ec_conditions = {
        "송도고": {"EC": 1.0, "color": "blue"},
        "하늘고": {"EC": 2.0, "color": "green"},
        "아라고": {"EC": 4.0, "color": "red"},
        "동산고": {"EC": 8.0, "color": "orange"}
    }

    if selected_school == "전체":
        school_ec_df = pd.DataFrame(ec_conditions).T
    else:
        school_ec_df = pd.DataFrame([ec_conditions[selected_school]], index=[selected_school])

    st.write(school_ec_df)

    # 주요 지표 카드
    total_plants = sum([len(df) for df in growth_data.values()])
    avg_temp = np.mean([env_data[school]["temperature"].mean() for school in env_data])
    avg_humidity = np.mean([env_data[school]["humidity"].mean() for school in env_data])
    optimal_ec = 2.0  # 하늘고의 EC는 최적값으로 설정

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("총 개체수", total_plants)
    with col2:
        st.metric("평균 온도", f"{avg_temp:.2f}°C")
    with col3:
        st.metric("평균 습도", f"{avg_humidity:.2f}%")
    with col4:
        st.metric("최적 EC", f"{optimal_ec} (하늘고)")

# Tab 2: 환경 데이터
with tab2:
    st.header("학교별 환경 평균 비교")

    # 선택된 학교의 환경 데이터 필터링
    selected_env_data = env_data[selected_school] if selected_school != "전체" else pd.concat(list(env_data.values()))

    # 환경 데이터 서브플롯
    fig = make_subplots(rows=2, cols=2,
                        subplot_titles=["평균 온도", "평균 습도", "평균 pH", "목표 EC vs 실측 EC"])

    fig.add_trace(go.Bar(x=selected_env_data.groupby('time')['temperature'].mean().index,
                         y=selected_env_data.groupby('time')['temperature'].mean(), name="평균 온도"), row=1, col=1)
    fig.add_trace(go.Bar(x=selected_env_data.groupby('time')['humidity'].mean().index,
                         y=selected_env_data.groupby('time')['humidity'].mean(), name="평균 습도"), row=1, col=2)
    fig.add_trace(go.Bar(x=selected_env_data.groupby('time')['ph'].mean().index,
                         y=selected_env_data.groupby('time')['ph'].mean(), name="평균 pH"), row=2, col=1)
    
    # 목표 EC vs 실측 EC
    for school, data in env_data.items():
        fig.add_trace(go.Bar(x=data['time'], y=data['ec'], name=f"{school} 실측 EC"), row=2, col=2)

    fig.update_layout(title_text="환경 데이터 분석", showlegend=True)
    st.plotly_chart(fig)

    # 시계열 데이터
    st.subheader(f"{selected_school} 시계열 데이터")
    if selected_school != "전체":
        selected_school_data = env_data[selected_school]
        fig2 = make_subplots(rows=1, cols=3, subplot_titles=["온도 변화", "습도 변화", "EC 변화"])
        
        fig2.add_trace(go.Scatter(x=selected_school_data['time'], y=selected_school_data['temperature'], mode='lines', name='온도'), row=1, col=1)
        fig2.add_trace(go.Scatter(x=selected_school_data['time'], y=selected_school_data['humidity'], mode='lines', name='습도'), row=1, col=2)
        fig2.add_trace(go.Scatter(x=selected_school_data['time'], y=selected_school_data['ec'], mode='lines', name='EC'), row=1, col=3)
        
        fig2.update_layout(title_text=f"{selected_school} 환경 시계열 분석")
        st.plotly_chart(fig2)

# Tab 3: 생육 결과
with tab3:
    st.header("학교별 생육 결과")
    
    # 생육 결과 분석
    growth_data_filtered = growth_data[selected_school] if selected_school != "전체" else pd.concat(growth_data.values())

    # 컬럼 이름 확인 및 정리
    growth_data_filtered.columns = growth_data_filtered.columns.str.strip()  # 공백 제거
    growth_data_filtered.columns = growth_data_filtered.columns.str.replace(" ", "")  # 공백 제거

    # EC와 생중량 컬럼이 실제로 존재하는지 확인
    if 'EC' in growth_data_filtered.columns and '생중량' in growth_data_filtered.columns:
        # 생중량 분석
        growth_fig = make_subplots(rows=2, cols=2,
                                   subplot_titles=["평균 생중량", "평균 잎 수", "평균 지상부 길이", "개체수 비교"])
        
        growth_fig.add_trace(go.Bar(x=growth_data_filtered.groupby('EC')['생중량'].mean().index,
                                    y=growth_data_filtered.groupby('EC')['생중량'].mean(), name="평균 생중량"), row=1, col=1)
        growth_fig.add_trace(go.Bar(x=growth_data_filtered.groupby('EC')['잎수'].mean().index,
                                    y=growth_data_filtered.groupby('EC')['잎수'].mean(), name="평균 잎 수"), row=1, col=2)
        growth_fig.add_trace(go.Bar(x=growth_data_filtered.groupby('EC')['지상부길이'].mean().index,
                                    y=growth_data_filtered.groupby('EC')['지상부길이'].mean(), name="평균 지상부 길이"), row=2, col=1)
        growth_fig.add_trace(go.Bar(x=growth_data_filtered.groupby('EC')['개체수'].mean().index,
                                    y=growth_data_filtered.groupby('EC')['개체수'].mean(), name="개체수"), row=2, col=2)
        
        growth_fig.update_layout(title_text="생육 결과 분석", showlegend=True)
        st.plotly_chart(growth_fig)

        # XLSX 다운로드
        st.subheader(f"{selected_school} 생육 결과 다운로드")
        buffer = io.BytesIO()
        growth_data_filtered.to_excel(buffer, index=False, engine="openpyxl")
        buffer.seek(0)
        st.download_button(label="다운로드 생육 데이터", data=buffer, file_name="growth_data.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.error("컬럼 'EC' 또는 '생중량'이 데이터에 없습니다. 데이터를 확인해 주세요.")
