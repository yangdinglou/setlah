ExtDOM U: INT.

[
    k(X)? :- dom_U(X).
    (\exists X. k(X)).
    (\forall X, Y. (\impl (\and k(X) k(Y)) (= X Y))).
    f(X, Y)? :- dom_U(X), dom_U(Y).
    g(X, Y)? :- dom_U(X), dom_U(Y).
    (\forall A, B, C. (\impl (\and k(A) f(A, B) g(B, C)) (= C A))).
]
