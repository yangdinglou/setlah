ExtDOM T: INT.
ExtPred n: (T, T).
ExtPred rw: (T, T).
[
    dl(X, 0, Y, 0) :- n(X, Y).
    dl(X, 1, Y, 0) :- n(X, Y).
    dl(X, 0, Y, 1) :- rw(X, Y).
    (\acyclic dl).
]
