ExtDOM Item: INT.
ExtPred available: (Item).

[
    selected(X)? :- available(X).
    (\exists X. selected(X)).
]
