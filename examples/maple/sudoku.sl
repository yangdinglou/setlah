ExtDOM Index: INT. % Represents 1..9
ExtPred initial: (Index, Index, Index).

[
    % 1. Guess
    sudoku(R, C, V)? :- dom_Index(R), dom_Index(C), dom_Index(V).

    % 2. Respect initial hints
    \forall R, C, V. (\impl initial(R, C, V) sudoku(R, C, V)).

    % 3. One value per cell (merged existence + uniqueness)
    \forall R, C. (\and
        (\exists V. sudoku(R, C, V))
        (\forall V1, V2. (\impl (\and sudoku(R, C, V1) sudoku(R, C, V2)) (= V1 V2)))
    ).

    % 4. Row: all values in a row are distinct
    \forall R, V, C1, C2.
        (\impl (\and sudoku(R, C1, V) sudoku(R, C2, V))
               (= C1 C2)).

    % 5. Column: all values in a column are distinct
    \forall C, V, R1, R2.
        (\impl (\and sudoku(R1, C, V) sudoku(R2, C, V))
               (= R1 R2)).

    % 6. Subgrid (3x3): same value in same block implies same cell
    \forall R1, C1, R2, C2, V.
        (\impl
            (\and
                sudoku(R1, C1, V)
                sudoku(R2, C2, V)
                (= (/ (- R1 1) 3) (/ (- R2 1) 3))
                (= (/ (- C1 1) 3) (/ (- C2 1) 3))
            )
            (\and (= R1 R2) (= C1 C2))
        ).
]
