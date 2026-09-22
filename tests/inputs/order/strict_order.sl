OrdDOM X: 0..15.
ExtDOM Q: INT.
Fun x: (Q) -> X.
ExtPred p: (Q, Q).
[
    \forall A, B, X1, X2. (\impl (\and p(A, B) x(A, X1) x(B, X2)) (< X1 X2)).
]
