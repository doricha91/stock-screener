# db_analyzer.py, DB 시각화, 분석

import sqlite3
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import os

# 한글 폰트 설정 (Windows 기준, 그래프 깨짐 방지)
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

# 그래프를 저장할 폴더 생성 (없으면 자동 생성)
save_dir = "analysis_results"
if not os.path.exists(save_dir):
    os.makedirs(save_dir)

# 1. DB 연결 및 데이터 불러오기
# 'your_database.db'를 실제 파일명으로, 'table_name'을 실제 테이블명으로 변경하세요.
con = sqlite3.connect('backtest_log.db')
query = "SELECT * FROM optimization_log"  # 테이블 이름을 확인해주세요
df = pd.read_sql(query, con)
con.close()

# 데이터 확인
print(df.head())
print(df.info())

# 2. 주요 파라미터와 성과 지표 간의 상관관계 분석
# 분석하고 싶은 컬럼만 선택 (입력 변수 + 결과 변수)
cols_to_analyze = [
    'exit_period', 'rs_lookback', 'score_threshold', 'rs_weight', 'turtle_weight', # 입력(파라미터)
    'cagr', 'mdd', 'sharpe_ratio', 'win_rate', 'profit_factor' # 결과(성과)
]

# 상관계수 계산
corr = df[cols_to_analyze].corr()

# 히트맵 그리기
plt.figure(figsize=(12, 10))
sns.heatmap(corr, annot=True, fmt=".2f", cmap='coolwarm', vmin=-1, vmax=1)
plt.title('파라미터와 성과 지표 간의 상관관계')
plt.savefig(f"{save_dir}/heatmap.png", dpi=300)
plt.show()

# 3. CAGR(수익률) vs MDD(낙폭) 산점도
plt.figure(figsize=(10, 6))
sns.scatterplot(data=df, x='mdd', y='cagr', hue='sharpe_ratio', size='profit_factor', palette='viridis', sizes=(20, 200))

plt.title('리스크(MDD) 대비 수익률(CAGR) 분석')
plt.xlabel('MDD (최대 낙폭, %)')
plt.ylabel('CAGR (연평균 수익률, %)')
plt.grid(True)
plt.savefig(f"{save_dir}/scatterplot_MDD_CAGR.png", dpi=300)
plt.show()

# 4. exit_period(청산 기간)에 따른 CAGR 분포 확인
plt.figure(figsize=(10, 6))
sns.boxplot(data=df, x='exit_period', y='cagr')
plt.title('청산 기간(Exit Period)별 수익률 분포')
plt.savefig(f"{save_dir}/boxplot_exit_period_CAGR.png", dpi=300)
plt.show()

# ---------------------------------------------------------
# [추가 코드] 파라미터 조합 심층 분석
# ---------------------------------------------------------

# 6. 모든 주요 변수별 수익률(CAGR) 분포 자동 시각화 (Box Plot 반복)
# turtle_weight는 값이 1.0 하나뿐이라 제외했습니다.
target_params = ['exit_period', 'rs_lookback', 'entry_period', 'max_positions', 'rs_weight', 'score_threshold']

# 서브플롯 설정 (2행 3열로 배치)
fig, axes = plt.subplots(2, 3, figsize=(18, 10))
axes = axes.flatten() # 2차원 배열을 1차원으로 펴서 반복문 돌리기 쉽게 만듦

for i, param in enumerate(target_params):
    sns.boxplot(data=df, x=param, y='cagr', hue=param, ax=axes[i], palette='Set2', legend=False)
    axes[i].set_title(f'{param}별 CAGR 분포')
    axes[i].set_xlabel(param)
    axes[i].set_ylabel('CAGR (%)')

plt.tight_layout()
plt.savefig(f"{save_dir}/all_params_boxplot.png", dpi=300)
print(f"[{save_dir}/all_params_boxplot.png] 저장 완료")
plt.show()


# 7. 핵심 변수 조합 핫스팟 분석 (Pivot Table Heatmap)
# 가장 중요한 두 변수 'exit_period'와 'rs_lookback'의 조합별 평균 수익률을 봅니다.
# "어떤 청산 기간과 어떤 RS 기간이 만났을 때 붉은색(고수익)인가?"를 찾으세요.
pivot_table = df.pivot_table(index='rs_lookback', columns='exit_period', values='cagr', aggfunc='mean')

plt.figure(figsize=(10, 8))
sns.heatmap(pivot_table, annot=True, fmt=".1f", cmap='RdYlGn', center=20) # center는 중간 수익률 기준값
plt.title('RS 기간(Lookback) vs 청산 기간(Exit) 조합별 평균 CAGR')
plt.ylabel('RS Lookback (일)')
plt.xlabel('Exit Period (일)')
plt.savefig(f"{save_dir}/heatmap_combination.png", dpi=300)
print(f"[{save_dir}/heatmap_combination.png] 저장 완료")
plt.show()


# 8. RS 비중과 진입 문턱의 관계 (Interaction Plot)
# rs_weight가 높을 때, score_threshold를 높이는 게 좋은지 낮추는 게 좋은지 확인합니다.
plt.figure(figsize=(12, 6))
sns.pointplot(data=df, x='rs_weight', y='cagr', hue='score_threshold', errorbar=None) # errorbar=None은 신뢰구간 제외 깔끔하게
plt.title('RS 비중(Weight)과 진입 점수(Threshold)의 관계')
plt.ylabel('평균 CAGR (%)')
plt.grid(True, alpha=0.3)
plt.savefig(f"{save_dir}/rs_interaction.png", dpi=300)
print(f"[{save_dir}/rs_interaction.png] 저장 완료")
plt.show()

# 9. 통계적으로 가장 우수한 파라미터 값 출력 (Robustness Check)
# 단순히 1등 전략의 파라미터가 아니라, "평균적으로 가장 성과가 좋은 값"을 보여줍니다.
print("\n=== 변수별 평균 성과 (Robustness Check) ===")
for param in target_params:
    best_val = df.groupby(param)['cagr'].mean().idxmax()
    max_val = df.groupby(param)['cagr'].mean().max()
    print(f"[{param}] 최적값: {best_val} (평균 CAGR: {max_val:.2f}%)")

# 5. Sharpe Ratio가 높은 순서대로 정렬하여 상위 5개 출력
top_strategies = df.sort_values(by='sharpe_ratio', ascending=False).head(5)

print("=== 샤프 지수 기준 Top 5 전략 ===")
# 보고 싶은 주요 컬럼만 출력
display_cols = ['id', 'cagr', 'mdd', 'sharpe_ratio', 'win_rate', 'exit_period', 'rs_weight', 'turtle_weight']
print(top_strategies[display_cols])