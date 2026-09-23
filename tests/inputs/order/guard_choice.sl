% A comparison in a cube with a chosen predicate: the reified Boolean's guard
% takes the fact literals only (pair), never the choice (c), whose models would
% multiply the theory rules.
ExtDOM S: INT.
ExtDOM Q: INT.
OrdDOM T: 0..10.
ExtPred item: (S).
ExtPred pair: (S, S).
Fun t: (S) -> T.
[
    c(S, Qv)? :- item(S), dom_Q(Qv).
    \forall S1, S2, X1, X2, Q1, Q2. (\impl (\and pair(S1, S2) t(S1, X1) t(S2, X2) c(S1, Q1) c(S2, Q2)) (\or (< X1 X2) (!= Q1 Q2))).
]
