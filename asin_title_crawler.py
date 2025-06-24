# 미맵핑 ASIN을 Google 검색 & Amazon 제품 url에서 title 추출
## 코드를 순차적으로 실행시키고 'c) 실행 / 1) CSV 파일 불러오기 및 검증'에서 input file 주소 변경 필요
pip install selenium
import requests
import time
import pandas as pd
import re
import json
import random
import logging, os

from bs4 import BeautifulSoup
from bs4 import BeautifulSoup
from http.client import RemoteDisconnected
from urllib.parse import urlparse, urlencode, parse_qs, quote
from selenium import webdriver
from selenium.webdriver import ChromeOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

OPTIONS = ChromeOptions()

# ScrapeOps Proxy 설정
API_KEY = ""
proxy_url = ""
# Google 요청 헤더 설정
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.3'
}
## a) Scapeops를 통해 'ASIN  amazon' 검색 
def search_amazon_asin(asin, pages=1, retries=3, num=5):
    """
    ScrapeOps를 사용하여 Google에서 특정 ASIN이 포함된 Amazon 제품 URL 검색
    """
    query = f"{asin} amazon"

    for page in range(pages):
        google_search_url = f"https://www.google.com/search?q={query}&start={page * num}&num={num}&nfpr=1"

        tries = 0
        while tries < retries:
            try:
                print(f"\n🔍 Google 검색: {query} (페이지 {page + 1})")
                response = requests.get(get_scrapeops_url(google_search_url), headers=headers)

                if response.status_code != 200:
                    print(f"❌ 서버 응답 실패: {response.status_code}")
                    raise Exception("서버 응답 오류 발생")

                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Google 검색 결과에서 Amazon URL을 저장할 리스트
                extracted_links = []

                for result in soup.find_all("div", class_="MjjYud"): ## yuRUbf, MjjYud class name으로 테스트
                    link_tag = result.find("a", href=True, jsname=True)
                    if link_tag:
                        link = link_tag["href"]
                        extracted_links.append(link)  # 모든 링크를 리스트에 저장
                        print("🔗 Extracted link:", link)

                # 모든 링크를 순차적으로 확인하여 ASIN 검증
                for link in extracted_links:
                    # ASIN을 포함하는 모든 Amazon URL 탐색
                    match = re.search(
                            r"amazon\.[a-z.]+(?:/-/[a-zA-Z_]+)?(?:/[^/]+)?/(?:dp|gp/product)/([A-Z0-9]{10})"
                                , link)

                    if match:
                        extracted_asin = match.group(1)  # URL에서 추출한 ASIN
                        print(f"🔎 Found ASIN in URL: {extracted_asin} (Expected: {asin})")

                        # 요청한 ASIN과 일치하는 경우 반환
                        if extracted_asin == asin:
                            print(f"✅ ASIN {asin} → URL 발견: {link}")
                            return link
                
                print(f"❌ ASIN {asin} → 유효한 Amazon URL 찾지 못함 (페이지 {page + 1})")
                return None

            except Exception as e:
                print(f"❌ 검색 실패, 재시도 중 ({tries + 1}/{retries})")
                time.sleep(3)
                tries += 1

    return None  # ASIN을 포함한 URL이 검색되지 않음

def check_asin_in_url(asin, asin_url_map):
    """
    특정 ASIN이 포함된 Amazon 제품 URL을 Google 검색에서 찾고 asin_url_map에 저장
    param asin: Amazon ASIN 코드
    param asin_url_map: ASIN별 Amazon URL 저장 딕셔너리
    """
    amazon_url = search_amazon_asin(asin)

    if amazon_url:
        asin_url_map[asin] = amazon_url
        print(f"✅ ASIN {asin} → URL 저장 완료: {amazon_url}")
    else:
        asin_url_map[asin] = "No Data"
        print(f"❌ ASIN {asin} → Amazon URL 검색 실패")
## b) amazon 제품 사이트에 접근해서 asin 코드 검증 & title 추출
### 1차 조회 : Request & Session 
# 요청 헤더 설정 (Amazon 크롤링 차단 방지)
amazon_headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
    "Referer": "https://www.google.com/",
    "Accept-Language": "en-US,en;q=0.9",
    "DNT": "1", 
    "Upgrade-Insecure-Requests": "1"
}

# 세션 생성 (연결 재사용으로 차단 가능성 줄이기)
session = requests.Session()
session.headers.update(amazon_headers)

