ExtDOM U: INT.

[
    r(X, Y)? :- dom_U(X), dom_U(Y).
    p(X)? :- dom_U(X).
    k(X)? :- dom_U(X).
    (\exists X. k(X)).
    (\forall X, Y. (\impl (\and k(X) k(Y)) (= X Y))).
    (\forall X. (\impl k(X) (\exists Y. (\and dom_U(Y) r(X, Y) (\exists X. (\and dom_U(X) r(Y, X) (\neg p(X)))))))).
]
