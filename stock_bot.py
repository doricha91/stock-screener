import yfinance as yf
import pandas as pd
import requests
import json
import os
from datetime import datetime
from dotenv import load_dotenv

# ==========================================
# [설정 로드] .env 파일에서 키를 가져옵니다
# ==========================================

# 1. .env 파일 로드
load_dotenv()

# 2. 환경변수에서 값 꺼내기
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

# [안전장치] 키가 제대로 안 불러와졌으면 프로그램 종료
if not NOTION_API_KEY or not DATABASE_ID:
    print("❌ 오류: .env 파일을 찾을 수 없거나 키 값이 비어있습니다.")
    print("같은 폴더에 .env 파일이 있는지, 변수명이 정확한지 확인해주세요.")
    exit()

# ==========================================
# [사용자 설정] 종목 리스트 및 평단가
# ==========================================
STOCK_LIST = {
    "036810.KQ": {"name": "에프에스티", "buy_price": 30400},
    "102970.KS": {"name": "KODEX 증권", "buy_price": 16319},
    "000660.KS": {"name": "SK하이닉스", "buy_price": 271063},
    "0072R0.KS": {"name": "TIGER KRX금현물A", "buy_price": 9960},
    "102110.KS": {"name": "TIGER 200", "buy_price": 41695},
    "316140.KS": {"name": "우리금융지주", "buy_price": 14910},
    "381170.KS": {"name": "TIGER 미국테크TOP10 INDXX", "buy_price": 17735},
    "0066W0.KS": {"name": "SOL 국제금", "buy_price": 11980},
    "0072R0.KS": {"name": "TIGER KRX금현물B", "buy_price": 12638},
    "481180.KS": {"name": "SOL 미국AI소프트웨어", "buy_price": 15529},
    "379810.KS": {"name": "KODEX 미국나스닥100", "buy_price": 23741},
    "MSFT": {"name": "마이크로소프트", "buy_price": 457.4},
    "AMZN": {"name": "아마존", "buy_price": 218.0},
    "NVDA": {"name": "엔비디아", "buy_price": 160.3},
    "SPY": {"name": "SPDR S&P 500", "buy_price": 566.0},
    "VOO": {"name": "VANGUARD S&P 500", "buy_price": 500.3},
    "QQQ": {"name": "INVESCO QQQ TRUST", "buy_price": 401.3},
    "BND": {"name": "VANGUARD TOTAL BOND MARKET", "buy_price": 73.3},

}


# ==========================================
# [로직 1] 주가 및 수익률 계산
# ==========================================
def get_market_data(ticker, buy_price):
    try:
        df = yf.download(ticker, period="60d", progress=False, auto_adjust=True)

        if len(df) < 20:
            print(f"⚠️ [{ticker}] 데이터 부족")
            return None

        if isinstance(df.columns, pd.MultiIndex):
            try:
                df = df.xs(ticker, level=1, axis=1)
            except:
                pass

        df['Low_20'] = df['Low'].shift(1).rolling(window=20).min()

        df['High-Low'] = df['High'] - df['Low']
        df['High-Close'] = abs(df['High'] - df['Close'].shift(1))
        df['Low-Close'] = abs(df['Low'] - df['Close'].shift(1))
        df['TR'] = df[['High-Low', 'High-Close', 'Low-Close']].max(axis=1)
        df['ATR'] = df['TR'].rolling(window=14).mean()
        df['High_20'] = df['High'].rolling(window=20).max()

        today = df.iloc[-1]

        def safe_float(val):
            if isinstance(val, pd.Series): return float(val.iloc[0])
            return float(val)

        current_price = safe_float(today['Close'])
        exit_all_price = safe_float(today['Low_20'])
        atr_value = safe_float(today['ATR'])
        recent_high = safe_float(today['High_20'])
        exit_half_price = recent_high - (atr_value * 2)

        if buy_price > 0:
            return_rate = (current_price - buy_price) / buy_price
        else:
            return_rate = 0.0

        if ".KS" in ticker or ".KQ" in ticker:
            currency_tag = "🇰🇷 KRW"
            p_current = int(current_price)
            p_half = int(exit_half_price)
            p_all = int(exit_all_price)
            p_buy = int(buy_price)
        else:
            currency_tag = "🇺🇸 USD"
            p_current = round(current_price, 2)
            p_half = round(exit_half_price, 2)
            p_all = round(exit_all_price, 2)
            p_buy = float(buy_price)

        status = "🟢 보유 (Hold)"
        if current_price < exit_all_price:
            status = "🔴 전량 매도 (추세 이탈)"
        elif current_price < exit_half_price:
            status = "🟡 50% 매도 (변동성 경고)"

        return {
            "price": p_current,
            "buy_price": p_buy,
            "return_rate": return_rate,
            "exit_half": p_half,
            "exit_all": p_all,
            "status": status,
            "currency": currency_tag
        }
    except Exception as e:
        print(f"⚠️ 계산 오류 ({ticker}): {e}")
        return None


# ==========================================
# [로직 2] 노션 전송
# ==========================================
def update_notion_direct(ticker, info, data):
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

    query_url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    query_payload = {
        "filter": {
            "property": "종목코드",
            "rich_text": {
                "equals": ticker
            }
        }
    }

    response = requests.post(query_url, headers=headers, json=query_payload)
    if response.status_code != 200:
        print(f"❌ 노션 접속 실패: {response.text}")
        return

    results = response.json().get("results")

    new_properties = {
        "properties": {
            "종목명": {"title": [{"text": {"content": info['name']}}]},
            "종목코드": {"rich_text": [{"text": {"content": ticker}}]},
            "현재가": {"number": data['price']},
            "평단가": {"number": data['buy_price']},
            "수익률": {"number": data['return_rate']},
            "50%매도(안전)": {"number": data['exit_half']},
            "전량매도(추세)": {"number": data['exit_all']},
            "상태": {"select": {"name": data['status']}},
            "통화": {"select": {"name": data['currency']}},
            "기준일": {"date": {"start": datetime.now().strftime("%Y-%m-%d")}}
        }
    }

    if results:
        page_id = results[0]['id']
        update_url = f"https://api.notion.com/v1/pages/{page_id}"
        requests.patch(update_url, headers=headers, json=new_properties)
        print(f"[수정] {info['name']}: {data['return_rate'] * 100:.2f}%")
    else:
        create_url = "https://api.notion.com/v1/pages"
        new_properties["parent"] = {"database_id": DATABASE_ID}
        requests.post(create_url, headers=headers, json=new_properties)
        print(f"[신규] {info['name']}: {data['return_rate'] * 100:.2f}%")


# ==========================================
# [실행부]
# ==========================================
print("🚀 주식 봇 시작 (.env 설정 적용)...")

for ticker, info in STOCK_LIST.items():
    result = get_market_data(ticker, info['buy_price'])
    if result:
        update_notion_direct(ticker, info, result)

print("✅ 완료되었습니다.")