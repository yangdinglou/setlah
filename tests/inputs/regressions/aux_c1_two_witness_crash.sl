ExtDOM N: INT.
ExtDOM R: INT.
ExtDOM P: INT.
[
    kn(X)? :- dom_N(X).
    kp(X)? :- dom_P(X).
    rr(X, Y)? :- dom_N(X), dom_P(Y).
    rs(X, Y)? :- dom_N(X), dom_R(Y).
    mt(X, Y)? :- dom_R(X), dom_P(Y).
    (\forall KN, KP. (\impl (\and kn(KN) kp(KP)) (\neg (\impl rr(KN, KP) (\exists Y. (\and dom_R(Y) (\and rs(KN, Y) mt(Y, KP)))))))).
]
