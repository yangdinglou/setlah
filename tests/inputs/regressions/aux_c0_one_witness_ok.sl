ExtDOM N: INT.
ExtDOM R: INT.
[
    k(X)? :- dom_N(X).
    p(X)? :- dom_N(X).
    q(X, Y)? :- dom_N(X), dom_R(Y).
    (\forall K. (\impl k(K) (\neg (\impl p(K) (\exists Y. (\and dom_R(Y) q(K, Y))))))).
]
