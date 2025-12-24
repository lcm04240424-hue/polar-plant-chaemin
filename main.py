import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import unicodedata
import io
import time

# -----------------------------------------------------------------------------
# 1. 페이지 설정 및 CSS (한글 폰트 깨짐 방지)
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="극지식물 최적 EC 농도 연구",
    page_icon="🌱",
    layout="wide"
)

# Streamlit UI 한글 폰트 적용
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700&display=swap');
html, body, [class*="css"] {
    font-family: 'Noto Sans KR', 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif;
}
</style>
""", unsafe_allow_html=True)

# Plotly 차트용 공통 폰트 설정 함수
def update_fig_layout(fig, title=None):
    fig.update_layout(
        font=dict(family="Noto Sans KR, Malgun Gothic, Apple SD Gothic Neo, sans-serif"),
        title_text=title if title else None,
        title_x=0.5
    )
    return fig

# -----------------------------------------------------------------------------
# 2. 데이터 로딩 및 전처리 (경로 문제, 인코딩 문제 해결)
# -----------------------------------------------------------------------------

# 학교별 메타데이터 정의
SCHOOL_META = {
    "송도고": {"ec_target": 1.0, "color": "#1f77b4", "file_keyword": "송도"},
    "하늘고": {"ec_target": 2.0, "color": "#2ca02c", "file_keyword": "하늘"}, # 최적 (초록)
    "아라고": {"ec_target": 4.0, "color": "#ff7f0e", "file_keyword": "아라"},
    "동산고": {"ec_target": 8.0, "color": "#d62728", "file_keyword": "동산"},
}

def normalize_str(s):
    """문자열을 NFC로 정규화하여 Mac/Win 파일명 차이 해결"""
    return unicodedata.normalize('NFC', s) if s else ""

@st.cache_data
def load_data():
    """데이터 폴더에서 파일을 자동으로 감지하여 로드 및 병합"""
    
    data_dir = Path("data")
    
    # 데이터 폴더 존재 확인
    if not data_dir.exists():
        return None, None, "❌ 'data' 폴더를 찾을 수 없습니다."

    env_dfs = []
    growth_dfs = []
    
    # 2-1. 파일 탐색 (iterdir 사용 + 인코딩 정규화)
    found_env_files = 0
    found_growth_file = False
    
    for file_path in data_dir.iterdir():
        # 파일명 정규화 (자소 분리 방지)
        fname = normalize_str(file_path.name)
        
        # A. 환경 데이터 (CSV) 로딩
        if fname.endswith(".csv") and "환경" in fname:
            for school, meta in SCHOOL_META.items():
                if meta["file_keyword"] in fname:
                    try:
                        # 한글 포함 CSV 읽기 시도 (utf-8 or cp949)
                        try:
                            df = pd.read_csv(file_path, encoding='utf-8')
                        except UnicodeDecodeError:
                            df = pd.read_csv(file_path, encoding='cp949')
                        
                        df['school'] = school
                        df['target_ec'] = meta['ec_target']
                        
                        # 컬럼명 소문자 변환 및 공백 제거
                        df.columns = [c.strip().lower() for c in df.columns]
                        
                        # 필수 컬럼 확인
                        required_cols = {'time', 'temperature', 'humidity', 'ph', 'ec'}
                        if required_cols.issubset(df.columns):
                            df['time'] = pd.to_datetime(df['time'], errors='coerce')
                            env_dfs.append(df)
                            found_env_files += 1
                    except Exception as e:
                        print(f"Error reading {fname}: {e}")
        
        # B. 생육 결과 데이터 (XLSX) 로딩
        elif fname.endswith(".xlsx") and "생육" in fname:
            try:
                found_growth_file = True
                excel_file = pd.ExcelFile(file_path)
                
                for sheet_name in excel_file.sheet_names:
                    norm_sheet = normalize_str(sheet_name)
                    
                    # 시트 이름과 학교 매칭
                    matched_school = None
                    for school, meta in SCHOOL_META.items():
                        if meta["file_keyword"] in norm_sheet:
                            matched_school = school
                            break
                    
                    if matched_school:
                        df_sheet = pd.read_excel(file_path, sheet_name=sheet_name)
                        df_sheet['school'] = matched_school
                        df_sheet['target_ec'] = SCHOOL_META[matched_school]['ec_target']
                        
                        # 컬럼 표준화 (예상되는 컬럼명 매핑)
                        # 실제 엑셀 헤더에 따라 조정 필요할 수 있음
                        # 컬럼: 개체번호, 잎 수(장), 지상부 길이(mm), 지하부길이(mm), 생중량(g)
                        df_sheet.columns = [c.strip() for c in df_sheet.columns]
                        growth_dfs.append(df_sheet)
                        
            except Exception as e:
                return None, None, f"❌ 엑셀 파일 로딩 중 오류: {e}"

    # 2-2. 데이터 병합 및 반환
    if not env_dfs:
        return None, None, "❌ 환경 데이터(CSV)를 찾을 수 없습니다."
    if not growth_dfs:
        return None, None, "❌ 생육 데이터(XLSX)를 찾을 수 없습니다."

    final_env_df = pd.concat(env_dfs, ignore_index=True)
    final_growth_df = pd.concat(growth_dfs, ignore_index=True)
    
    return final_env_df, final_growth_df, None

# -----------------------------------------------------------------------------
# 3. 데이터 다운로드 함수 (BytesIO 사용)
# -----------------------------------------------------------------------------
def convert_df_to_excel(df):
    buffer = io.BytesIO()
    # ExcelWriter와 openpyxl 엔진 명시
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    buffer.seek(0)
    return buffer

# -----------------------------------------------------------------------------
# 4. 앱 메인 로직
# -----------------------------------------------------------------------------
def main():
    st.title("🌱 극지식물 최적 EC 농도 연구 대시보드")
    
    # 사이드바
    st.sidebar.header("🔍 필터 옵션")
    school_options = ["전체"] + list(SCHOOL_META.keys())
    selected_school = st.sidebar.selectbox("학교 선택", school_options)
    
    # 데이터 로딩
    with st.spinner("데이터를 불러오는 중입니다..."):
        env_df, growth_df, error_msg = load_data()

    if error_msg:
        st.error(error_msg)
        st.stop()
    
    # 필터링
    if selected_school != "전체":
        filtered_env = env_df[env_df['school'] == selected_school]
        filtered_growth = growth_df[growth_df['school'] == selected_school]
    else:
        filtered_env = env_df
        filtered_growth = growth_df

    # 탭 구성
    tab1, tab2, tab3 = st.tabs(["📖 실험 개요", "🌡️ 환경 데이터", "📊 생육 결과"])

    # --- Tab 1: 실험 개요 ---
    with tab1:
        st.header("연구 배경 및 목적")
        st.markdown("""
        본 연구는 극지 식물의 생육에 가장 적합한 양액 농도(EC)를 규명하기 위해 수행되었습니다.
        서로 다른 EC 조건(1.0, 2.0, 4.0, 8.0 dS/m)을 설정한 4개 학교의 스마트팜 데이터를 통합 분석합니다.
        """)
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.subheader("실험 조건")
            condition_data = []
            for school, meta in SCHOOL_META.items():
                count = len(growth_df[growth_df['school'] == school])
                condition_data.append({
                    "학교명": school,
                    "목표 EC": meta['ec_target'],
                    "개체수": f"{count}개",
                    "비고": "최적 조건" if school == "하늘고" else ""
                })
            st.dataframe(pd.DataFrame(condition_data), hide_index=True)
            
        with col2:
            st.subheader("전체 데이터 요약")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("총 개체수", f"{len(growth_df)}개")
            m2.metric("평균 온도", f"{env_df['temperature'].mean():.1f}℃")
            m3.metric("평균 습도", f"{env_df['humidity'].mean():.1f}%")
            m4.metric("최적 EC (가설)", "2.0 (하늘고)", delta_color="normal")

    # --- Tab 2: 환경 데이터 ---
    with tab2:
        st.header("학교별 환경 제어 상태 비교")
        
        # 1. 평균 비교 (2x2 Subplots)
        avg_env = env_df.groupby('school')[['temperature', 'humidity', 'ph', 'ec', 'target_ec']].mean().reset_index()
        
        fig_env = make_subplots(
            rows=2, cols=2,
            subplot_titles=("평균 온도 (℃)", "평균 습도 (%)", "평균 pH", "목표 EC vs 실측 EC")
        )
        
        # 학교별 색상 매핑
        colors = [SCHOOL_META[s]['color'] for s in avg_env['school']]
        
        # 좌상: 온도
        fig_env.add_trace(go.Bar(x=avg_env['school'], y=avg_env['temperature'], name="온도", marker_color=colors), row=1, col=1)
        # 우상: 습도
        fig_env.add_trace(go.Bar(x=avg_env['school'], y=avg_env['humidity'], name="습도", marker_color=colors), row=1, col=2)
        # 좌하: pH
        fig_env.add_trace(go.Bar(x=avg_env['school'], y=avg_env['ph'], name="pH", marker_color=colors), row=2, col=1)
        # 우하: EC (이중 막대)
        fig_env.add_trace(go.Bar(x=avg_env['school'], y=avg_env['target_ec'], name="목표 EC", marker_color='lightgray'), row=2, col=2)
        fig_env.add_trace(go.Bar(x=avg_env['school'], y=avg_env['ec'], name="실측 EC", marker_color=colors), row=2, col=2)
        
        fig_env.update_layout(height=600, showlegend=False)
        update_fig_layout(fig_env)
        st.plotly_chart(fig_env, use_container_width=True)
        
        st.divider()
        
        # 2. 시계열 변화
        st.subheader(f"⏱️ 시계열 변화 ({selected_school})")
        
        # 시계열 차트 그리기 (샘플링하여 성능 최적화 가능)
        ts_df = filtered_env.sort_values('time')
        
        fig_ts = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.1,
                               subplot_titles=("온도 변화", "습도 변화", "EC 변화"))
        
        # 학교가 '전체'일 경우 색상으로 구분, 단일 학교일 경우 단일 색상
        if selected_school == "전체":
            for school in SCHOOL_META.keys():
                s_df = ts_df[ts_df['school'] == school]
                color = SCHOOL_META[school]['color']
                fig_ts.add_trace(go.Scatter(x=s_df['time'], y=s_df['temperature'], name=f"{school} 온도", line=dict(color=color), legendgroup=school), row=1, col=1)
                fig_ts.add_trace(go.Scatter(x=s_df['time'], y=s_df['humidity'], name=f"{school} 습도", line=dict(color=color), legendgroup=school), row=2, col=1)
                fig_ts.add_trace(go.Scatter(x=s_df['time'], y=s_df['ec'], name=f"{school} EC", line=dict(color=color), legendgroup=school), row=3, col=1)
        else:
            color = SCHOOL_META[selected_school]['color']
            fig_ts.add_trace(go.Scatter(x=ts_df['time'], y=ts_df['temperature'], name="온도", line=dict(color=color)), row=1, col=1)
            fig_ts.add_trace(go.Scatter(x=ts_df['time'], y=ts_df['humidity'], name="습도", line=dict(color=color)), row=2, col=1)
            fig_ts.add_trace(go.Scatter(x=ts_df['time'], y=ts_df['ec'], name="EC", line=dict(color=color)), row=3, col=1)
            # 목표 EC 라인 추가
            target = SCHOOL_META[selected_school]['ec_target']
            fig_ts.add_hline(y=target, line_dash="dash", line_color="red", annotation_text="목표 EC", row=3, col=1)

        fig_ts.update_layout(height=700)
        update_fig_layout(fig_ts)
        st.plotly_chart(fig_ts, use_container_width=True)
        
        # 데이터 원본 및 다운로드
        with st.expander("환경 데이터 원본 보기"):
            st.dataframe(filtered_env.head(100))
            
            excel_buffer = convert_df_to_excel(filtered_env)
            st.download_button(
                label="📥 환경 데이터 엑셀 다운로드",
                data=excel_buffer,
                file_name=f"env_data_{selected_school}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    # --- Tab 3: 생육 결과 ---
    with tab3:
        st.header("📊 EC 농도별 생육 결과 비교")
        
        # 컬럼 이름이 한글이므로 변수 매핑 확인
        # 컬럼: 개체번호, 잎 수(장), 지상부 길이(mm), 지하부길이(mm), 생중량(g)
        col_weight = '생중량(g)'
        col_leaf = '잎 수(장)'
        col_len_top = '지상부 길이(mm)'
        col_len_root = '지하부길이(mm)'
        
        # 1. 핵심 결과 카드 (최대 생중량)
        max_weight_school = growth_df.groupby('school')[col_weight].mean().idxmax()
        max_weight_val = growth_df.groupby('school')[col_weight].mean().max()
        
        st.info(f"🥇 가장 생육이 좋은 조건은 **{max_weight_school} (EC {SCHOOL_META[max_weight_school]['ec_target']})** 입니다. 평균 생중량: **{max_weight_val:.2f}g**")
        
        # 2. 4개 지표 비교 (2x2)
        avg_growth = growth_df.groupby('school')[[col_weight, col_leaf, col_len_top, '개체번호']].agg({
            col_weight: 'mean', col_leaf: 'mean', col_len_top: 'mean', '개체번호': 'count'
        }).reset_index().rename(columns={'개체번호': '개체수'})
        
        # 정렬 (EC 순서대로: 송도->하늘->아라->동산)
        sorter = ["송도고", "하늘고", "아라고", "동산고"]
        avg_growth['school'] = pd.Categorical(avg_growth['school'], categories=sorter, ordered=True)
        avg_growth = avg_growth.sort_values('school')
        
        fig_growth = make_subplots(rows=2, cols=2, subplot_titles=("평균 생중량 (g)", "평균 잎 수 (장)", "평균 지상부 길이 (mm)", "총 개체수"))
        
        bar_colors = [SCHOOL_META[s]['color'] for s in avg_growth['school']]
        
        fig_growth.add_trace(go.Bar(x=avg_growth['school'], y=avg_growth[col_weight], marker_color=bar_colors, name="생중량"), row=1, col=1)
        fig_growth.add_trace(go.Bar(x=avg_growth['school'], y=avg_growth[col_leaf], marker_color=bar_colors, name="잎 수"), row=1, col=2)
        fig_growth.add_trace(go.Bar(x=avg_growth['school'], y=avg_growth[col_len_top], marker_color=bar_colors, name="지상부 길이"), row=2, col=1)
        fig_growth.add_trace(go.Bar(x=avg_growth['school'], y=avg_growth['개체수'], marker_color='gray', name="개체수"), row=2, col=2)
        
        fig_growth.update_layout(height=600, showlegend=False)
        update_fig_layout(fig_growth)
        st.plotly_chart(fig_growth, use_container_width=True)
        
        st.divider()
        
        col_g1, col_g2 = st.columns(2)
        
        # 3. 분포 (Box Plot)
        with col_g1:
            st.subheader("학교별 생중량 분포")
            fig_box = px.box(filtered_growth, x='school', y=col_weight, color='school',
                             color_discrete_map={k: v['color'] for k, v in SCHOOL_META.items()})
            update_fig_layout(fig_box)
            st.plotly_chart(fig_box, use_container_width=True)
            
        # 4. 상관관계 (Scatter)
        with col_g2:
            st.subheader("잎 수 vs 생중량 상관관계")
            fig_scatter = px.scatter(filtered_growth, x=col_leaf, y=col_weight, color='school',
                                     trendline="ols", # 회귀선 추가
                                     color_discrete_map={k: v['color'] for k, v in SCHOOL_META.items()})
            update_fig_layout(fig_scatter)
            st.plotly_chart(fig_scatter, use_container_width=True)

        # 데이터 원본 및 다운로드
        with st.expander("생육 결과 데이터 원본 보기"):
            st.dataframe(filtered_growth)
            
            growth_buffer = convert_df_to_excel(filtered_growth)
            st.download_button(
                label="📥 생육 데이터 엑셀 다운로드",
                data=growth_buffer,
                file_name=f"growth_data_{selected_school}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

if __name__ == "__main__":
    main()
