from setlah.transpile.safety import _infer_safety_guards


def test_arithmetic_comparison_propagates_domain_guards():
    guards = _infer_safety_guards(
        ["queen(R1, C1)", "not (R1 - R2) != (C1 - C2)"],
        pred_arg_types={"queen": ("Index", "Index")},
    )

    assert guards == ["dom_Index(C2)", "dom_Index(R2)"]
