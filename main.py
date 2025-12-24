import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import unicodedata
from pathlib import Path
import io

# 한글 폰트 깨짐 방지
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR&display=swap');
html, body, [class*="css"] {
    font-family: 'Noto Sans KR', 'Malgun Gothic', sans-serif;
}
</style>
""", unsafe_allow_html=True)

# 데이터 파일 로드 함수 (파일 인식 오류 방지)
@st.cache_data
def load_data():
    data_path = Path("data")
    
    # 파일 인식 오류 방지
    files = [f for f in data_path.iterdir() if unicodedata.normalize('NFC', f.name) == f.name]
    
    # 환경 데이터
    env_data = {}
    for file in files[:4]:  # CSV 파일 4개
        school_name = file.stem.split('_')[0]
        env_data[school_name] = pd.read_csv(file)
    
    # 생육 데이터 (엑셀)
    growth_data = pd.read_excel(data_path / "4개교_생육결과데이터.xlsx", sheet_name=None)
    
    return env_data, growth_data

# 데이터 로딩
env_data, growth_data = load_data()

# 사이드바: 학교 선택
school_list = ['전체', '송도고', '하늘고', '아라고', '동산고']
selected_school = st.sidebar.selectbox("학교 선택", school_list)

# 탭: 실험 개요
tab1, tab2, tab3 = st.tabs(["📖 실험 개요", "🌡️ 환경 데이터", "📊 생육 결과"])

# Tab 1: 실험 개요
with tab1:
    st.header("🌱 극지식물 최적 EC 농도 연구")
    st.write("""
    본 연구는 극지식물의 최적 EC 농도를 도출하기 위해 다양한 학교에서 측정된 환경 데이터와 생육 데이터를 비교 분석하는 것입니다.
    """)
    
    # 학교별 EC 조건 표
    ec_conditions = {
        "송도고": 1.0,
        "하늘고": 2.0,
        "아라고": 4.0,
        "동산고": 8.0
    }
    school_ec = pd.DataFrame.from_dict(ec_conditions, orient="index", columns=["EC 목표"])
    school_ec["개체수"] = [env_data[school]["time"].count() for school in ec_conditions]
    school_ec["색상"] = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
    st.table(school_ec)
    
    # 주요 지표 카드
    if selected_school == "전체":
        total_samples = sum([env_data[school]["time"].count() for school in env_data])
        avg_temp = pd.concat([env_data[school]["temperature"] for school in env_data]).mean()
        avg_humidity = pd.concat([env_data[school]["humidity"] for school in env_data]).mean()
        optimal_ec = 2.0  # 하늘고 기준
        
        st.metric("총 개체수", total_samples)
        st.metric("평균 온도", f"{avg_temp:.2f}°C")
        st.metric("평균 습도", f"{avg_humidity:.2f}%")
        st.metric("최적 EC", optimal_ec)
    else:
        school_data = env_data[selected_school]
        total_samples = school_data["time"].count()
        avg_temp = school_data["temperature"].mean()
        avg_humidity = school_data["humidity"].mean()
        optimal_ec = ec_conditions[selected_school]
        
        st.metric("총 개체수", total_samples)
        st.metric("평균 온도", f"{avg_temp:.2f}°C")
        st.metric("평균 습도", f"{avg_humidity:.2f}%")
        st.metric("최적 EC", optimal_ec)

# Tab 2: 환경 데이터
with tab2:
    st.header("🌡️ 환경 데이터")
    
    # 환경 데이터 비교 (학교별)
    if selected_school == "전체":
        school_data = env_data
    else:
        school_data = {selected_school: env_data[selected_school]}
    
    fig = make_subplots(rows=2, cols=2, subplot_titles=("평균 온도", "평균 습도", "평균 pH", "목표 EC vs 실측 EC"))
    
    for idx, (school, data) in enumerate(school_data.items()):
        row, col = divmod(idx, 2)
        fig.add_trace(go.Bar(
            x=[school],
            y=[data["temperature"].mean()],
            name=f"{school} 온도",
            marker_color='#1f77b4'
        ), row=row+1, col=col+1)
        
    fig.update_layout(
        height=600,
        width=800,
        title_text="환경 데이터 비교",
        font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif")
    )
    st.plotly_chart(fig)

    # 환경 데이터 원본 테이블
    st.expander("환경 데이터 원본 테이블 보기").table(school_data[selected_school])  # 원본 데이터 테이블

# Tab 3: 생육 결과
with tab3:
    st.header("📊 생육 결과")
    
    # 생육 결과 카드
    growth_stats = {
        "평균 생중량": 15.5,  # 예시 값
        "평균 잎 수": 7.0,    # 예시 값
        "평균 지상부 길이": 120.0  # 예시 값
    }
    for stat, value in growth_stats.items():
        st.metric(stat, value)
    
    # EC별 생육 비교
    fig = make_subplots(rows=2, cols=2, subplot_titles=("생중량", "잎 수", "지상부 길이", "개체수 비교"))
    
    # 예시 값들
    st.plotly_chart(fig)

    # 상관 관계 분석 (산점도)
    st.write("상관 관계 분석")
    fig = go.Figure(data=go.Scatter(
        x=[5, 6, 7, 8],  # 예시 값
        y=[10, 15, 20, 25],  # 예시 값
        mode='markers',
        marker=dict(size=12, color='rgba(255, 182, 193, .9)', line=dict(width=2))
    ))
    st.plotly_chart(fig)

    # 원본 데이터 다운로드 (XLSX)
    buffer = io.BytesIO()
    growth_data[selected_school].to_excel(buffer, index=False, engine="openpyxl")
    buffer.seek(0)
    st.download_button(
        label="엑셀 파일 다운로드",
        data=buffer,
        file_name=f"{selected_school}_생육결과.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