def fetch_product_title(asin_url_map, product_url, asin, asin_title_map, driver):
    max_retries_amazon = 3
    retry_sleep_sequence = [3, 5, 7]

    if asin in asin_title_map:
        print(f"🔁 중복 요청 방지: ASIN {asin}은 이미 조회됨.")
        return asin_title_map[asin]

    if asin_url_map.get(asin) in ["수기 요청", "No Data"]:
        return asin_url_map.get(asin)

    random_delay = random.randint(5, 12)
    print(f"\n[{asin}] 요청 전 랜덤 대기: {random_delay}초")
    time.sleep(random_delay)

    for attempt in range(1, max_retries_amazon + 1):
        try:
            print(f"\n🔍 [{attempt}/{max_retries_amazon}] Amazon에 {asin} 요청 중: {product_url}")
            response = session.get(product_url, headers=amazon_headers, allow_redirects=True, timeout=10)

            ## 서버 요청 결과에 따른 필터링 ##
            status = response.status_code
            if status in [500, 503]:
                print(f"🚨 {status} Error 발생, {attempt}/{max_retries_amazon}회 재시도 중...")
                time.sleep(retry_sleep_sequence[min(attempt - 1, len(retry_sleep_sequence)-1)])
                continue
            elif status == 404:
                print(f"🚨 404 Not Found: {product_url} → 'No Data' 반환")
                return "No Data"

            response.raise_for_status()

            ## redirection 처리 ##
            original_asin = re.search(r"/dp/([A-Z0-9]{10})", product_url).group(1)
            final_url = response.url
            final_asin = re.search(r"/dp/([A-Z0-9]{10})", final_url).group(1)
            if original_asin and final_asin:
                if original_asin != final_asin:
                    print(f"❌ ASIN 불일치! 요청 ASIN: {original_asin} | 리디렉션된 ASIN: {final_asin}")
                    return "No Data"
            ## captcha 처리 ##
            if "captcha" in response.text.lower():
                print(f"🛑 CAPTCHA 감지됨 — ScrapOps로 전환")
                return fetch_title_scrapeops(product_url, asin, driver)
            
            # HTML elements 불러오기
            soup = BeautifulSoup(response.text, "html.parser")

            ## ASIN 추출 후 대조
            # Regular expression pattern for ASIN (10 alphanumeric characters)
            # Search for ASIN using regex in the page content
            asin_pattern = r'/dp/([A-Z0-9]{10})'
            asin_match = re.search(asin_pattern, soup.prettify())
            asin_extracted = asin_match.group(1)
            print(f"🔍 ASIN extracted : {asin_extracted}")
            if asin_extracted != asin:
                print(f"❌ ASIN 불일치! 요청 ASIN: {asin} | 조회된 ASIN: {asin_extracted}")
                return "No Data"
    
            ## 페이지 로딩 결과에 따른 필터링 ##
            ## ============================ ##
            # 아마존 "We're sorry" 체크 
            if soup.find("img", src=re.compile("title\\._ttd_\\.png", re.IGNORECASE)):
                print("❌ Page Not Found — No Data")
                return "No Data"

            title_tag = soup.find("span", id="productTitle") or soup.find("span", id="title")
            if title_tag:
                product_title = title_tag.text.strip()
                print(f"✅ Title (HTML 추출): {product_title}")
                asin_title_map[asin] = product_title
                return product_title

            print(f"❌ 제품 제목을 찾을 수 없음, ScrapOps로 전환")
            return fetch_title_scrapeops(product_url, asin, driver)

        except requests.exceptions.RequestException as e:
            print(f"🚨 Amazon 요청 실패: {e}")

    print(f"➡️ 요청 실패, ScrapOps 사용")
    return fetch_title_scrapeops(product_url, asin, driver)

### 2차 조회 : ScrapeOps Title Extraction
def init_driver(headless=True):
    options = Options()
    if headless:
        options.add_argument("--headless=new") # 브라우저를 열지 않도록 설정
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/119 Safari/537.36")
        options.add_argument("--no-sandbox") # Linux 같은 GUI 환경을 지원하지 않는 곳에서 사용
        options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)
    return driver
def get_scrapeops_url(original_url: str) -> str:
    encoded_url = quote(original_url, safe="")
    return f"https://proxy.scrapeops.io/v1/?api_key={API_KEY}&url={encoded_url}&country=us"

def fetch_title_scrapeops(product_url: str, asin: str, driver) -> str:
    try:
        driver.get(get_scrapeops_url(product_url))
        print(f"🌐 [ScrapeOps] Fetched page with Selenium for ASIN: {asin}")
        page_source = driver.page_source.lower()

        ## Internal failure 처리 로직 ##
        if "failed to get successful response" in page_source:
            print("❌ [ScrapOps] Internal fetch failure")
            if not retry:
                print("🔁 재시도 중 (ScrapeOps)")
                return fetch_title_scrapeops(product_url, asin, driver, retry=True)
            return "수기 요청"
            
        ## Page not found 처리 로직 ##
        if ("sorry! we couldn't find that page" in page_source or
            "we couldn't find that page" in page_source or
            "title._ttd_.png" in page_source):
            print("❌ Page Not Found — No Data")
            return "No Data"

        
        ## Url redirection 처리: ASIN이 다르면 리디렉션 ##
        asin_match = re.search(r'/dp/([a-z0-9]{10})', page_source)
        if asin_match:
            final_asin = asin_match.group(1).upper()
            if asin != final_asin:
                print(f"❌ ASIN 불일치! 요청 ASIN: {asin} | 페이지 내 조회된 ASIN: {final_asin}")
                return "No Data"
            else:
                print(f"✅ 요청된 {asin}과 페이지 내 조회 {final_asin} 일치")
                
    except Exception as e:
        print(f"⚠️ [ScrapeOps] 요청 실패: {e}")

    print(f"❌ 최종 실패, 수기 요청 필요: {product_url}")
    return "수기 요청"

