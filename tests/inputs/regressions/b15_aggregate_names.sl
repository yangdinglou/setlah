% B15: aggregate variables that do not reuse the defining rule's names -> unsafe aggregate element, exit 0.
% Expected: 6 models on b15_aggregate_names.lp (same as with `\forall A. #count {Set_nxt}(B) <= 1.`).
ExtDOM N: INT.
ExtPred cand: (N, N).
[
    nxt(A, B)? :- cand(A, B).
    \forall X. #count {Set_nxt}(Y) <= 1.
]
