% B16, third form: the choice is guarded by f(X) but the existence constraint quantifies over t(X); the fusion emits a global 1{...}1 with no head condition.
% Expected on b16_choice_guard_lost_2.lp: 9 models (one position per thread, 3^2); emitted: 6 (exactly one cut atom in total).
% B16, third occurrence: the choice is guarded by f(X), the existence constraint quantifies over t(X)
ExtDOM T: INT.
ExtDOM P: INT.
ExtPred t: (T).
ExtPred f: (T).
ExtPred pos: (P).

[
    cut(X, Q)? :- f(X), pos(Q).
    \forall X. (\impl t(X) (\exists Q. cut(X, Q))).
    \forall X, Q1, Q2. (\impl (\and cut(X, Q1) cut(X, Q2)) (= Q1 Q2)).
]
