#!/usr/bin/env python3
"""Validate image/XML pairing for an object detection dataset release.

One annotation XML per image with the same filename stem, e.g.:
  images/000001.jpg
  annotations/000001.xml
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


def list_image_stems(images_dir: Path) -> set[str]:
    stems = set()
    for p in images_dir.iterdir():
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS:
            stems.add(p.stem)
    return stems


def list_xml_stems(ann_dir: Path) -> set[str]:
    return {p.stem for p in ann_dir.iterdir() if p.is_file() and p.suffix.lower() == ".xml"}


def format_examples(items: Iterable[str], max_items: int = 10) -> str:
    items = list(sorted(items))
    if not items:
        return "(none)"
    head = items[:max_items]
    suffix = "" if len(items) <= max_items else f" ... (+{len(items)-max_items} more)"
    return ", ".join(head) + suffix


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", required=True, type=Path, help="Path to images directory")
    parser.add_argument("--annotations", required=True, type=Path, help="Path to XML annotations directory")
    args = parser.parse_args()

    images_dir: Path = args.images
    ann_dir: Path = args.annotations

    if not images_dir.is_dir():
        print(f"[ERROR] Images directory not found: {images_dir}")
        return 2
    if not ann_dir.is_dir():
        print(f"[ERROR] Annotations directory not found: {ann_dir}")
        return 2

    image_stems = list_image_stems(images_dir)
    xml_stems = list_xml_stems(ann_dir)

    missing_xml = image_stems - xml_stems
    missing_img = xml_stems - image_stems

    print("=== HCMUT-UAV Pair Check ===")
    print(f"Images found        : {len(image_stems)}")
    print(f"XML annotations found: {len(xml_stems)}")
    print(f"Paired files        : {len(image_stems & xml_stems)}")
    print()

    if missing_xml:
        print(f"[WARN] Images without XML ({len(missing_xml)}):")
        print("       " + format_examples(missing_xml))
    else:
        print("[OK] Every image has a matching XML annotation.")

    if missing_img:
        print(f"[WARN] XML files without image ({len(missing_img)}):")
        print("       " + format_examples(missing_img))
    else:
        print("[OK] Every XML has a matching image file.")

    if not missing_xml and not missing_img:
        print("\n[SUCCESS] Dataset pairing looks consistent.")
        return 0

    print("\n[CHECK REQUIRED] Please fix missing pairs.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
