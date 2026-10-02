"""Remove one retired fueling claim from delivered road guides (Motoren AE-6.3).

Run once to write; --check verifies the published source tree afterward.
"""

from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "athletes"
OLD_ITEM = b"<li>Can even train fasted if under 90 minutes</li>"
NEW_ITEM = b"<li>Eat normally before easy rides; plan fueling for the ride's duration and your recovery needs.</li>"
OLD_RULE = b"<p><strong>The rule:</strong> Hard sessions need fuel. Easy sessions are flexible.</p>"
NEW_RULE = b"<p><strong>The rule:</strong> Fuel hard and easy sessions; adjust intake to the ride's duration and demands.</p>"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    files = sorted(ROOT.glob("*/index.html"))
    if not files:
        raise SystemExit("No delivered guide files found")
    changed = 0
    for path in files:
        original = path.read_bytes()
        old_count = original.count(OLD_ITEM)
        rule_count = original.count(OLD_RULE)
        if old_count not in (0, 1) or rule_count != old_count:
            raise SystemExit(f"Unexpected fueling block in {path}: {old_count=} {rule_count=}")
        if args.check:
            if old_count:
                raise SystemExit(f"Retired fasted advice remains in {path}")
            continue
        if old_count:
            updated = original.replace(OLD_ITEM, NEW_ITEM).replace(OLD_RULE, NEW_RULE)
            path.write_bytes(updated)
            changed += 1
    if args.check:
        remaining = [p for p in files if b"fasted" in p.read_bytes().lower()]
        if remaining:
            raise SystemExit(f"Fasted text remains in {len(remaining)} guides")
    print(f"guides={len(files)} changed={changed} check={args.check}")


if __name__ == "__main__":
    main()
