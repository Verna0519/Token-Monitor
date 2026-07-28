#!/usr/bin/env python3
"""Structure check for a capability-coordinate upload (called by check-visibility-seam.sh (b)).

A coordinate carries EXACTLY {format, version, submission_id, period, position} — nothing else:
no evidence text, no identity fields, no extra keys. The shape check IS the coordinate-equivalent
of the old digest flags (operator ruling 2026-07-15: "回頭對其契約改個人層"). Axes come from the
single source config/extraction.schema.json (domain_signals.required). Exit 1 + message on any
violation; exit 0 when clean.
"""

import json
import os
import sys


def fail(msg):
    print(msg)
    sys.exit(1)


def main():
    if len(sys.argv) != 2:
        fail("usage: _check_coordinate_shape.py <coordinate.json>")
    path = sys.argv[1]
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "config", "extraction.schema.json"), encoding="utf-8") as fh:
        schema = json.load(fh)
    axes = schema["properties"]["domain_signals"]["required"]

    try:
        with open(path, encoding="utf-8") as fh:
            obj = json.load(fh)
    except Exception as e:  # noqa: BLE001
        fail(f"not valid JSON: {e}")
    if not isinstance(obj, dict):
        fail("not a JSON object")

    expected = {"format", "version", "submission_id", "period", "position"}
    keys = set(obj.keys())
    if keys != expected:
        extra = sorted(keys - expected)
        missing = sorted(expected - keys)
        fail(f"key set must be exactly {sorted(expected)} — extra {extra}, missing {missing}")
    if obj["format"] != "capability-coordinate":
        fail(f"format must be 'capability-coordinate', got {obj['format']!r}")
    if obj["version"] != "0.1":
        fail(f"version must be '0.1' (strict contract — operator ruling 2026-07-15: unplaceable "
             f"axes mean collect more evidence, not a looser contract), got {obj['version']!r}")
    sid = obj["submission_id"]
    if not isinstance(sid, str) or not sid.startswith("sub-") or len(sid) < 8:
        fail(f"submission_id must be an opaque 'sub-...' string, got {sid!r}")
    pos = obj["position"]
    if not isinstance(pos, dict) or set(pos.keys()) != set(axes):
        fail(f"position must carry exactly the {len(axes)} axes {sorted(axes)}")
    for a in axes:
        v = pos[a]
        if not isinstance(v, int) or isinstance(v, bool) or not (0 <= v <= 3):
            fail(f"axis '{a}': level must be an int in [0,3], got {v!r} (no nullable levels)")
    sys.exit(0)


if __name__ == "__main__":
    main()
