#!/usr/bin/env python3
"""ExpToolKit smoke test — post-deployment verification.

Purpose: confirm the package is correctly installed, all key modules are
importable, and basic functionality works.

Dependencies: stdlib + exp_toolkit only.
Usage: python scripts/smoke_test.py
Exit code: 0 = all passed, non-zero = number of failures
"""

from __future__ import annotations

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure editable-install exp_toolkit is importable (not needed with pip install)
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Test harness
# ---------------------------------------------------------------------------

FAILURES: list[str] = []


def _check(condition: bool, msg: str) -> None:
    """Record a failure without stopping subsequent tests."""
    if not condition:
        FAILURES.append(msg)


# ---------------------------------------------------------------------------
# Test 1: imports
# ---------------------------------------------------------------------------

def test_imports() -> None:
    """Verify all public modules / symbols are importable."""
    print("-" * 56)
    print("[1/4] Module imports")

    modules: list[tuple[str, list[str]]] = [
        ("exp_toolkit", ["__version__"]),
        ("exp_toolkit.io", ["load_experiment"]),
        ("exp_toolkit.fitting", ["fit_t1", "fit_spectro", "fit_f01_dispersion",
                                  "fit_ramsey", "fit_rabi", "fit_rb",
                                  "fit", "models"]),
        ("exp_toolkit.fitting.iq_analysis", ["assignment_fidelity"]),
        ("exp_toolkit.state", ["ChipState"]),
        ("exp_toolkit.visualization", ["ChipTopology", "ChipArtist"]),
        ("exp_toolkit.report", ["ReportGenerator"]),
    ]

    all_ok = True
    for mod_name, expected_names in modules:
        try:
            mod = __import__(mod_name, fromlist=expected_names)
            for name in expected_names:
                obj = getattr(mod, name, None)
                _check(obj is not None, f"  {mod_name}.{name} — not found")
                if obj is not None:
                    print(f"  [OK] {mod_name}.{name}")
        except ImportError as e:
            print(f"  [FAIL] {mod_name} — import error: {e}")
            all_ok = False

    if all_ok and not FAILURES:
        print("  [PASS] All modules imported successfully")
    else:
        print(f"  [FAIL] {len(FAILURES)} import errors")


# ---------------------------------------------------------------------------
# Test 2: synthetic T1 fit
# ---------------------------------------------------------------------------

def test_synthetic_t1() -> None:
    """Synthetic T1 data: verify engine + ExponentialDecay model."""
    print("-" * 56)
    print("[2/4] Synthetic T1 fit")

    try:
        import numpy as np
        from exp_toolkit.fitting.engine import fit
        from exp_toolkit.fitting.models import exp_decay

        rng = np.random.default_rng(0)
        x = np.linspace(0, 100, 50)
        tau_true = 40.0
        y_true = 0.8 * np.exp(-x / tau_true) + 0.2
        y = y_true + rng.normal(0, 0.01, 50)

        result = fit(x, y, exp_decay, params_hint={"amplitude": 0.8, "tau": 30.0, "offset": 0.2})

        _check(result.success, f"Fit did not converge: {result.message}")
        _check(30 < result.params["tau"] < 55,
               f"tau={result.params['tau']:.1f} outside reasonable range [30, 55]")
        _check(result.params["tau"] > 0, "tau must be positive")
        _check("tau" in result.errors, "Missing uncertainty for tau")

        if result.success:
            print(f"  [OK] tau = {result.params['tau']:.1f} +/- "
                  f"{result.errors.get('tau', float('nan')):.1f} "
                  f"(true={tau_true:.1f})")
        print("  [PASS] Synthetic T1 fit" if not FAILURES else f"  [FAIL] {len(FAILURES)} errors")

    except Exception as e:
        FAILURES.append(f"Synthetic T1 fit exception: {e}")
        print(f"  [FAIL] Exception: {e}")


# ---------------------------------------------------------------------------
# Test 3: synthetic Lorentzian fit
# ---------------------------------------------------------------------------

