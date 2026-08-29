from setlah import Program, SolveStatus, string


CHOICE = r"""
ExtDOM Item: INT.
ExtPred available: (Item).
[
    selected(X)? :- available(X).
    (\exists X. selected(X)).
]
"""


def main() -> None:
    instance = (
        Program(CHOICE)
        .instance()
        .add_raw_facts("dom_Item(1..3).")
        .add_fact("available", 1)
        .add_fact("available", 2)
        .add_fact("available", 3)
        .add_fact("label", 1, string("first"))
    )
    result = instance.solve()

    if result.status is not SolveStatus.SATISFIABLE:
        raise RuntimeError(f"expected SAT, got {result.status.value}")

    for selected in result.models[0].atoms_named("selected"):
        print(selected.render())


if __name__ == "__main__":
    main()
