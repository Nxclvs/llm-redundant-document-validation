import sys
from pathlib import Path

# 1. Python-Pfad reparieren (damit imports funktionieren)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# 2. Jetzt importieren
from framework.metrics.metrics import evaluate_all

# 3. Pfade definieren (WICHTIG: Mit PROJECT_ROOT verknüpfen!)
RESULTS_DIR = PROJECT_ROOT / "results"

# HIER WAR DER FEHLER:
# 1. PROJECT_ROOT davor setzen
# 2. Den richtigen Datensatz-Namen (generated_de_v1_mini) nutzen
GROUND_TRUTH_DIR = PROJECT_ROOT / "tests" / "datasets" / "generated_de_v1" / "ground_truth"

OUTPUT_FILE = RESULTS_DIR / "metrics_summary.json"


if __name__ == "__main__":
    print(f"Project Root: {PROJECT_ROOT}")
    print(f"Results Dir:  {RESULTS_DIR}")
    print(f"GT Dir:       {GROUND_TRUTH_DIR}")

    # Sicherheitscheck vor dem Crash
    if not GROUND_TRUTH_DIR.exists():
        print(f"\n❌ FEHLER: Der Ground-Truth Ordner existiert nicht:\n   {GROUND_TRUTH_DIR}")
        print("   Hast du den Datensatz mit 'python scripts/generate_test_data.py --dataset generated_de_v1_mini' erstellt?")
        sys.exit(1)

    if not RESULTS_DIR.exists():
        print(f"\n❌ FEHLER: Der Results Ordner existiert nicht:\n   {RESULTS_DIR}")
        print("   Hast du vorher 'batch_run.py' ausgeführt?")
        sys.exit(1)

    print("\nRunning metrics evaluation...")

    evaluate_all(
        results_root=RESULTS_DIR,
        ground_truth_root=GROUND_TRUTH_DIR,
        output_path=OUTPUT_FILE,
    )

    print(f"\n✅ Metrics written to: {OUTPUT_FILE}")