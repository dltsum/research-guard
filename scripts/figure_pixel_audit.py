"""Reproducible native-resolution evidence, never an automatic aesthetic verdict.

python figure_pixel_audit.py reference.png candidate.png --output audit-dir
    [--regions regions.json] [--geometry geometry.json]
Regions: [{"id":"label", "reference":[l,t,r,b], "candidate":[l,t,r,b]}]
Geometry: {"boxes":[{"id":"a","bbox":[l,t,r,b]}],
 "edges":[{"id":"e","points":[[x,y],...],"max_bends":2}],
 "flat_regions":[{"id":"fill","bbox":[l,t,r,b],"max_channel_range":0}]}
All coordinates are pixels. Geometry rules are declared expectations, not guesses
about the meaning of a raster image. Unlabelled overlaps are review evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageChops


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bbox(value, size):
    if (not isinstance(value, list) or len(value) != 4
            or any(type(v) is not int for v in value)):
        raise ValueError("bounding boxes require four integer pixel coordinates")
    left, top, right, bottom = value
    if not (0 <= left < right <= size[0] and 0 <= top < bottom <= size[1]):
        raise ValueError("bounding box is outside the native image")
    return value


def alpha_metrics(reference, candidate):
    """Compare rendered alpha separately from the existing RGB metrics."""
    if reference.size != candidate.size:
        return {"status": "SIZE_MISMATCH", "channels": ["A"]}
    has_alpha = lambda im: "A" in im.getbands() or "transparency" in im.info
    if not (has_alpha(reference) or has_alpha(candidate)):
        return {"status": "NOT_PRESENT", "channels": ["A"]}
    delta = ImageChops.difference(reference.convert("RGBA").getchannel("A"),
                                  candidate.convert("RGBA").getchannel("A"))
    histogram = delta.histogram()
    pixels = delta.width * delta.height
    return {"status": "COMPARED", "channels": ["A"], "pixels_examined": pixels,
            "changed_pixels": pixels - histogram[0],
            "mean_absolute_difference": sum(i * count for i, count in enumerate(histogram)) / pixels,
            "maximum_absolute_difference": delta.getextrema()[1]}


def compare(reference: Path, candidate: Path, output: Path, *, regions=None, geometry=None):
    output.mkdir(parents=True, exist_ok=True)
    with Image.open(reference) as im:
        ref_native = im.copy()
        ref = im.convert("RGB")
    with Image.open(candidate) as im:
        cand_native = im.copy()
        cand = im.convert("RGB")
    report = {
        "schema_version": 1, "reference_sha256": sha256(reference),
        "candidate_sha256": sha256(candidate), "reference_size": list(ref.size),
        "candidate_size": list(cand.size), "resized": False,
        "pixel_comparison": None, "alpha_comparison": alpha_metrics(ref_native, cand_native),
        "regions": [], "geometry_findings": [],
        "conclusion_boundary": "Pixel differences, geometry and flat-color checks are evidence only; they do not prove information completeness, style fidelity or visual quality.",
    }
    if ref.size == cand.size:
        delta = ImageChops.difference(ref, cand)
        histogram = delta.histogram()
        absolute_sum = sum((i % 256) * count for i, count in enumerate(histogram))
        red, green, blue = delta.split()
        changed = ref.width * ref.height - ImageChops.lighter(ImageChops.lighter(red, green), blue).histogram()[0]
        delta.save(output / "absolute-difference.png")
        report["pixel_comparison"] = {
            "channels": ["R", "G", "B"],
            "pixels_examined": ref.width * ref.height,
            "changed_pixels": changed, "mean_absolute_channel_difference": absolute_sum / (ref.width * ref.height * 3),
            "difference_image": "absolute-difference.png",
        }
        if report["alpha_comparison"]["status"] == "COMPARED":
            ImageChops.difference(ref_native.convert("RGBA").getchannel("A"),
                                  cand_native.convert("RGBA").getchannel("A")).save(output / "alpha-difference.png")
            report["alpha_comparison"]["difference_image"] = "alpha-difference.png"
    else:
        report["pixel_comparison"] = {"status": "SIZE_MISMATCH", "reason": "No implicit resize or aligned-pixel similarity claim is made."}
    seen = set()
    for index, region in enumerate(regions or []):
        identifier = str(region.get("id") or "")
        if not identifier or identifier in seen:
            raise ValueError("crop regions require distinct non-empty ids")
        seen.add(identifier)
        item = {"id": identifier}
        for name, im in (("reference", ref_native), ("candidate", cand_native)):
            box = bbox(region.get(name), im.size)
            filename = f"crop-{index + 1:03d}-{name}.png"
            native_crop = im.crop(tuple(box))
            # PNG supports these original sample modes. Other image modes use
            # an explicit rendering conversion; never call that native channels.
            png_crop = native_crop if im.mode in {"1", "L", "LA", "P", "RGB", "RGBA"} else native_crop.convert("RGBA")
            png_crop.save(output / filename)
            with Image.open(output / filename) as saved:
                preserved = saved.mode == native_crop.mode and saved.tobytes() == native_crop.tobytes()
                crop_mode = saved.mode
            item[name] = {"bbox": box, "path": filename, "native_resolution": True,
                          "source_mode": im.mode, "crop_mode": crop_mode,
                          "native_channels_preserved": preserved}
        report["regions"].append(item)
    geometry = geometry or {}
    boxes = geometry.get("boxes", [])
    for item in boxes:
        bbox(item.get("bbox"), cand.size)
    for index, left in enumerate(boxes):
        for right in boxes[index + 1:]:
            a, b = left["bbox"], right["bbox"]
            area = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
            if area and not (left.get("allow_overlap") or right.get("allow_overlap")):
                report["geometry_findings"].append({"type": "box_overlap", "ids": [left["id"], right["id"]], "area_px": area})
        if "text_bbox" in left:
            text = bbox(left["text_bbox"], cand.size)
            a = left["bbox"]
            if not (a[0] <= text[0] < text[2] <= a[2] and a[1] <= text[1] < text[3] <= a[3]):
                report["geometry_findings"].append({"type": "text_outside_box", "id": left["id"]})
            offset = [abs((a[0] + a[2] - text[0] - text[2]) / 2), abs((a[1] + a[3] - text[1] - text[3]) / 2)]
            if max(offset) > float(left.get("center_tolerance_px", 2)):
                report["geometry_findings"].append({"type": "text_not_centered", "id": left["id"], "offset_px": offset})
    for edge in geometry.get("edges", []):
        points = edge.get("points", [])
        if len(points) < 2 or any(not isinstance(p, list) or len(p) != 2 or any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in p) for p in points):
            raise ValueError("edges need at least two finite pixel points")
        if any(not (0 <= p[0] <= cand.width and 0 <= p[1] <= cand.height) for p in points):
            raise ValueError("edge point is outside the candidate image")
        if len(points) - 2 > int(edge.get("max_bends", 2)):
            report["geometry_findings"].append({"type": "excessive_bends", "id": edge["id"], "bends": len(points) - 2})
        for endpoint, expected in ((points[0], edge.get("source_anchor")), (points[-1], edge.get("target_anchor"))):
            if expected is not None and math.dist(endpoint, expected) > float(edge.get("anchor_tolerance_px", 2)):
                report["geometry_findings"].append({"type": "disconnected_anchor", "id": edge["id"], "distance_px": math.dist(endpoint, expected)})
    for region in geometry.get("flat_regions", []):
        box = bbox(region.get("bbox"), cand.size)
        ranges = [hi - lo for lo, hi in cand.crop(tuple(box)).getextrema()]
        if max(ranges) > int(region.get("max_channel_range", 0)):
            report["geometry_findings"].append({"type": "nonuniform_flat_fill", "id": region["id"], "channel_ranges": ranges})
    (output / "pixel-audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--regions", type=Path)
    parser.add_argument("--geometry", type=Path)
    args = parser.parse_args()
    load = lambda p: json.loads(p.read_text(encoding="utf-8")) if p else None
    print(json.dumps(compare(args.reference, args.candidate, args.output, regions=load(args.regions), geometry=load(args.geometry)), ensure_ascii=False))


if __name__ == "__main__":
    main()
