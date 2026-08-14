ExtDOM Index: INT.
ExtPred n_map: (Index, Index).

[
    % 1. Guess: Place queens on valid squares defined by n_map
    queen(R, C)? :- n_map(R, C).

    % Modified from FOL existence+uniqueness (4 lines) to #count:
    % (was: \forall R. \exists C. queen(R, C).
    %        \forall R, C1, C2. (\impl (\and queen(R, C1) queen(R, C2)) (= C1 C2)).)
    % 2. Row: exactly one queen per row
    \forall R. #count {Set_queen}(C) = 1.

    % Modified from FOL existence+uniqueness (4 lines) to #count:
    % (was: \forall C. \exists R. queen(R, C).
    %        \forall C, R1, R2. (\impl (\and queen(R1, C) queen(R2, C)) (= R1 R2)).)
    % 3. Column: exactly one queen per column
    \forall C. #count {Set_queen}(R) = 1.

    % 4. Diagonal Constraints (unchanged - arithmetic, no set operation applies)
    \forall R1, C1, R2, C2.
        (\impl
            (\and queen(R1, C1) queen(R2, C2) (!= R1 R2))
            (\and
                (!= (- R1 R2) (- C1 C2))
                (!= (- R1 R2) (- C2 C1))
            )
        ).
]