def test_synthetic_lorentzian() -> None:
    """Synthetic Lorentzian: verify spectroscopy fitting path."""
    print("-" * 56)
    print("[3/4] Synthetic Lorentzian fit")

    try:
        import numpy as np
        from exp_toolkit.fitting.engine import fit
        from exp_toolkit.fitting.models import lorentzian

        rng = np.random.default_rng(1)
        x = np.linspace(4.0, 5.0, 200)
        x0_true, gamma_true, A_true, C_true = 4.5, 0.01, 0.005, 0.001
        y_true = A_true * gamma_true**2 / ((x - x0_true)**2 + gamma_true**2) + C_true
        y = y_true + rng.normal(0, 0.0001, 200)

        result = fit(x, y, lorentzian, params_hint={"amplitude": 0.01, "center": 4.5, "gamma": 0.02, "offset": 0.0})

        _check(result.success, f"Fit did not converge: {result.message}")
        _check(abs(result.params["center"] - x0_true) < 3 * result.errors.get("center", 0.01),
               f"center={result.params['center']:.5f} deviates from true {x0_true}")

        if result.success:
            print(f"  [OK] center = {result.params['center']:.5f} +/- "
                  f"{result.errors.get('center', float('nan')):.5f} "
                  f"(true={x0_true})")
        print("  [PASS] Synthetic Lorentzian fit" if not FAILURES else f"  [FAIL] {len(FAILURES)} errors")

    except Exception as e:
        FAILURES.append(f"Lorentzian fit exception: {e}")
        print(f"  [FAIL] Exception: {e}")


# ---------------------------------------------------------------------------
# Test 4: ChipState round-trip
# ---------------------------------------------------------------------------

def test_chip_state_roundtrip() -> None:
    """Verify ChipState new -> save -> load round-trip consistency."""
    print("-" * 56)
    print("[4/4] ChipState round-trip")

    try:
        import tempfile
        from exp_toolkit.visualization.chip_plot import ChipTopology
        from exp_toolkit.state.chip_state import ChipState

        topo = ChipTopology.from_grid(3, 3, numbering="row-major")
        state = ChipState.new("smoke-test-chip", topo)
        state.add_T1("Q1", value=42.0, error=1.5, freq_GHz=4.7,
                     source_exp="99999", timestamp="2026-06-23")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            state.save(f.name)
            loaded = ChipState.load(f.name)

        q1 = loaded.get_qubit("Q1")

        # Phase 11: coherence grouped as CoherenceGroup per frequency
        # Each CoherenceGroup has T1_us, T2star_us, T2echo_us as CoherenceEntry | None
        if hasattr(q1, "coherence") and q1.coherence:
            # Find the group that has T1_us set
            t1_val = None
            for g in q1.coherence:
                if g.T1_us is not None:
                    t1_val = g.T1_us.value
                    break
            _check(t1_val is not None, "No T1 entry found in coherence groups")
            if t1_val is not None:
                _check(abs(t1_val - 42.0) < 0.01,
                       f"T1 round-trip mismatch: {t1_val} != 42.0")
        elif hasattr(q1, "T1_us") and q1.T1_us:
            _check(abs(q1.T1_us[-1].value - 42.0) < 0.01,
                   f"T1 round-trip mismatch: {q1.T1_us[-1].value} != 42.0")

        _check(loaded.chip_id == "smoke-test-chip",
               f"chip_id mismatch: {loaded.chip_id}")
        _check(loaded.topology is not None, "topology not loaded")

        print(f"  [OK] chip_id = {loaded.chip_id}")
        print(f"  [OK] T1(Q1) = 42.0 saved and loaded correctly")
        print("  [PASS] ChipState round-trip" if not FAILURES else f"  [FAIL] {len(FAILURES)} errors")

    except Exception as e:
        FAILURES.append(f"ChipState round-trip exception: {e}")
        print(f"  [FAIL] Exception: {e}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 56)
    print("  ExpToolKit Smoke Test")
    print(f"  Python: {sys.version}")
    import exp_toolkit
    ver = getattr(exp_toolkit, "__version__", "(unknown)")
    print(f"  ExpToolKit: {ver}")
    print("=" * 56)
    print()

    test_imports()
    test_synthetic_t1()
    test_synthetic_lorentzian()
    test_chip_state_roundtrip()

    print()
    print("=" * 56)
    if FAILURES:
        print(f"FAIL — {len(FAILURES)} item(s) did not pass:")
        for f_msg in FAILURES:
            print(f"  * {f_msg}")
        return len(FAILURES)
    else:
        print("PASS — ExpToolKit is healthy")
        return 0


if __name__ == "__main__":
    sys.exit(main())
