#!/usr/bin/env python3
"""Repair and audit the race-vitals block in selected Roadie Labs guides.

The affected guide ladders were generated with either a stale generic
60.3-mile / 4,587-foot block or a missing elevation row.  This script keeps
the correction reproducible and fails if a ladder is incomplete.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ATHLETES = ROOT / "athletes"

SPECS = {
    "gfny-nyc": {
        "distance": "85",
        "elevation": "6,370",
        "source": "https://nyc.gfny.com/wp-content/uploads/sites/8/2026/05/GFNY26-Race-Guide-EN.pdf",
        "replacements": {"85.1mi": "85mi", "85.1 miles": "85 miles"},
    },
    "letape-norway": {
        "distance": "80.8",
        "elevation": "5,151",
        "source": "https://trondheim.letapeseries.com/",
    },
    "letape-cancun": {
        "distance": "63.1",
        "elevation": "436",
        "source": "https://cancun.letapeseries.com/stages",
    },
    "etape-caledonia": {
        "distance": "85",
        "elevation": "5,101",
        "source": "https://www.etapecaledonia.com/",
    },
    "tour-de-big-bear": {
        "distance": "100",
        "elevation": "8,585",
        "source": "https://tourdebigbear.com/road/",
    },
    "arlberg-giro": {
        "distance": "93",
        "elevation": "8,202",
        "source": "https://arlberg-giro.com/en/home",
    },
    "letape-argentina": {
        "distance": "83",
        "elevation": "5,840",
        "source": "https://argentina.letapeseries.com/",
    },
    "levis-granfondo": {
        "distance": "138",
        "elevation": "14,000",
        "source": "https://www.levisgranfondo.com/guide",
    },
    "styrkeproven": {
        "distance": "320",
        "elevation": "13,845",
        "source": "https://styrkeproven.no/main-page/trondheim-oslo/?lang=en",
    },
    "gran-fondo-florida": {
        "distance": "101.08",
        "elevation": "3,409",
        "source": "https://ridewithgps.com/routes/6205144",
    },
    "highlands-gran-fondo": {
        "distance": "103.5",
        "elevation": "7,535",
        "source": "https://ridewithgps.com/routes/11738715",
    },
    "gfny-jose-ignacio": {
        "distance": "80.5",
        "elevation": "3,130",
        "source": "https://gfny.com/gfny-announces-jose-ignacio-race-on-uruguays-atlantic-coast/",
    },
}

META_RE = re.compile(
    r'(?P<open><div class="guide-meta">\n)(?P<body>.*?)(?P<close>\n\s*</div>)',
    re.DOTALL,
)
DISTANCE_RE = re.compile(
    r'^(?P<indent>\s*)<span>[\d,.]+ miles</span>$', re.MULTILINE
)
ELEVATION_RE = re.compile(
    r'^(?P<indent>\s*)<span>[\d,]+ ft</span>$', re.MULTILINE
)


def guide_paths(slug: str) -> list[Path]:
    return sorted(ATHLETES.glob(f"{slug}-*/index.html"))


def expected_spans(spec: dict[str, object]) -> tuple[str, str]:
    return (
        f'<span>{spec["distance"]} miles</span>',
        f'<span>{spec["elevation"]} ft</span>',
    )


def repair(text: str, spec: dict[str, object]) -> str:
    for old, new in spec.get("replacements", {}).items():
        text = text.replace(old, new)

    match = META_RE.search(text)
    if not match:
        raise ValueError("missing guide-meta block")

    body = match.group("body")
    distance_span, elevation_span = expected_spans(spec)
    distance_match = DISTANCE_RE.search(body)
    if not distance_match:
        raise ValueError("missing distance span in guide-meta block")

    indent = distance_match.group("indent")
    body = DISTANCE_RE.sub(f"{indent}{distance_span}", body, count=1)
    elevation_match = ELEVATION_RE.search(body)
    if elevation_match:
        elevation_indent = elevation_match.group("indent")
        body = ELEVATION_RE.sub(
            f"{elevation_indent}{elevation_span}", body, count=1
        )
    else:
        body = body.replace(
            f"{indent}{distance_span}",
            f"{indent}{distance_span}\n{indent}{elevation_span}",
            1,
        )

    return text[: match.start("body")] + body + text[match.end("body") :]


def audit_file(path: Path, spec: dict[str, object]) -> list[str]:
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    match = META_RE.search(text)
    if not match:
        return ["missing guide-meta block"]

    body = match.group("body")
    distance_span, elevation_span = expected_spans(spec)
    if body.count(distance_span) != 1:
        errors.append(f"expected one {distance_span!r} in guide-meta")
    if body.count(elevation_span) != 1:
        errors.append(f"expected one {elevation_span!r} in guide-meta")
    if "60.3 miles" in body or "4,587 ft" in body:
        errors.append("stale generic vitals remain in guide-meta")
    for old in spec.get("replacements", {}):
        if old in text:
            errors.append(f"stale value remains: {old!r}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()

    changed: list[str] = []
    failures: dict[str, list[str]] = {}
    files: list[dict[str, object]] = []

    for slug, spec in SPECS.items():
        paths = guide_paths(slug)
        if len(paths) != 7:
            failures[slug] = [f"expected 7 guides, found {len(paths)}"]
            continue

        for path in paths:
            before = path.read_text(encoding="utf-8")
            if args.apply:
                try:
                    after = repair(before, spec)
                except ValueError as exc:
                    failures[str(path.relative_to(ROOT))] = [str(exc)]
                    continue
                if after != before:
                    path.write_text(after, encoding="utf-8")
                    changed.append(str(path.relative_to(ROOT)))

            errors = audit_file(path, spec)
            if errors:
                failures[str(path.relative_to(ROOT))] = errors
            else:
                data = path.read_bytes()
                files.append(
                    {
                        "path": str(path.relative_to(ROOT)),
                        "sha256": hashlib.sha256(data).hexdigest(),
                    }
                )

    receipt = {
        "status": "passed" if not failures else "failed",
        "race_count": len(SPECS),
        "expected_guide_count": len(SPECS) * 7,
        "verified_guide_count": len(files),
        "changed_guide_count": len(changed),
        "changed": changed,
        "sources": {slug: spec["source"] for slug, spec in SPECS.items()},
        "files": files,
        "failures": failures,
    }
    print(json.dumps(receipt, indent=2, ensure_ascii=False))

    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(
            json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
