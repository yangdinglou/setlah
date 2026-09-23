% The comparison's variables are bound only by a chosen predicate: the Boolean
% takes domain guards, not the choice.
ExtDOM S: INT.
ExtDOM Q: INT.
OrdDOM T: 0..10.
ExtPred item: (S).
Fun t: (S) -> T.
[
    c(S, Qv)? :- item(S), dom_Q(Qv).
    \forall S1, S2, X1, X2, Qv. (\impl (\and c(S1, Qv) c(S2, Qv) t(S1, X1) t(S2, X2) (< S1 S2)) (< X1 X2)).
]
