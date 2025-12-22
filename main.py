# [ 📄 main.py (최종본) ]

import screener  # 5단계 모듈
import utils  # 5단계 모듈
import datetime


def main():
    """
    주식 스크리너 프로그램의 메인 실행 함수
    """
    print("=" * 50)
    print(f"주식 스크리너 프로그램을 시작합니다. (Today: {datetime.date.today()})")
    print("=" * 50)

    # 1. 스크리너 실행 (screener.py)
    #    -> 'Buy' 신호가 나온 종목 리스트를 받아옴
    results = screener.run_screener()

    # 2. 리포트 저장 (utils.py)
    #    -> 받아온 리스트를 CSV 파일로 저장
    utils.save_report(results)

    print("=" * 50)
    print(f"스크리닝 완료. 총 {len(results)}개의 'Buy' 신호 종목을 찾았습니다.")
    print("프로그램을 종료합니다.")
    print("=" * 50)


# 이 파일(main.py)을 직접 실행했을 때만 main() 함수를 호출
if __name__ == "__main__":
    main()