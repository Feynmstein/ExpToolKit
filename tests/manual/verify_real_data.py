#!/usr/bin/env python
"""手动验证脚本 — 用真实实验数据验证 IO 模块各 API。

用途：在修改 IO 模块后，手动运行此脚本确认与真实仪器输出兼容。
本脚本不随 pytest 自动运行（需真实数据文件存在于 data/ 目录中）。

用法:
    python tests/manual/verify_real_data.py
"""

from __future__ import annotations

from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_DATA = _REPO / "data"

_EXPERIMENTS = [
    {
        "file": "00747 - T1_ground, Q16.csv",
        "exp_id": "00747",
        "title": "T1_ground, Q16",
        "expected_shape": (21, 9),
        "n_independent": 1,
        "n_dependent": 8,
        "key_dep_categories": ["Q16 P0", "Q16 P1"],
        "verified_must_include": ["Q16"],
    },
    {
        "file": "00023 - spectro, Q07.csv",
        "exp_id": "00023",
        "title": "spectro, Q07",
        "expected_shape": (7371, 6),
        "n_independent": 2,
        "n_dependent": 4,
        "key_dep_categories": ["Q07 IQ Amp", "Q07 IQ phase", "Q07 I", "Q07 Q"],
        "verified_must_include": ["Q07"],
    },
    {
        "file": "00732 - spectro, Q15.csv",
        "exp_id": "00732",
        "title": "spectro, Q15",
        "expected_shape": (16441, 6),
        "n_independent": 2,
        "n_dependent": 4,
        "key_dep_categories": ["Q15 P0", "Q15 P1"],
        "verified_must_include": ["Q15"],
    },
]


def main() -> int:
    from exp_toolkit.io import (
        ColumnMeta,
        Experiment,
        IniMeta,
        ParamsSnapshot,
        load_experiment,
        load_parameters,
        parse_ini_metadata,
    )

    all_ok = True

    for exp_spec in _EXPERIMENTS:
        csv_path = _DATA / exp_spec["file"]
        if not csv_path.exists():
            print(f"[SKIP] {exp_spec['file']} — file not found")
            continue

        print(f"\n{'='*60}")
        print(f"Testing: {exp_spec['file']}")
        print(f"{'='*60}")

        # 1. load_experiment (主入口)
        exp = load_experiment(csv_path)
        checks = [
            ("exp_id", exp.exp_id == exp_spec["exp_id"]),
            ("title", exp.title == exp_spec["title"]),
            ("shape", exp.data.shape == exp_spec["expected_shape"]),
            ("n_independent", len(exp.independent_vars) == exp_spec["n_independent"]),
            ("n_dependent", len(exp.dependent_vars) == exp_spec["n_dependent"]),
            ("params not None", exp.params is not None),
        ]
        for name, ok in checks:
            status = "PASS" if ok else f"FAIL (expected different value)"
            if not ok:
                all_ok = False
            print(f"  [{status}] {name}")

        # 2. 列类别验证
        dep_cats = [c.category for c in exp.dependent_vars]
        for cat in exp_spec["key_dep_categories"]:
            ok = cat in dep_cats
            if not ok:
                all_ok = False
            print(f"  [{'PASS' if ok else 'FAIL'}] dep category '{cat}'")

        # 3. Verified qubits
        if exp.params:
            for qname in exp_spec["verified_must_include"]:
                has_q = qname in exp.params.qubits
                is_v = has_q and exp.params.qubits[qname].verified
                ok = has_q and is_v
                if not ok:
                    all_ok = False
                print(
                    f"  [{'PASS' if ok else 'FAIL'}] {qname} verified={is_v}"
                )

            # 4. P0 fix: extras 应包含非提取字段
            for qname, qp in exp.params.qubits.items():
                if qname in exp_spec["verified_must_include"]:
                    n_extras = len(qp.extras)
                    print(f"  [INFO] {qname} extras has {n_extras} keys")
                    break

        # 5. INI 底层 API
        ini_p = csv_path.with_suffix(".ini")
        meta = parse_ini_metadata(ini_p)
        assert isinstance(meta, IniMeta)
        print("  [PASS] parse_ini_metadata()")

        # 6. JSON 底层 API
        json_p = _DATA / f"{exp_spec['exp_id']} - parameters.json"
        if json_p.exists():
            params = load_parameters(json_p)
            assert isinstance(params, ParamsSnapshot)
            print(f"  [PASS] load_parameters() — {len(params.qubits)} qubits")

    if all_ok:
        print(f"\n{'='*60}")
        print("ALL CHECKS PASSED")
        print(f"{'='*60}")
        return 0
    else:
        print(f"\n{'='*60}")
        print("SOME CHECKS FAILED — see above")
        print(f"{'='*60}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
