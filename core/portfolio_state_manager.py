# core/portfolio_state_manager.py
import json
import dataclasses
import re
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
from core.target_portfolio_state import CurrentPortfolioState
from core.paths import current_state_snapshot_path, FRONT_TEST_DIR
from screener import data_manager

class PortfolioStateError(Exception):
    """포트폴리오 상태 로드/저장 중 발생하는 예외"""
    pass

def update_portfolio_state_after_close(date_str: str, actual_trades: List[Dict[str, Any]], actual_cash: Optional[float] = None) -> Path:
    """
    장 마감 후 실제 집행 내역을 반영하여 상태를 업데이트합니다.
    - actual_cash: 사용자가 주입한 실제 계좌 현금 (최우선 반영)
    """
    # 1. 최신 상태 로드
    current = load_current_state()
    
    # 가변 객체로 변환하여 작업
    new_symbols = set(current.current_symbols)
    new_shares = dict(current.shares)
    new_avg_price = dict(current.avg_price)
    new_highest_prices = dict(current.highest_prices)
    new_highest_price_meta = {
        symbol: dict(meta)
        for symbol, meta in current.highest_price_meta.items()
    }
    
    # 지침 3: 실제 주입된 현금이 있으면 그것을 사용, 없으면 기존 로직대로 계산
    new_cash = actual_cash if actual_cash is not None else current.absolute_cash

    # 2. 실제 매매 내역 반영
    for trade in actual_trades:
        symbol = trade['symbol']
        t_shares = trade['shares'] # 지침 1에 의해 SELL은 음수로 들어옴
        t_price = trade['price']

        if t_shares > 0: # BUY
            if symbol in new_symbols:
                old_qty = new_shares[symbol]
                old_avg = new_avg_price[symbol]
                new_qty = old_qty + t_shares
                new_avg_price[symbol] = ((old_qty * old_avg) + (t_shares * t_price)) / new_qty
                new_shares[symbol] = new_qty
            else:
                new_symbols.add(symbol)
                new_shares[symbol] = t_shares
                new_avg_price[symbol] = t_price
                new_highest_prices[symbol] = t_price
                new_highest_price_meta[symbol] = {
                    "updated_at": date_str,
                    "source": "actual_trade_buy",
                    "basis": "trade_price",
                }
            
            # 현금 입력을 따로 받지 않았을 때만 자동 차감
            if actual_cash is None:
                new_cash -= (t_shares * t_price)
            
        elif t_shares < 0: # SELL (음수 수량)
            if symbol in new_symbols:
                abs_sell_qty = abs(t_shares)
                old_qty = new_shares[symbol]
                new_qty = old_qty - abs_sell_qty
                
                # 현금 입력을 따로 받지 않았을 때만 자동 합산
                if actual_cash is None:
                    new_cash += (abs_sell_qty * t_price)
                
                if new_qty <= 0:
                    new_symbols.remove(symbol)
                    new_shares.pop(symbol, None)
                    new_avg_price.pop(symbol, None)
                    new_highest_prices.pop(symbol, None)
                    new_highest_price_meta.pop(symbol, None)
                else:
                    new_shares[symbol] = new_qty

    # 3. 오늘 시장 데이터를 조회하여 최고가 롤링 업데이트
    for symbol in list(new_symbols):
        try:
            # 장 마감 후이므로 date_str 일자의 전체 데이터를 가져옴
            df = data_manager.get_price_data(symbol, start_date=date_str)
            if df is not None and not df.empty:
                # 오늘(또는 지정일)의 고가 가져오기
                today_high = df.iloc[-1]['high']
                try:
                    today_high_float = float(today_high)
                except (TypeError, ValueError):
                    today_high_float = None

                if today_high_float is not None and today_high_float > 0:
                    previous_highest = float(new_highest_prices.get(symbol, 0) or 0)
                    new_highest_prices[symbol] = max(previous_highest, today_high_float)
                    new_highest_price_meta[symbol] = {
                        "updated_at": date_str,
                        "source": "update_portfolio_state_after_close",
                        "basis": "today_high",
                    }
        except Exception as e:
            print(f"⚠️ Failed to update highest price for {symbol}: {e}")

    # 4. 비중 재계산 (오늘 종가 기준 자산 가치 산정 필요)
    total_stock_value = 0
    for symbol in new_symbols:
        try:
            df = data_manager.get_price_data(symbol, start_date=date_str)
            price = df.iloc[-1]['close'] if df is not None else new_avg_price[symbol]
            total_stock_value += (new_shares[symbol] * price)
        except:
            total_stock_value += (new_shares[symbol] * new_avg_price[symbol])
            
    total_equity = new_cash + total_stock_value
    new_cash_ratio = new_cash / total_equity if total_equity > 0 else 1.0

    # 5. 새로운 상태 객체 생성 및 저장
    new_state = CurrentPortfolioState(
        current_symbols=sorted(list(new_symbols)),
        current_cash_ratio=new_cash_ratio,
        current_hedge_ratio=current.current_hedge_ratio,
        absolute_cash=new_cash,
        shares=new_shares,
        avg_price=new_avg_price,
        highest_prices=new_highest_prices,
        highest_price_meta=new_highest_price_meta,
        hedge_symbols=current.hedge_symbols
    )
    
    return save_current_state(new_state, date_str)

