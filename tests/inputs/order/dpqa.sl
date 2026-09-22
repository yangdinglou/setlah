% OLSQ-DPQA optimal-mode query with the coordinates as order sorts (docs/order-sorts.md)
ExtDOM Q: INT.
ExtDOM S: INT.
ExtDOM G: INT.
ExtDOM K: INT.
OrdDOM X: 0..15.
OrdDOM C: 0..15.
ExtPred qubit: (Q).
ExtPred stage: (S).
ExtPred rps: (K).
ExtPred gate: (G, Q, Q).
ExtPred coll: (G, G).
Fun x: (Q, S) -> X.
Fun y: (Q, S) -> X.
Fun c: (Q, S) -> C.
Fun r: (Q, S) -> C.

[
    next(S, S2) :- stage(S), stage(S2), (= S2 (+ S 1)).
    a(Q, S)? :- qubit(Q), stage(S).
    t(G, S)? :- gate(G, Q0, Q1), stage(S), (> S 0).
    \forall G, Q0, Q1. (\impl gate(G, Q0, Q1) (\exists S. t(G, S))).
    \forall G, S1, S2. (\impl (\and t(G, S1) t(G, S2)) (= S1 S2)).
    % SLM atoms keep their site
    \forall Q, S, S2, X1, X2. (\impl (\and qubit(Q) (\neg a(Q, S)) next(S, S2) x(Q, S, X1) x(Q, S2, X2)) (= X1 X2)).
    \forall Q, S, S2, Y1, Y2. (\impl (\and qubit(Q) (\neg a(Q, S)) next(S, S2) y(Q, S, Y1) y(Q, S2, Y2)) (= Y1 Y2)).
    % AOD atoms keep column and row while in the AOD
    \forall Q, S, S2, C1, C2. (\impl (\and a(Q, S) a(Q, S2) next(S, S2) c(Q, S, C1) c(Q, S2, C2)) (= C1 C2)).
    \forall Q, S, S2, R1, R2. (\impl (\and a(Q, S) a(Q, S2) next(S, S2) r(Q, S, R1) r(Q, S2, R2)) (= R1 R2)).
    % same column -> same site column next; column order -> site order next; far columns -> strictly apart next
    \forall Q0, Q1, S, S2, C1, C2, X1, X2. (\impl (\and a(Q0, S) a(Q1, S) (!= Q0 Q1) next(S, S2) c(Q0, S, C1) c(Q1, S, C2) (= C1 C2) x(Q0, S2, X1) x(Q1, S2, X2)) (= X1 X2)).
    \forall Q0, Q1, S, S2, R1, R2, Y1, Y2. (\impl (\and a(Q0, S) a(Q1, S) (!= Q0 Q1) next(S, S2) r(Q0, S, R1) r(Q1, S, R2) (= R1 R2) y(Q0, S2, Y1) y(Q1, S2, Y2)) (= Y1 Y2)).
    \forall Q0, Q1, S, S2, C1, C2, X1, X2. (\impl (\and a(Q0, S) a(Q1, S) (!= Q0 Q1) next(S, S2) c(Q0, S, C1) c(Q1, S, C2) (< C1 C2) x(Q0, S2, X1) x(Q1, S2, X2)) (<= X1 X2)).
    \forall Q0, Q1, S, S2, R1, R2, Y1, Y2. (\impl (\and a(Q0, S) a(Q1, S) (!= Q0 Q1) next(S, S2) r(Q0, S, R1) r(Q1, S, R2) (< R1 R2) y(Q0, S2, Y1) y(Q1, S2, Y2)) (<= Y1 Y2)).
    \forall Q0, Q1, S, S2, K, C1, C2, X1, X2. (\impl (\and a(Q0, S) a(Q1, S) (!= Q0 Q1) next(S, S2) rps(K) c(Q0, S, C1) c(Q1, S, C2) (> (- C1 C2) K) x(Q0, S2, X1) x(Q1, S2, X2)) (> X1 X2)).
    \forall Q0, Q1, S, S2, K, R1, R2, Y1, Y2. (\impl (\and a(Q0, S) a(Q1, S) (!= Q0 Q1) next(S, S2) rps(K) r(Q0, S, R1) r(Q1, S, R2) (> (- R1 R2) K) y(Q0, S2, Y1) y(Q1, S2, Y2)) (> Y1 Y2)).
    \forall Q0, Q1, K, C1, C2, X1, X2. (\impl (\and a(Q0, 0) a(Q1, 0) (!= Q0 Q1) rps(K) c(Q0, 0, C1) c(Q1, 0, C2) (> (- C1 C2) K) x(Q0, 0, X1) x(Q1, 0, X2)) (> X1 X2)).
    \forall Q0, Q1, K, R1, R2, Y1, Y2. (\impl (\and a(Q0, 0) a(Q1, 0) (!= Q0 Q1) rps(K) r(Q0, 0, R1) r(Q1, 0, R2) (> (- R1 R2) K) y(Q0, 0, Y1) y(Q1, 0, Y2)) (> Y1 Y2)).
    % site order gives strict column order among AOD atoms now
    \forall Q0, Q1, S, X1, X2, C1, C2. (\impl (\and a(Q0, S) a(Q1, S) (!= Q0 Q1) x(Q0, S, X1) x(Q1, S, X2) (< X1 X2) c(Q0, S, C1) c(Q1, S, C2)) (< C1 C2)).
    \forall Q0, Q1, S, Y1, Y2, R1, R2. (\impl (\and a(Q0, S) a(Q1, S) (!= Q0 Q1) y(Q0, S, Y1) y(Q1, S, Y2) (< Y1 Y2) r(Q0, S, R1) r(Q1, S, R2)) (< R1 R2)).
    % site crowding: two AOD atoms never share (column, row); two SLM atoms never share a site
    \forall Q0, Q1, S, C1, C2, R1, R2. (\impl (\and a(Q0, S) a(Q1, S) (< Q0 Q1) c(Q0, S, C1) c(Q1, S, C2) (= C1 C2) r(Q0, S, R1) r(Q1, S, R2)) (!= R1 R2)).
    \forall Q0, Q1, S, X1, X2, Y1, Y2. (\impl (\and qubit(Q0) qubit(Q1) stage(S) (< Q0 Q1) (\neg a(Q0, S)) (\neg a(Q1, S)) x(Q0, S, X1) x(Q1, S, X2) (= X1 X2) y(Q0, S, Y1) y(Q1, S, Y2)) (!= Y1 Y2)).
    % two atoms meeting at a site after stage 0: keep AOD membership, and a gate between them there
    meet(Q0, Q1, S) :- qubit(Q0), qubit(Q1), stage(S), (< Q0 Q1), (> S 0), x(Q0, S, X1), x(Q1, S, X2), (= X1 X2), y(Q0, S, Y1), y(Q1, S, Y2), (= Y1 Y2).
    \forall Q0, Q1, S, S0. (\impl (\and meet(Q0, Q1, S) next(S0, S)) (\and (\impl a(Q0, S) a(Q0, S0)) (\impl a(Q0, S0) a(Q0, S)) (\impl a(Q1, S) a(Q1, S0)) (\impl a(Q1, S0) a(Q1, S)))).
    gateat(Q0, Q1, S) :- gate(G, Q0, Q1), t(G, S).
    \forall Q0, Q1, S. (\impl meet(Q0, Q1, S) gateat(Q0, Q1, S)).
    % a scheduled gate has its qubits at one site; gates sharing a qubit are in different stages
    \forall G, S, Q0, Q1, X1, X2. (\impl (\and t(G, S) gate(G, Q0, Q1) x(Q0, S, X1) x(Q1, S, X2)) (= X1 X2)).
    \forall G, S, Q0, Q1, Y1, Y2. (\impl (\and t(G, S) gate(G, Q0, Q1) y(Q0, S, Y1) y(Q1, S, Y2)) (= Y1 Y2)).
    \forall G1, G2, S. (\neg (\and coll(G1, G2) t(G1, S) t(G2, S))).
]
