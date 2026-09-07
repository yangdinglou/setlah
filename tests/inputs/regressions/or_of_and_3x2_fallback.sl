ExtDOM U: INT.
ExtPred one: (U).

[
    k_s_e0(X)? :- dom_U(X).
    (\exists X. k_s_e0(X)).
    (\forall X, Y. (\impl (\and k_s_e0(X) k_s_e0(Y)) (= X Y))).
    k_s_e1(X)? :- dom_U(X).
    (\exists X. k_s_e1(X)).
    (\forall X, Y. (\impl (\and k_s_e1(X) k_s_e1(Y)) (= X Y))).
    k_s_e2(X)? :- dom_U(X).
    (\exists X. k_s_e2(X)).
    (\forall X, Y. (\impl (\and k_s_e2(X) k_s_e2(Y)) (= X Y))).
    k_s_e3(X)? :- dom_U(X).
    (\exists X. k_s_e3(X)).
    (\forall X, Y. (\impl (\and k_s_e3(X) k_s_e3(Y)) (= X Y))).
    k_s_unit(X)? :- dom_U(X).
    (\exists X. k_s_unit(X)).
    (\forall X, Y. (\impl (\and k_s_unit(X) k_s_unit(Y)) (= X Y))).
    f_s_inv(X0, Y)? :- dom_U(X0), dom_U(Y).
    (\forall X0. (\impl dom_U(X0) (\exists Y. f_s_inv(X0, Y)))).
    (\forall X0, Y1, Y2. (\impl (\and f_s_inv(X0, Y1) f_s_inv(X0, Y2)) (= Y1 Y2))).
    f_s_op(X0, X1, Y)? :- dom_U(X0), dom_U(X1), dom_U(Y).
    (\forall X0, X1. (\impl (\and dom_U(X0) dom_U(X1)) (\exists Y. f_s_op(X0, X1, Y)))).
    (\forall X0, X1, Y1, Y2. (\impl (\and f_s_op(X0, X1, Y1) f_s_op(X0, X1, Y2)) (= Y1 Y2))).
    (\forall F0, F1, F2, F3, F4. (\impl (\and dom_U(F0) dom_U(F1) dom_U(F2) dom_U(F3) dom_U(F4)) (\or (\and (= F3 F0) (= F4 F0)) (\and (= F3 F1) (= F4 F1)) (\and (= F3 F2) (= F4 F2))))).
]
