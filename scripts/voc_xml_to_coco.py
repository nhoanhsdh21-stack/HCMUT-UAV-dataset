#!/usr/bin/env python3
"""Convert Pascal VOC XML annotations to COCO JSON.

Designed for the public HCMUT-UAV XML release format (one XML per image).
By default, only two classes are used:
  1: car
  2: motorbike

Usage:
  python scripts/voc_xml_to_coco.py \
    --images ./HCMUT-UAV/images \
    --annotations ./HCMUT-UAV/annotations \
    --output ./HCMUT-UAV/annotations_coco.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

IMAGE_EXTS = [".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"]

DEFAULT_CLASS_MAP = {
    "car": 1,
    "motorbike": 2,
    "motorbike\n": 2,
}


def find_image_file(images_dir: Path, stem: str) -> Path | None:
    for ext in IMAGE_EXTS:
        p = images_dir / f"{stem}{ext}"
        if p.exists():
            return p
    # Fallback: case-insensitive scan (slower but safer for mixed-case extensions)
    for p in images_dir.iterdir():
        if p.is_file() and p.stem == stem and p.suffix.lower() in IMAGE_EXTS:
            return p
    return None


def get_text(parent: ET.Element, tag: str, default: str | None = None) -> str | None:
    child = parent.find(tag)
    if child is None or child.text is None:
        return default
    return child.text.strip()


def parse_int(text: str | None, field: str) -> int:
    if text is None:
        raise ValueError(f"Missing integer field: {field}")
    return int(float(text))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", required=True, type=Path)
    parser.add_argument("--annotations", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--allow-unknown",
        action="store_true",
        help="Skip unknown class labels instead of raising an error.",
    )
    args = parser.parse_args()

    images_dir = args.images
    ann_dir = args.annotations
    output_path = args.output

    if not images_dir.is_dir():
        print(f"[ERROR] Images directory not found: {images_dir}")
        return 2
    if not ann_dir.is_dir():
        print(f"[ERROR] Annotations directory not found: {ann_dir}")
        return 2

    xml_files = sorted([p for p in ann_dir.iterdir() if p.is_file() and p.suffix.lower() == ".xml"])
    if not xml_files:
        print(f"[ERROR] No XML files found in: {ann_dir}")
        return 2

    coco = {
        "info": {
            "description": "HCMUT-UAV (converted from VOC XML to COCO JSON)",
            "version": "1.0",
            "year": None,
            "contributor": None,
            "url": None,
            "date_created": None,
        },
        "licenses": [],
        "images": [],
        "annotations": [],
        "categories": [
            {"id": 1, "name": "car", "supercategory": "vehicle"},
            {"id": 2, "name": "motorbike", "supercategory": "vehicle"},
        ],
    }

    ann_id = 1
    img_id = 1
    num_skipped_unknown = 0
    num_missing_images = 0

    for xml_path in xml_files:
        try:
            root = ET.parse(xml_path).getroot()
        except ET.ParseError as e:
            print(f"[ERROR] XML parse failed: {xml_path.name}: {e}")
            return 3

        stem = xml_path.stem
        image_path = find_image_file(images_dir, stem)
        if image_path is None:
            print(f"[WARN] Missing image for XML: {xml_path.name}")
            num_missing_images += 1
            continue

        size_node = root.find("size")
        if size_node is not None:
            width = parse_int(get_text(size_node, "width"), "size/width")
            height = parse_int(get_text(size_node, "height"), "size/height")
        else:
            # Fallback: try PIL if available
            try:
                from PIL import Image  # type: ignore
                with Image.open(image_path) as im:
                    width, height = im.size
            except Exception:
                raise ValueError(
                    f"Missing <size> in {xml_path.name} and unable to read image dimensions. "
                    "Install Pillow or ensure VOC XML includes size/width and size/height."
                )

        coco["images"].append(
            {
                "id": img_id,
                "file_name": image_path.name,
                "width": width,
                "height": height,
            }
        )

        for obj in root.findall("object"):
            raw_name = (get_text(obj, "name", "") or "").strip()
            label_key = raw_name.lower()
            cat_id = DEFAULT_CLASS_MAP.get(label_key)
            if cat_id is None:
                msg = f"Unknown class label '{raw_name}' in {xml_path.name}"
                if args.allow_unknown:
                    print(f"[WARN] {msg} -> skipped")
                    num_skipped_unknown += 1
                    continue
                raise ValueError(msg)

            bnd = obj.find("bndbox")
            if bnd is None:
                print(f"[WARN] Missing bndbox in {xml_path.name}; object skipped")
                continue

            xmin = parse_int(get_text(bnd, "xmin"), "bndbox/xmin")
            ymin = parse_int(get_text(bnd, "ymin"), "bndbox/ymin")
            xmax = parse_int(get_text(bnd, "xmax"), "bndbox/xmax")
            ymax = parse_int(get_text(bnd, "ymax"), "bndbox/ymax")

            # Normalize ordering and clip to image range
            x1, x2 = sorted((xmin, xmax))
            y1, y2 = sorted((ymin, ymax))
            x1 = max(0, min(x1, width - 1))
            y1 = max(0, min(y1, height - 1))
            x2 = max(0, min(x2, width))
            y2 = max(0, min(y2, height))

            w = max(0, x2 - x1)
            h = max(0, y2 - y1)
            if w <= 0 or h <= 0:
                print(f"[WARN] Invalid box in {xml_path.name}: [{xmin},{ymin},{xmax},{ymax}] -> skipped")
                continue

            difficult = get_text(obj, "difficult", "0")
            iscrowd = 1 if str(difficult).strip() == "1" else 0

            coco["annotations"].append(
                {
                    "id": ann_id,
                    "image_id": img_id,
                    "category_id": cat_id,
                    "bbox": [x1, y1, w, h],
                    "area": float(w * h),
                    "iscrowd": iscrowd,
                }
            )
            ann_id += 1

        img_id += 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(coco, f, ensure_ascii=False, indent=2)

    print("=== VOC XML -> COCO JSON Conversion Complete ===")
    print(f"Images written       : {len(coco['images'])}")
    print(f"Annotations written  : {len(coco['annotations'])}")
    print(f"Unknown labels skipped: {num_skipped_unknown}")
    print(f"Missing images skipped: {num_missing_images}")
    print(f"Output               : {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
