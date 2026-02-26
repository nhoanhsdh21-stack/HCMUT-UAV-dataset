import os
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
from collections import Counter

def parse_int(text, default=0):
    try:
        return int(str(text).strip())
    except Exception:
        return default

def main():
    ap = argparse.ArgumentParser("Count instances from Pascal VOC XMLs")
    ap.add_argument("--ann_dir", required=True, help="Path to annotations folder")
    ap.add_argument("--recursive", action="store_true", help="Search XMLs recursively")
    ap.add_argument("--exclude_difficult", action="store_true",
                    help="Exclude objects with <difficult>1</difficult>")
    args = ap.parse_args()

    ann_dir = Path(args.ann_dir)
    xml_files = sorted(ann_dir.rglob("*.xml")) if args.recursive else sorted(ann_dir.glob("*.xml"))

    if not xml_files:
        print(f"[ERROR] No XML files found in: {ann_dir}")
        return

    total_images = 0
    empty_images = 0
    total_instances = 0
    class_counter = Counter()
    difficult_instances = 0
    parse_errors = 0

    for xf in xml_files:
        try:
            root = ET.parse(xf).getroot()
            total_images += 1

            objects = root.findall("object")
            if not objects:
                empty_images += 1
                continue

            for obj in objects:
                name_el = obj.find("name")
                cls = (name_el.text.strip() if (name_el is not None and name_el.text) else "UNKNOWN")

                diff_el = obj.find("difficult")
                is_diff = parse_int(diff_el.text if diff_el is not None else 0, 0) == 1
                if is_diff:
                    difficult_instances += 1
                    if args.exclude_difficult:
                        continue

                total_instances += 1
                class_counter[cls] += 1

        except Exception as e:
            parse_errors += 1
            print(f"[PARSE ERROR] {xf.name}: {e}")

    print("===== SUMMARY =====")
    print(f"XML files (images)        : {len(xml_files)}")
    print(f"Parsed images             : {total_images}")
    print(f"Images with 0 objects      : {empty_images}")
    print(f"Total instances (objects)  : {total_instances}")
    print(f"Difficult instances (all)  : {difficult_instances}")
    print(f"Parse errors              : {parse_errors}")

    print("\n===== INSTANCES PER CLASS =====")
    for cls, cnt in class_counter.most_common():
        print(f"{cls:20s} {cnt}")

if __name__ == "__main__":
    main()
