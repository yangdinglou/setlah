ExtDOM U: INT.

[
    k(X)? :- dom_U(X).
    (\exists X. k(X)).
    (\forall X, Y. (\impl (\and k(X) k(Y)) (= X Y))).
    f(X, Y)? :- dom_U(X), dom_U(Y).
    (\forall X. (\impl dom_U(X) (\exists Y. f(X, Y)))).
    (\forall X, Y1, Y2. (\impl (\and f(X, Y1) f(X, Y2)) (= Y1 Y2))).
    g(X, Y)? :- dom_U(X), dom_U(Y).
    (\forall X. (\impl dom_U(X) (\exists Y. g(X, Y)))).
    (\forall X, Y1, Y2. (\impl (\and g(X, Y1) g(X, Y2)) (= Y1 Y2))).
    (\forall A, B, C. (\impl (\and k(A) f(A, B) g(B, C)) (= C A))).
]
