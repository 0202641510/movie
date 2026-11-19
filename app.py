import re
import requests
import pandas as pd
from bs4 import BeautifulSoup
import streamlit as st
import plotly.express as px


def fetch_html(url):
    # 수업 실습용 User-Agent 설정
    headers = {
        "User-Agent": "Mozilla/5.0 (Educational-Class-Practice; Python-requests)"
    }
    try:
        # timeout을 10초로 설정하여 웹 페이지 요청
        response = requests.get(url, headers=headers, timeout=10)
        # HTTP 오류 상태 코드(4xx, 5xx) 확인
        response.raise_for_status()
        return response.text
    except requests.exceptions.Timeout:
        st.error("시간 초과: 서버 응답이 너무 늦습니다.")
    except requests.exceptions.ConnectionError:
        st.error("연결 실패: 인터넷 연결이나 주소를 확인해 주세요.")
    except requests.exceptions.HTTPError as e:
        st.error(f"HTTP 오류가 발생했습니다: {e}")
    except requests.exceptions.RequestException as e:
        st.error(f"요청 중 알 수 없는 오류가 발생했습니다: {e}")
    return None


def parse_target_table(html):
    soup = BeautifulSoup(html, "html.parser")
    # wikitable 클래스를 가진 모든 테이블 탐색
    tables = soup.find_all("table", {"class": "wikitable"})

    target_table = None
    for table in tables:
        first_row = table.find("tr")
        if not first_row:
            continue
        # 첫 줄의 제목 칸(th) 텍스트 추출
        headers = [th.get_text(strip=True) for th in first_row.find_all("th")]
        header_text = " ".join(headers)
        # 첫 줄에 '관객수'와 '감독'이 모두 포함된 첫 번째 표 선택
        if "관객수" in header_text and "감독" in header_text:
            target_table = table
            break

    # 조건에 맞는 표를 찾지 못한 경우
    if target_table is None:
        st.error("조건에 맞는 표('관객수'와 '감독' 포함)를 찾지 못했습니다.")
        return None

    # 표 내부의 모든 각주(sup 태그) 제거
    for sup in target_table.find_all("sup"):
        sup.decompose()

    rows = target_table.find_all("tr")
    # 첫 줄에서 열 이름 추출
    columns = [th.get_text(strip=True) for th in rows[0].find_all("th")]

    data = []
    # 두 번째 줄부터 각 영화 데이터(td) 추출
    for row in rows[1:]:
        cells = row.find_all("td")
        if not cells:
            continue
        row_data = [td.get_text(strip=True) for td in cells]
        # 열 개수와 데이터 개수가 일치하는 행만 추가
        if len(row_data) == len(columns):
            data.append(row_data)

    return pd.DataFrame(data, columns=columns)


def clean_movie_data(df):
    cleaned_df = df.copy()

    # 제목 열 찾기 및 겹화살괄호(《》) 제거
    title_col = [col for col in cleaned_df.columns if "제목" in col or "영화" in col][0]
    cleaned_df[title_col] = cleaned_df[title_col].str.replace("《", "", regex=False).str.replace("》", "", regex=False)

    # 관객수 열 찾기 및 숫자형으로 변환 (쉼표, '명' 등 비숫자 문자 제거)
    audience_col = [col for col in cleaned_df.columns if "관객수" in col][0]
    cleaned_df["관객수_숫자"] = (
        cleaned_df[audience_col]
        .astype(str)
        .str.replace(r"[^0-9]", "", regex=True)
    )
    cleaned_df["관객수_숫자"] = pd.to_numeric(cleaned_df["관객수_숫자"], errors="coerce")

    # 개봉일 열 찾기 및 개봉연도, 개봉월 추출
    date_col = [col for col in cleaned_df.columns if "개봉일" in col][0]
    cleaned_df["개봉연도"] = cleaned_df[date_col].apply(extract_year)
    cleaned_df["개봉월"] = cleaned_df[date_col].apply(extract_month)

    # 통일된 분석을 위해 핵심 열 이름 정리
    cleaned_df = cleaned_df.rename(columns={title_col: "영화제목"})
    return cleaned_df