def _get_all_snapshots() -> List[Path]:
    """outputs/front_test/ 디렉토리 내의 모든 current_state_*.json 파일을 반환합니다."""
    return list(FRONT_TEST_DIR.glob("current_state_*.json"))

def _extract_date_from_filename(path: Path) -> Optional[datetime]:
    """파일명(current_state_YYYYMMDD.json)에서 날짜를 추출합니다."""
    match = re.search(r"current_state_(\d{8})\.json", path.name)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y%m%d")
        except ValueError:
            return None
    return None

def save_current_state(state: CurrentPortfolioState, date_str: str) -> Path:
    # ... (기존 코드 유지)
    file_path = current_state_snapshot_path(date_str)
    
    try:
        # 데이터 클래스를 딕셔너리로 변환
        data = dataclasses.asdict(state)
        
        # JSON 저장 (들여쓰기 포함하여 사람이 읽기 좋게 저장)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            
        return file_path
    except Exception as e:
        raise PortfolioStateError(f"현재 상태 저장 실패 ({file_path}): {e}")

def load_current_state(date_str: Optional[str] = None) -> CurrentPortfolioState:
    """
    포트폴리오 상태를 로드합니다.
    - date_str이 주어지면 해당 날짜 파일을 로드합니다.
    - date_str이 없으면 outputs/front_test/ 에서 가장 최신 스냅샷을 자동으로 찾아 로드합니다.
    - 로드한 파일이 현재 시점보다 4일 이상 지났다면 경고를 출력합니다.
    """
    if date_str:
        file_path = current_state_snapshot_path(date_str)
        target_date = datetime.strptime(date_str.replace("-", ""), "%Y%m%d")
    else:
        # 최신 파일 탐색
        snapshots = _get_all_snapshots()
        if not snapshots:
            raise FileNotFoundError(f"❌ [Fail-safe] No snapshot files found in {FRONT_TEST_DIR}")
        
        # 날짜 순으로 정렬 (내림차순)
        snapshots_with_date = []
        for s in snapshots:
            dt = _extract_date_from_filename(s)
            if dt:
                snapshots_with_date.append((dt, s))
        
        if not snapshots_with_date:
            raise FileNotFoundError(f"❌ [Fail-safe] No valid dated snapshots found in {FRONT_TEST_DIR}")
            
        snapshots_with_date.sort(key=lambda x: x[0], reverse=True)
        target_date, file_path = snapshots_with_date[0]
        print(f"🔍 Found latest snapshot: {file_path.name} (Date: {target_date.strftime('%Y-%m-%d')})")

    # 공통 로드 로직
    if not file_path.exists():
        raise FileNotFoundError(f"❌ [Fail-safe] snapshot file not found: {file_path}")
        
    # 4일 경과 체크 (Warning)
    days_diff = (datetime.now() - target_date).days
    if days_diff >= 4:
        print(f"⚠️  [WARNING] The latest snapshot is {days_diff} days old. Please check if you missed an update!")

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # 필수 필드 검증 (스키마 체크)
        required_fields = [
            'current_symbols', 'current_cash_ratio', 'current_hedge_ratio', 
            'absolute_cash', 'shares', 'avg_price', 'highest_prices'
        ]
        missing = [f for f in required_fields if f not in data]
        if missing:
            raise ValueError(f"필수 필드 누락: {missing}")
            
        # CurrentPortfolioState 객체로 복원 (자동으로 __post_init__ 검증 수행됨)
        return CurrentPortfolioState(
            current_symbols=data['current_symbols'],
            current_cash_ratio=data['current_cash_ratio'],
            current_hedge_ratio=data['current_hedge_ratio'],
            absolute_cash=data['absolute_cash'],
            shares=data['shares'],
            avg_price=data['avg_price'],
            highest_prices=data['highest_prices'],
            highest_price_meta=data.get('highest_price_meta', {}),
            hedge_symbols=data.get('hedge_symbols', [])
        )
    except json.JSONDecodeError as e:
        raise PortfolioStateError(f"❌ [Fail-safe] JSON decode error ({file_path}): {e}")
    except ValueError as e:
        # __post_init__ 에서 발생한 검증 오류도 여기서 잡힘
        raise PortfolioStateError(f"❌ [Fail-safe] Data integrity error: {e}")
    except Exception as e:
        raise PortfolioStateError(f"❌ [Fail-safe] Unexpected error during state load: {e}")
