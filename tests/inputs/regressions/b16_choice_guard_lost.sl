% B16: a choice with a guarded existence constraint and a uniqueness constraint is fused into one global 1{...}1, dropping the guard.
% Expected on b16_choice_guard_lost.lp: 8 models (one pick per constraint, 2^3); emitted: 6 (one pick in total).
ExtDOM C: INT.
ExtDOM K: INT.
ExtPred constr: (C).
ExtPred alt: (C, K).
[
    pick(X, Y)? :- alt(X, Y).
    \forall X. (\impl constr(X) (\exists Y. pick(X, Y))).
    \forall X, Y1, Y2. (\impl (\and pick(X, Y1) pick(X, Y2)) (= Y1 Y2)).
]
