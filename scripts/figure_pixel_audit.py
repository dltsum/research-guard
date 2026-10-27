"""Reproducible native-resolution evidence, never an automatic aesthetic verdict.

python figure_pixel_audit.py reference.png candidate.png --output audit-dir
    [--regions regions.json] [--geometry geometry.json] [--require-flat-fills]
Regions: [{"id":"label", "reference":[l,t,r,b], "candidate":[l,t,r,b]}]
Geometry: {"boxes":[{"id":"a","bbox":[l,t,r,b]}],
 "edges":[{"id":"e","points":[[x,y],...],"max_bends":1}],
 "flat_regions":[{"id":"fill","bbox":[l,t,r,b],"max_channel_range":0}]}
All coordinates are pixels. Geometry rules are declared expectations, not guesses
about the meaning of a raster image. Unlabelled overlaps are review evidence.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw


def bbox(value, size):
    if (not isinstance(value, list) or len(value) != 4
            or any(type(v) is not int for v in value)):
        raise ValueError("bounding boxes require four integer pixel coordinates")
    left, top, right, bottom = value
    if not (0 <= left < right <= size[0] and 0 <= top < bottom <= size[1]):
        raise ValueError("bounding box is outside the native image")
    return value


def polyline_bends(points):
    """Count direction changes, not duplicate or forward-collinear samples.

    A reversal counts as a turn. This is not raster extraction or a shortest-
    route solver; callers supply the actual path and inspect simpler layouts.
    """
    if (not isinstance(points, list) or len(points) < 2
            or any(not isinstance(p, list) or len(p) != 2
                   or any(type(v) not in (int, float) or not math.isfinite(v) for v in p)
                   for p in points)):
        raise ValueError("edges need at least two finite pixel points")
    distinct = [points[0]]
    for point in points[1:]:
        if point != distinct[-1]:
            distinct.append(point)
    if len(distinct) < 2:
        raise ValueError("edge path needs at least two distinct points")
    bends = 0
    for a, b, c in zip(distinct, distinct[1:], distinct[2:]):
        u = (b[0] - a[0], b[1] - a[1])
        v = (c[0] - b[0], c[1] - b[1])
        cross = u[0] * v[1] - u[1] * v[0]
        dot = u[0] * v[0] + u[1] * v[1]
        if cross != 0 or dot <= 0:
            bends += 1
    return bends


def connector_findings(geometry, size):
    """Recompute declared routing defects for both CLI and final admission."""
    geometry = {} if geometry is None else geometry
    if not isinstance(geometry, dict) or not isinstance(geometry.get("edges", []), list):
        raise ValueError("geometry edges must be an array")
    findings = []
    for edge in geometry.get("edges", []):
        if not isinstance(edge, dict) or not isinstance(edge.get("id"), str) or not edge["id"].strip():
            raise ValueError("edges need a non-empty string id")
        points = edge.get("points", [])
        bends = polyline_bends(points)
        if any(not (0 <= p[0] <= size[0] and 0 <= p[1] <= size[1]) for p in points):
            raise ValueError("edge point is outside the candidate image")
        budget = edge.get("max_bends", 1)
        if type(budget) is not int or budget < 0:
            raise ValueError("max_bends must be a nonnegative integer")
        reason = edge.get("routing_reason")
        if budget > 1 and (not isinstance(reason, str) or not reason.strip()):
            findings.append({"type": "unjustified_bend_budget", "id": edge["id"], "max_bends": budget})
        if bends > budget:
            findings.append({"type": "excessive_bends", "id": edge["id"], "bends": bends, "max_bends": budget})
        for endpoint, expected in ((points[0], edge.get("source_anchor")), (points[-1], edge.get("target_anchor"))):
            if expected is not None and math.dist(endpoint, expected) > float(edge.get("anchor_tolerance_px", 2)):
                findings.append({"type": "disconnected_anchor", "id": edge["id"], "distance_px": math.dist(endpoint, expected)})
    return findings


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


def flat_fill_metrics(candidate, geometry=None):
    """Inspect every declared interior pixel, not samples or reviewer claims.

    Exclude known text/art/borders explicitly, never by color heuristics. The
    scope is the declared interiors, NOT automatically the entire figure.
    Without expected_rgba, componentwise minima define the lower end of each
    allowed channel interval; this tests uniformity, not color correctness.
    """
    geometry = {} if geometry is None else geometry
    if not isinstance(geometry, dict):
        raise ValueError("geometry must be an object")
    regions = geometry.get("flat_regions", [])
    if not isinstance(regions, list):
        raise ValueError("flat_regions must be an array")
    result = {"status": "NOT_RUN", "region_count": len(regions),
              "pixels_examined": 0, "regions": [],
              "coverage_scope": "Declared eligible interiors only; no automatic whole-figure coverage claim."}
    rgba = candidate.convert("RGBA")
    seen = set()
    for region in regions:
        if not isinstance(region, dict):
            raise ValueError("each flat region must be an object")
        identifier = region.get("id")
        if not isinstance(identifier, str) or not identifier.strip() or identifier in seen:
            raise ValueError("flat regions need distinct non-empty string ids")
        seen.add(identifier)
        bounds = bbox(region.get("bbox"), rgba.size)
        tolerance = region.get("max_channel_range", 0)
        if type(tolerance) is not int or not 0 <= tolerance <= 255:
            raise ValueError("max_channel_range must be an integer from 0 to 255")
        expected = region.get("expected_rgba")
        if expected is not None and (not isinstance(expected, list) or len(expected) != 4
                or any(type(v) is not int or not 0 <= v <= 255 for v in expected)):
            raise ValueError("expected_rgba needs four integer channels from 0 to 255")
        exclusions = region.get("exclude_boxes", [])
        if not isinstance(exclusions, list):
            raise ValueError("exclude_boxes must be an array")
        reason = region.get("exclusion_reason", "")
        if exclusions and (not isinstance(reason, str) or not reason.strip()):
            raise ValueError("text/art/border exclusions need an exclusion_reason")
        left, top, right, bottom = bounds
        crop = rgba.crop(tuple(bounds))
        mask = Image.new("L", crop.size, 255)
        draw = ImageDraw.Draw(mask)
        for exclusion in exclusions:
            a, b, c, d = bbox(exclusion, rgba.size)
            if not (left <= a < c <= right and top <= b < d <= bottom):
                raise ValueError("exclude_boxes must stay inside their flat region")
            draw.rectangle((a-left, b-top, c-left-1, d-top-1), fill=0)
        count = mask.histogram()[255]
        if count == 0:
            raise ValueError("flat region excludes every pixel")
        histograms = [band.histogram(mask=mask) for band in crop.split()]
        minima = [next(i for i, n in enumerate(histogram) if n) for histogram in histograms]
        maxima = [max(i for i, n in enumerate(histogram) if n) for histogram in histograms]
        baseline = expected if expected is not None else minima
        data, eligible = crop.load(), mask.load()
        examined = violations = 0
        maximum_delta = 0
        samples, violation_bounds = [], None
        for y in range(crop.height):
            for x in range(crop.width):
                if not eligible[x, y]:
                    continue
                examined += 1
                pixel = data[x, y]
                delta = max(abs(value - base) for value, base in zip(pixel, baseline))
                maximum_delta = max(maximum_delta, delta)
                if delta > tolerance:
                    violations += 1
                    px, py = left + x, top + y
                    if len(samples) < 16:
                        samples.append({"xy": [px, py], "rgba": list(pixel), "maximum_channel_deviation": delta})
                    if violation_bounds is None:
                        violation_bounds = [px, py, px+1, py+1]
                    else:
                        violation_bounds = [min(violation_bounds[0], px), min(violation_bounds[1], py),
                                            max(violation_bounds[2], px+1), max(violation_bounds[3], py+1)]
        result["pixels_examined"] += examined
        result["regions"].append({"id": identifier, "bbox": bounds,
            "exclude_boxes": exclusions, "exclusion_reason": reason,
            "pixels_examined": examined, "pixels_excluded": crop.width * crop.height - examined,
            "channel_minima": minima, "channel_maxima": maxima,
            "channel_ranges": [hi-lo for lo, hi in zip(minima, maxima)],
            "expected_rgba": expected, "comparison_baseline": baseline,
            "baseline_rule": "expected_rgba" if expected is not None else "per_channel_minimum",
            "max_channel_range": tolerance, "maximum_channel_deviation": maximum_delta,
            "violating_pixels": violations, "violation_bbox": violation_bounds,
            "first_violations": samples, "status": "FAIL" if violations else "PASS"})
    if regions:
        result["status"] = "FAIL" if any(row["status"] == "FAIL" for row in result["regions"]) else "PASS"
    return result


def compare(reference: Path, candidate: Path, output: Path, *, regions=None, geometry=None):
    output.mkdir(parents=True, exist_ok=True)
    with Image.open(reference) as im:
        ref_native = im.copy()
        ref = im.convert("RGB")
    with Image.open(candidate) as im:
        cand_native = im.copy()
        cand = im.convert("RGB")
    report = {
        "schema_version": 1, "reference_file": str(reference),
        "candidate_file": str(candidate), "reference_size": list(ref.size),
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
    report["geometry_findings"].extend(connector_findings(geometry, cand.size))
    report["geometry"] = geometry
    report["flat_fill_audit"] = flat_fill_metrics(cand_native, geometry)
    for region in report["flat_fill_audit"]["regions"]:
        if region["status"] == "FAIL":
            report["geometry_findings"].append({"type": "nonuniform_flat_fill", "id": region["id"],
                "channel_ranges": region["channel_ranges"], "violating_pixels": region["violating_pixels"],
                "violation_bbox": region["violation_bbox"]})
    (output / "pixel-audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--regions", type=Path)
    parser.add_argument("--geometry", type=Path)
    parser.add_argument("--require-flat-fills", action="store_true",
                        help="exit 2 when declared fill checks fail or were not run")
    args = parser.parse_args()
    load = lambda p: json.loads(p.read_text(encoding="utf-8")) if p else None
    report = compare(args.reference, args.candidate, args.output, regions=load(args.regions), geometry=load(args.geometry))
    print(json.dumps(report, ensure_ascii=False))
    if args.require_flat_fills and report["flat_fill_audit"]["status"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
