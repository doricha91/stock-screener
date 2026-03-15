from pathlib import Path
import pandas as pd

# 현재 파일 위치: scripts/batch/merge_summary_csv.py
THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[2]

summary_dir = PROJECT_ROOT / "outputs" / "summary"
files = sorted(summary_dir.glob("summary_*.csv"))

print(f"PROJECT_ROOT: {PROJECT_ROOT}")
print(f"SUMMARY_DIR : {summary_dir}")

if not files:
    print("summary 파일을 찾지 못했습니다.")
    raise SystemExit(1)

dfs = []
for file in files:
    df = pd.read_csv(file)
    df["source_file"] = file.name  # 어떤 파일에서 왔는지 추적용
    dfs.append(df)

merged = pd.concat(dfs, ignore_index=True)

output_file = summary_dir / "merged_summary_all.csv"
merged.to_csv(output_file, index=False, encoding="utf-8-sig")

print(f"완료: {output_file}")
print(f"총 {len(files)}개 파일, {len(merged)}행 병합")