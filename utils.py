# [ 📄 utils.py ]

import os
import pandas as pd
import datetime

REPORTS_DIR = "reports"


def save_report(results_list):
    """
    분석 결과를 리스트로 받아 reports 폴더에 CSV 파일로 저장합니다.

    :param results_list: (list) 스크리너가 찾은 'Buy' 신호 종목들의 딕셔너리 리스트
    """

    # 1. 결과가 없으면 저장하지 않고 종료
    if not results_list:
        print("분석 결과: 'Buy' 신호를 찾지 못했습니다.")
        return

    # 2. 파일명 생성 (예: report_2025-11-08.csv)
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    filename = f"report_{today_str}.csv"
    file_path = os.path.join(REPORTS_DIR, filename)

    # 3. 리스트를 Pandas DataFrame으로 변환
    df = pd.DataFrame(results_list)

    # 4. CSV 파일로 저장
    try:
        df.to_csv(file_path, index=False)
        print(f"성공: 리포트가 {file_path} 에 저장되었습니다.")
    except Exception as e:
        print(f"오류: 리포트 저장 실패. {e}")