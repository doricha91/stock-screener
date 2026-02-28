import sqlite3
import pandas as pd
from datetime import datetime


class PortfolioDB:
    def __init__(self, db_path="portfolio.db", initial_cash=10000.0):
        self.db_path = db_path
        self.initial_capital = initial_cash

        # [DB 연결] 인스턴스 변수로 유지 (In-memory DB 호환성)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._init_db()

    def __del__(self):
        """객체 소멸 시 안전하게 연결 종료"""
        try:
            if self.conn:
                self.conn.close()
        except:
            pass

    def _init_db(self):
        """DB 테이블 초기화"""
        cursor = self.conn.cursor()

        # 1. 계좌 잔고 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS account (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                cash REAL DEFAULT 0,
                total_equity REAL DEFAULT 0,
                updated_at TEXT
            )
        ''')

        # 2. 보유 종목 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS positions (
                symbol TEXT PRIMARY KEY,
                shares INTEGER,
                avg_price REAL,
                current_price REAL,
                highest_price REAL,
                pnl REAL,
                return_pct REAL,
                entry_date TEXT,
                strategy_name TEXT,
                sector TEXT,
                updated_at TEXT
            )
        ''')

        # 3. 매매 기록 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trade_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                type TEXT, 
                symbol TEXT,
                shares INTEGER,
                price REAL,
                amount REAL,
                commission REAL DEFAULT 0.0,
                strategy_name TEXT,
                reason TEXT,
                profit REAL DEFAULT 0.0
            )
        ''')

        # 초기 자본 설정
        cursor.execute("SELECT count(*) FROM account")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO account (id, cash, updated_at) VALUES (1, ?, ?)",
                           (self.initial_capital, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

        self.conn.commit()

    # =========================================================================
    # 💰 계좌 및 상태 조회 (Read)
    # =========================================================================
    def get_account_status(self):
        """현재 현금 및 총 자산 반환"""
        cursor = self.conn.cursor()

        cursor.execute("SELECT cash FROM account WHERE id=1")
        cash = cursor.fetchone()[0]

        cursor.execute("SELECT SUM(shares * current_price) FROM positions")
        result = cursor.fetchone()[0]
        stock_val = result if result else 0.0

        return {'cash': cash, 'stock_value': stock_val, 'total_equity': cash + stock_val}

    def get_positions(self):
        """보유 종목 전체를 딕셔너리로 반환"""
        try:
            df = pd.read_sql("SELECT * FROM positions", self.conn)
            if df.empty:
                return {}
            return df.set_index('symbol').to_dict(orient='index')
        except Exception as e:
            print(f"❌ 포지션 조회 오류: {e}")
            return {}

    def get_position(self, symbol):
        """특정 종목 정보만 조회"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM positions WHERE symbol=?", (symbol,))
        row = cursor.fetchone()
        return row

    # =========================================================================
    # 🛒 매매 실행 (Transaction)
    # =========================================================================
    def buy(self, symbol, price, shares, date, strategy_name="Unknown", sector="", commission=0.0):
        """매수 실행 및 DB 업데이트"""

        # [수정] 날짜가 Timestamp 객체일 경우 문자열로 변환
        date_str = str(date)

        status = self.get_account_status()
        cost = (price * shares) + commission

        if status['cash'] < cost:
            return False

        cursor = self.conn.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        try:
            # 1. 현금 차감
            new_cash = status['cash'] - cost
            cursor.execute("UPDATE account SET cash=?, updated_at=? WHERE id=1", (new_cash, now))

            # 2. 포지션 업데이트
            cursor.execute("SELECT shares, avg_price FROM positions WHERE symbol=?", (symbol,))
            row = cursor.fetchone()

            if row:
                # 추가 매수
                old_shares, old_avg = row
                total_shares = old_shares + shares
                new_avg = ((old_shares * old_avg) + (shares * price)) / total_shares

                cursor.execute('''
                    UPDATE positions 
                    SET shares=?, avg_price=?, current_price=?, updated_at=? 
                    WHERE symbol=?
                ''', (total_shares, new_avg, price, now, symbol))
            else:
                # 신규 매수
                cursor.execute('''
                    INSERT INTO positions (symbol, shares, avg_price, current_price, highest_price, pnl, return_pct, entry_date, strategy_name, sector, updated_at)
                    VALUES (?, ?, ?, ?, ?, 0, 0, ?, ?, ?, ?)
                ''', (symbol, shares, price, price, price, date_str, strategy_name, sector, now))

            # 3. 거래 기록
            cursor.execute('''
                INSERT INTO trade_history (date, type, symbol, shares, price, amount, commission, strategy_name)
                VALUES (?, 'BUY', ?, ?, ?, ?, ?, ?)
            ''', (date_str, symbol, shares, price, cost, commission, strategy_name))

            self.conn.commit()
            return True

        except Exception as e:
            self.conn.rollback()
            print(f"❌ 매수 오류: {e}")
            return False

    def sell(self, symbol, price, shares, date, reason="Exit", commission=0.0):
        """매도 실행 및 DB 업데이트"""

        # [수정] 날짜가 Timestamp 객체일 경우 문자열로 변환
        date_str = str(date)

        cursor = self.conn.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        try:
            cursor.execute("SELECT shares, avg_price FROM positions WHERE symbol=?", (symbol,))
            row = cursor.fetchone()
            if not row: return False

            current_shares, avg_price = row
            sell_shares = min(shares, current_shares)

            # 1. 현금 입금
            revenue = (price * sell_shares) - commission
            cursor.execute("UPDATE account SET cash = cash + ?, updated_at = ? WHERE id=1", (revenue, now))

            # 2. 수익 계산
            profit = (price - avg_price) * sell_shares - commission

            # 3. 포지션 갱신 또는 삭제
            if sell_shares >= current_shares:
                cursor.execute("DELETE FROM positions WHERE symbol=?", (symbol,))
            else:
                cursor.execute("UPDATE positions SET shares = shares - ? WHERE symbol=?", (sell_shares, symbol))

            # 4. 거래 기록
            cursor.execute('''
                INSERT INTO trade_history (date, type, symbol, shares, price, amount, commission, reason, profit)
                VALUES (?, 'SELL', ?, ?, ?, ?, ?, ?, ?)
            ''', (date_str, symbol, sell_shares, price, revenue, commission, reason, profit))

            self.conn.commit()
            return True

        except Exception as e:
            self.conn.rollback()
            print(f"❌ 매도 오류: {e}")
            return False

    # =========================================================================
    # 🔄 시장 데이터 업데이트 (Daily Update)
    # =========================================================================
    def update_market_status(self, symbol, current_price):
        """현재가로 포지션 상태 갱신"""
        cursor = self.conn.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        try:
            cursor.execute("SELECT shares, avg_price, highest_price FROM positions WHERE symbol=?", (symbol,))
            row = cursor.fetchone()

            if row:
                shares, avg_price, highest_price = row

                new_highest = max(highest_price, current_price)
                pnl = (current_price - avg_price) * shares
                return_pct = ((current_price - avg_price) / avg_price) * 100

                cursor.execute('''
                    UPDATE positions 
                    SET current_price=?, highest_price=?, pnl=?, return_pct=?, updated_at=?
                    WHERE symbol=?
                ''', (current_price, new_highest, pnl, return_pct, now, symbol))

                self.conn.commit()
        except Exception as e:
            pass

    def check_trailing_stop(self, symbol, current_price, current_atr, multiplier=2.5):
        """트레일링 스탑 체크"""
        # 1. 상태 업데이트 (최고가 갱신)
        self.update_market_status(symbol, current_price)

        # 2. DB 조회
        cursor = self.conn.cursor()
        cursor.execute("SELECT highest_price FROM positions WHERE symbol=?", (symbol,))
        row = cursor.fetchone()

        if not row: return False, 0.0

        highest = row[0]
        safe_atr = current_atr if current_atr > 0 else (current_price * 0.02)
        stop_price = highest - (safe_atr * multiplier)

        is_triggered = current_price < stop_price
        return is_triggered, stop_price

    def _get_conn(self):
        return self.conn