def update_asin_data_hybrid(input_file_path, asin_url_map, asin_title_map):
    df = pd.read_csv(input_file_path, dtype=str)

    # action_required 컬럼이 없으면 생성
    if "action_required" not in df.columns:
        df["action_required"] = ""
    if "item_name" not in df.columns:
        df["item_name"] = ""

    # 1) 브라우저(ChromeDriver) 초기화
    driver = init_driver(headless=True)  # headless=False로 하면 브라우저 창 표시

    for asin, product_url in asin_url_map.items():
        if asin in asin_title_map:
            print(f"🔁 {asin} 이미 처리됨, 건너뜀")
            continue

        if product_url == "No Data":
            asin_title_map[asin] = "No Data"
            continue

        product_title = fetch_product_title(redirected_asin, product_url, asin, asin_title_map, driver)
        asin_title_map[asin] = product_title

    # 2) 결과를 csv 파일에 반영
    for asin, product_title in asin_title_map.items():
        if product_title == "수기 요청":
            df.loc[df["asin"] == asin, "action_required"] = "수기 요청"
            df.loc[df["asin"] == asin, "item_name"] = ""
        elif product_title == "No Data":
            df.loc[df["asin"] == asin, "action_required"] = "No Data"
            df.loc[df["asin"] == asin, "item_name"] = ""
        else:
            df.loc[df["asin"] == asin, "item_name"] = product_title
            df.loc[df["asin"] == asin, "action_required"] = ""

    updated_file_path = "asin_crawling_" + input_file_path
    df.to_csv(updated_file_path, index=False, encoding="utf-8-sig")

    print(f"\n✅ 업데이트 완료! 저장된 파일: {updated_file_path}")

    # 5) 마무리: WebDriver 종료
    driver.quit()
## c) 실행
### 1) CSV 파일 불러오기 및 검증
input_file_path = "미조회_asin_425_250224.csv" # 조회해야 할 CSV 파일 경로, 파일에 따라 입력 필요

# CSV 파일 읽기
try:
    df = pd.read_csv(input_file_path, dtype=str)
    print(f"CSV 파일 로드 완료: {input_file_path}")
except FileNotFoundError:
    print(f"에러: 파일 '{input_file_path}'을 찾을 수 없습니다.")
    df = None

# asin 컬럼 df_asin_to_test 리스트로 저장
if df is not None:
    if "asin" in df.columns:
        df_asin_list = df["asin"].dropna().astype(str).tolist() # 특정 개수의 asin을 테스트 하고 싶다면 [:num] 추가 ex) tolist()[:10]
        print(f"🔍 검색할 ASIN 개수: {len(df_asin_list)}")
    else:
        print("CSV 파일에 'asin' 컬럼이 없습니다.")
        df_asin_list = []
else:
    df_asin_list = [] # df_asin_to_test : 조회 할 asin 코드 담겨져 있는 리스트

# df_asin_to_test 출력
print(f"테스트할 ASIN 리스트: {df_asin_list}")
### 1-1) 엑셀 파일 불러올시, 아래 코드 참조
# # 엑셀 파일 경로
# input_file_path = "asin_400_20250224.xlsx"  # 확장자를 .xlsx로 변경

# # 엑셀 파일 읽기
# try:
#     df = pd.read_excel(input_file_path, sheet_name="asin", dtype=str)  # 'asin' 시트 읽기
#     print(f"📂 엑셀 파일 로드 완료: {input_file_path} (시트: 'asin')")
# except FileNotFoundError:
#     print(f"❌ 에러: 파일 '{input_file_path}'을 찾을 수 없습니다.")
#     df = None
# except ValueError:
#     print(f"❌ 에러: 파일에 'asin' 시트가 존재하지 않습니다.")
#     df = None

# # ASIN 컬럼 값 리스트로 변환
# if df is not None:
#     if "asin" in df.columns:
#         df_asin_list = df["asin"].dropna().astype(str).tolist()  # ASIN 리스트 생성
#         print(f"🔍 검색할 ASIN 개수: {len(df_asin_list)}")
#     else:
#         print("❌ 엑셀 파일에 'asin' 컬럼이 없습니다.")
#         df_asin_list = []
# else:
#     df_asin_list = []  # 오류 발생 시 빈 리스트 반환

# # 결과 출력
# print(f"📌 테스트할 ASIN 리스트: {df_asin_list}")
### 2) ASIN 구글 검색 실행
### 3) 제품 사이트 asin 조회 및 검증, 검증 완료 asin은 title 추출
asin_url_map = {}
asin_title_map = {}

## 'ASIN amazon' 구글 검색 실행 ##
#asin_url_map에 결과 적재

for asin in df_asin_list:
    check_asin_in_url(asin, asin_url_map)

## amazon url에 접속, asin 코드 검증 후 title값을 csv파일 업로드 ##
# asin_url_map 적재된 결과를 기반으로 제품 title 추출

update_asin_data_hybrid(input_file_path, asin_url_map, asin_title_map)
