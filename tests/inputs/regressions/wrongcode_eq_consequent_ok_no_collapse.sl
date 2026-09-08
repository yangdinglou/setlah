ExtDOM U: INT.

[
    k(X)? :- dom_U(X).
    f(X, Y)? :- dom_U(X), dom_U(Y).
    (\forall X. (\impl dom_U(X) (\exists Y. f(X, Y)))).
    g(X, Y)? :- dom_U(X), dom_U(Y).
    (\forall X. (\impl dom_U(X) (\exists Y. g(X, Y)))).
    (\forall A, B, C. (\impl (\and k(A) f(A, B) g(B, C)) (= C A))).
]
