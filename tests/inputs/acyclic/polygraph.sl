ExtDOM C: INT.
ExtDOM K: INT.
ExtDOM N: INT.
ExtPred constr: (C).
ExtPred alt: (C, K, N, N).
ExtPred fixed: (N, N).
[
    pick(X, Y)? :- constr(X), alt(X, Y, A, B).
    \forall X. (\impl constr(X) (\exists Y. pick(X, Y))).
    edge(A, B) :- fixed(A, B).
    edge(A, B) :- pick(C, K), alt(C, K, A, B).
    (\acyclic edge).
]
