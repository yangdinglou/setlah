% The same comparison at two sites (under p and under q) shares one Boolean;
% the opposite comparison under r is its complement.
ExtDOM S: INT.
OrdDOM T: 0..9.
ExtPred p: (S, S).
ExtPred q: (S, S).
ExtPred r: (S, S).
Fun t: (S) -> T.
[
    \forall A, B, X, Y. (\impl (\and p(A, B) t(A, X) t(B, Y)) (< X Y)).
    \forall A, B, X, Y. (\impl (\and q(A, B) t(A, X) t(B, Y)) (< X Y)).
    \forall A, B, X, Y. (\impl (\and r(A, B) t(A, X) t(B, Y)) (>= X Y)).
]
