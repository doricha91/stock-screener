from pathlib import Path
import json
import pandas as pd

# 현재 파일 위치: scripts/batch/merge_meta_json.py
THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[2]

meta_dir = PROJECT_ROOT / "outputs" / "meta"
files = sorted(meta_dir.glob("meta_*.json"))

print(f"PROJECT_ROOT: {PROJECT_ROOT}")
print(f"META_DIR    : {meta_dir}")

if not files:
    print("meta 파일을 찾지 못했습니다.")
    raise SystemExit(1)

rows = []
for file in files:
    with open(file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 어떤 파일에서 왔는지 추적용
    data["source_file"] = file.name
    rows.append(data)

df = pd.DataFrame(rows)

output_file = meta_dir / "merged_meta_all.csv"
df.to_csv(output_file, index=False, encoding="utf-8-sig")

print(f"완료: {output_file}")
print(f"총 {len(files)}개 파일 병합")