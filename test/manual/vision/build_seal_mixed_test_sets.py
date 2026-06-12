from __future__ import annotations

import argparse
import json
import random
import shutil
from pathlib import Path

DEFAULT_SEALS_DIR = Path("test/seals")
DEFAULT_SEED = 20260612
DATASET_NAMES = ("train_images2", "train_images3", "train_images4")


def build_dataset(dataset_dir: Path, seed: int) -> dict:
    positive_dir = dataset_dir / "gen_imgs"
    negative_dir = dataset_dir / "gen_masks"
    output_dir = dataset_dir / "test"
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Output directory is not empty: {output_dir}")

    positives = sorted(positive_dir.glob("*.png"))
    records = []
    for positive_path in positives:
        negative_path = negative_dir / f"{positive_path.stem}_0.png"
        if not negative_path.is_file():
            raise FileNotFoundError(negative_path)
        records.extend(
            [
                {
                    "label": 1,
                    "source": positive_path,
                    "pair_id": positive_path.stem,
                },
                {
                    "label": 0,
                    "source": negative_path,
                    "pair_id": positive_path.stem,
                },
            ]
        )

    random.Random(seed).shuffle(records)
    output_dir.mkdir(parents=True)
    manifest = []
    for index, record in enumerate(records):
        output_name = f"{index:04d}_{record['label']}.png"
        output_path = output_dir / output_name
        shutil.copy2(record["source"], output_path)
        manifest.append(
            {
                "file": output_name,
                "label": record["label"],
                "pair_id": record["pair_id"],
                "source": str(record["source"]),
            }
        )

    payload = {
        "dataset": dataset_dir.name,
        "seed": seed,
        "images": len(manifest),
        "positives": sum(item["label"] for item in manifest),
        "negatives": sum(1 - item["label"] for item in manifest),
        "records": manifest,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seals-dir", type=Path, default=DEFAULT_SEALS_DIR)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()

    summaries = []
    for dataset_name in DATASET_NAMES:
        payload = build_dataset(
            args.seals_dir / dataset_name,
            args.seed,
        )
        summaries.append(
            {
                key: payload[key]
                for key in ("dataset", "seed", "images", "positives", "negatives")
            }
        )
    print(json.dumps(summaries, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