def extract_year(date_str):
    # 문자열에서 4자리 연도 추출
    match = re.search(r"(\d{4})", str(date_str))
    return int(match.group(1)) if match else None


def extract_month(date_str):
    # 연도 뒤에 나오는 월(1~2자리 숫자) 추출
    match = re.search(r"\d{4}\D+(\d{1,2})", str(date_str))
    return int(match.group(1)) if match else None


def display_dashboard(df):
    # 천만 관객 영화만 필터링 (10,000,000명 이상)
    ten_million_df = df[df["관객수_숫자"] >= 10000000].copy()
    ten_million_df = ten_million_df.sort_values(by="관객수_숫자", ascending=False)

    # 주요 지표 계산
    total_count = len(ten_million_df)
    top_movie = ten_million_df.iloc[0]["영화제목"]
    top_audience = int(ten_million_df.iloc[0]["관객수_숫자"])

    # 지표(Metric) 출력
    col1, col2, col3 = st.columns(3)
    col1.metric("천만 영화 수", f"{total_count}편")
    col2.metric("역대 1위 영화", top_movie)
    col3.metric("1위 관객수", f"{top_audience:,}명")

    st.divider()

    # 정제된 데이터 표 출력 (인덱스 숨김 처리)
    st.subheader("천만 관객 영화 목록")
    display_cols = [col for col in ten_million_df.columns if col != "관객수_숫자"]
    st.dataframe(ten_million_df[display_cols], hide_index=True, use_container_width=True)

    st.divider()

    # 관객수 상위 10편 가로 막대 차트
    st.subheader("관객수 상위 10편")
    top10_df = ten_million_df.head(10).sort_values(by="관객수_숫자", ascending=True)
    fig_top10 = px.bar(
        top10_df,
        x="관객수_숫자",
        y="영화제목",
        orientation="h",
        labels={"관객수_숫자": "관객수(명)", "영화제목": "영화 제목"},
        text="관객수_숫자"
    )
    fig_top10.update_traces(texttemplate="%{text:,}", textposition="outside")
    fig_top10.update_layout(xaxis_range=[0, top_audience * 1.15])
    st.plotly_chart(fig_top10, use_container_width=True)

    # 개봉 연도별 편수 막대 차트
    st.subheader("개봉 연도별 천만 영화 편수")
    year_counts = ten_million_df["개봉연도"].value_counts().sort_index().reset_index()
    year_counts.columns = ["개봉연도", "편수"]
    year_counts["개봉연도"] = year_counts["개봉연도"].astype(str)

    fig_year = px.bar(
        year_counts,
        x="개봉연도",
        y="편수",
        labels={"개봉연도": "개봉 연도", "편수": "영화 편수(편)"},
        text="편수"
    )
    fig_year.update_traces(textposition="outside")
    st.plotly_chart(fig_year, use_container_width=True)


def main():
    st.set_page_config(page_title="천만 관객 영화 분석", layout="wide")
    st.title("대한민국 천만 관객 영화 흥행 기록 분석")
    st.write("위키백과 '대한민국의 영화 흥행 기록' 문서에서 데이터를 수집하여 분석합니다.")

    url = "https://ko.wikipedia.org/wiki/대한민국의_영화_흥행_기록"

    # 버튼 클릭 시 데이터 수집 및 분석 실행
    if st.button("위키백과 데이터 가져오기"):
        with st.spinner("데이터를 수집하고 분석하는 중입니다..."):
            html = fetch_html(url)
            if html:
                raw_df = parse_target_table(html)
                if raw_df is not None and not raw_df.empty:
                    cleaned_df = clean_movie_data(raw_df)
                    display_dashboard(cleaned_df)


if __name__ == "__main__":
    main()