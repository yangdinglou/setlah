ExtDOM Index: INT.
ExtPred n_map: (Index, Index).

[
    % 1. Guess
    queen(R, C)? :- n_map(R, C).

    % 2. Row: exactly one queen per row (merged existence + uniqueness)
    \forall R. (\and
        (\exists C. queen(R, C))
        (\forall C1, C2. (\impl (\and queen(R, C1) queen(R, C2)) (= C1 C2)))
    ).

    % 3. Column: exactly one queen per column (merged existence + uniqueness)
    \forall C. (\and
        (\exists R. queen(R, C))
        (\forall R1, R2. (\impl (\and queen(R1, C) queen(R2, C)) (= R1 R2)))
    ).

    % 4. Diagonal: no two queens share a diagonal
    \forall R1, C1, R2, C2.
        (\impl
            (\and queen(R1, C1) queen(R2, C2) (!= R1 R2))
            (\and
                (!= (- R1 R2) (- C1 C2))
                (!= (- R1 R2) (- C2 C1))
            )
        ).
]
