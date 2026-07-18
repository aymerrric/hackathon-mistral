"""Download the MultiWOZ 2.2 dataset via Salesforce/DialogStudio on Hugging Face."""

from pathlib import Path

from datasets import load_dataset

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = REPO_ROOT / "data" / "multiwoz_2_2"


def main():
    dataset = load_dataset("Salesforce/dialogstudio", "MULTIWOZ2_2", trust_remote_code=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dataset.save_to_disk(str(OUTPUT_DIR))
    print(f"Saved splits {list(dataset.keys())} to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
