% B12 reproducer (limits harness w_v6_c2): universally quantified variables that
% occur in no literal are put inside a #count aggregate as unbound element
% variables, so Clingo refuses to ground the program; exit 0.
% The direct lowering (--lowering direct) compiles it correctly.
ExtDOM D: INT.
ExtPred q0: (D, D).
ExtPred q1: (D, D).
ExtPred tgt: (D, D).

[
    pick(X0, X1, X2, X3, X4, X5)? :- dom_D(X0), dom_D(X1), dom_D(X2), dom_D(X3), dom_D(X4), dom_D(X5).
    \forall X0, X1, X2, X3, X4, X5. (\impl (\and q0(X0, X1) q1(X0, X1)) (\exists Z. (\and dom_D(Z) tgt(X0, X1)))).
]
