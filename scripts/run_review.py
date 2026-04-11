# scripts/run_review.py
import sys
import argparse
from pathlib import Path

# 프로젝트 루트 추가
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.review_generator import ReviewGenerator

def main():
    parser = argparse.ArgumentParser(description="Front-test Execution Review")
    parser.add_argument("--days", type=int, default=7, help="Analysis period in days (default: 7)")
    args = parser.parse_args()

    print("\n" + "📊"*30)
    print(f" STOCK SCREENER - EXECUTION REVIEW (Last {args.days} Days)")
    print("📊"*30)

    try:
        generator = ReviewGenerator(days=args.days)
        report_path = generator.generate_report()
        
        if "❌" in report_path:
            print(report_path)
        else:
            print(f"\n✨ Review Report generated successfully!")
            print(f"👉 {report_path}")
            
    except Exception as e:
        print(f"\n❌ Error during review generation: {e}")
        sys.exit(1)

    print("\n" + "📊"*30 + "\n")

if __name__ == "__main__":
    main()
