ExtDOM Index: INT.

[
    % Simple constraint 1: Existence
    \forall X. (\exists Y. p(X, Y)).
    
    % Simple constraint 2: Uniqueness
    \forall X, Y1, Y2. (\impl (\and p(X, Y1) p(X, Y2)) (= Y1 Y2)).
]
