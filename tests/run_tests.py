#!/usr/bin/env python3
"""Run the suite without requiring pytest."""
import sys, pathlib
root = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root)); sys.path.insert(0, str(root / "tests"))
import test_scorer as m

passed = failed = 0
for name in sorted(n for n in dir(m) if n.startswith("test_")):
    try:
        getattr(m, name)(); print(f"PASS  {name}"); passed += 1
    except Exception as e:
        print(f"FAIL  {name}: {e}"); failed += 1
print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
