ExtDOM U: INT.
ExtPred one: (U).

[
    k0(X)? :- dom_U(X).
    (\exists X. k0(X)).
    (\forall X, Y. (\impl (\and k0(X) k0(Y)) (= X Y))).
    k1(X)? :- dom_U(X).
    (\exists X. k1(X)).
    (\forall X, Y. (\impl (\and k1(X) k1(Y)) (= X Y))).
    k2(X)? :- dom_U(X).
    (\exists X. k2(X)).
    (\forall X, Y. (\impl (\and k2(X) k2(Y)) (= X Y))).
    k3(X)? :- dom_U(X).
    (\exists X. k3(X)).
    (\forall X, Y. (\impl (\and k3(X) k3(Y)) (= X Y))).
    k4(X)? :- dom_U(X).
    (\exists X. k4(X)).
    (\forall X, Y. (\impl (\and k4(X) k4(Y)) (= X Y))).
    k5(X)? :- dom_U(X).
    (\exists X. k5(X)).
    (\forall X, Y. (\impl (\and k5(X) k5(Y)) (= X Y))).
    k6(X)? :- dom_U(X).
    (\exists X. k6(X)).
    (\forall X, Y. (\impl (\and k6(X) k6(Y)) (= X Y))).
    k7(X)? :- dom_U(X).
    (\exists X. k7(X)).
    (\forall X, Y. (\impl (\and k7(X) k7(Y)) (= X Y))).
    k8(X)? :- dom_U(X).
    (\exists X. k8(X)).
    (\forall X, Y. (\impl (\and k8(X) k8(Y)) (= X Y))).
    p(X, Y)? :- dom_U(X), dom_U(Y).
    (\exists F0, F1, F2, F3, F4, F5, F6, F7, F8. (\and k0(F0) k1(F1) k2(F2) k3(F3) k4(F4) k5(F5) k6(F6) k7(F7) k8(F8) p(F0, F8))).
]
