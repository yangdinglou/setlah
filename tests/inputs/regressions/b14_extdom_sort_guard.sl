% B14: auxiliary heads guarded by dom_<Sort> for an external sort -> UNSAT on a SAT program (direct lowering).
% Expected: SAT with v_t(2) on b14_extdom_sort_guard.lp.
ExtDOM D: INT.
ExtPred dom: (D).
ExtPred dom_any: (D).

[
    v_t(X)? :- dom(X).
    (\exists X. v_t(X)).
    (\forall X, Y. (\impl (\and v_t(X) v_t(Y)) (= X Y))).
    (\forall W1. (\impl v_t(W1) (= W1 2))).
    (\forall W3. (\impl dom_any(W3) (\impl (\forall W4. (\impl dom_any(W4) (\impl (= W4 5) (= W3 W4)))) (= W3 5)))).
]
