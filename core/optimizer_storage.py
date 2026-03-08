import json
from datetime import datetime

TABLE_NAME = "optimization_log"          # Phase 1: 학습 결과 저장 (기존 기능)
OOS_TABLE_NAME = "oos_validation_log"    # Phase 2: 검증 결과 저장 (신규 기능)

# 🛠️ DB 관리 함수 1: 기존 학습 데이터용 (optimization_log)
def ensure_table_exists(conn, param_keys):
    cursor = conn.cursor()
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_date TEXT,
            total_return REAL, cagr REAL, mdd REAL, final_equity REAL,
            sharpe_ratio REAL, sortino_ratio REAL, calmar_ratio REAL,
            win_rate REAL, profit_factor REAL, total_trades INTEGER,
            avg_win REAL, avg_loss REAL, yearly_returns TEXT,
            cb_halt_days INTEGER, vix_trigger_count INTEGER, 
            drawdown_trigger_count INTEGER, breadth_low_count INTEGER,
            ma_cross_bearish_count INTEGER,
            panic_days INTEGER, bear_days INTEGER, 
            unstable_days INTEGER, bull_days INTEGER
        )
    ''')
    cursor.execute(f"PRAGMA table_info({TABLE_NAME})")
    existing_columns = {row[1] for row in cursor.fetchall()}
    
    # 파라미터 컬럼 추가
    for param in param_keys:
        if param not in existing_columns:
            try:
                cursor.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN {param} REAL")
            except:
                pass

    # 안전장치 컬럼 추가 (기존 테이블 대응)
    safety_cols = [
        'cb_halt_days', 'vix_trigger_count', 'drawdown_trigger_count', 
        'breadth_low_count', 'ma_cross_bearish_count',
        'panic_days', 'bear_days', 'unstable_days', 'bull_days'
    ]
    for col in safety_cols:
        if col not in existing_columns:
            try:
                cursor.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN {col} INTEGER DEFAULT 0")
            except:
                pass
    conn.commit()

def save_dynamic_result(conn, params, res):
    cursor = conn.cursor()
    record = {
        'run_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_return': round(res['return'], 2),
        'cagr': round(res['cagr'], 2),
        'mdd': round(res['mdd'], 2),
        'final_equity': round(res['final_equity'], 0),
        'sharpe_ratio': round(res.get('sharpe', 0), 4),
        'sortino_ratio': round(res.get('sortino', 0), 4),
        'calmar_ratio': round(res.get('calmar', 0), 4),
        'win_rate': round(res['win_rate'], 2),
        'profit_factor': round(res['profit_factor'], 2),
        'total_trades': res['total_trades'],
        'avg_win': round(res['avg_win'], 2),
        'avg_loss': round(res['avg_loss'], 2),
        'yearly_returns': res.get('yearly_json', '{}')
    }
    
    # 안전장치 통계 추가
    if 'safety_stats' in res:
        record.update(res['safety_stats'])
        
    record.update(params)
    columns = ', '.join(record.keys())
    placeholders = ', '.join(['?'] * len(record))
    values = list(record.values())
    try:
        cursor.execute(f"INSERT INTO {TABLE_NAME} ({columns}) VALUES ({placeholders})", values)
        conn.commit()
    except Exception as e:
        print(f"❌ DB 저장 오류 (Train): {e}")

# 🛠️ DB 관리 함수 2: 신규 검증 데이터용 (oos_validation_log)
def ensure_oos_table_exists(conn):
    cursor = conn.cursor()
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {OOS_TABLE_NAME} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_date TEXT,
            params_json TEXT,
            train_cagr REAL, train_mdd REAL, train_sharpe REAL,
            test_cagr REAL, test_mdd REAL, test_sharpe REAL,
            robustness_score REAL 
        )
    ''')
    conn.commit()

def save_oos_result(conn, params, train_res, test_res):
        cursor = conn.cursor()
        params_json = json.dumps(params)
        robustness = 0.0
        if train_res.get('sharpe', 0) != 0:
            robustness = round(test_res.get('sharpe', 0) / train_res['sharpe'], 2)

        sql = f'''
            INSERT INTO {OOS_TABLE_NAME} 
            (run_date, params_json, train_cagr, train_mdd, train_sharpe, test_cagr, test_mdd, test_sharpe, robustness_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        values = (
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            params_json,
            round(train_res['cagr'], 2), round(train_res['mdd'], 2), round(train_res.get('sharpe', 0), 2),
            round(test_res['cagr'], 2), round(test_res['mdd'], 2), round(test_res.get('sharpe', 0), 2),
            robustness
        )
        try:
            cursor.execute(sql, values)
            conn.commit()
        except Exception as e:
            print(f"❌ DB 저장 오류 (OOS): {e}")

