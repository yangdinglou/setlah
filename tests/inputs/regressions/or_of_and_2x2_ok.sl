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
    (\forall F918, F919, F920, F921. (\impl (\and dom_U(F918) dom_U(F919) dom_U(F920) dom_U(F921)) (\or (\and (= F919 F918) (= F921 F918)) (\and (= F919 F920) (= F921 F920))))).
]
