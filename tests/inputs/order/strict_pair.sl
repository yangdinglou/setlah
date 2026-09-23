% A strict order in both directions: the two comparisons share one Boolean up to
% the swap of its arguments and exclude each other.
ExtDOM S: INT.
OrdDOM T: 0..9.
ExtPred p: (S, S).
Fun t: (S) -> T.
[
    \forall A, B, X, Y. (\impl (\and p(A, B) t(A, X) t(B, Y)) (< X Y)).
]
