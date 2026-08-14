ExtDOM Index: INT. % Represents 1..9
ExtPred initial: (Index, Index, Index).

[
    % 1. Guess: Assign a value V to cell (R, C).
    sudoku(R, C, V)? :- dom_Index(R), dom_Index(C), dom_Index(V).

    % 2. Respect Initial Hints (unchanged)
    \forall R, C, V. (\impl initial(R, C, V) sudoku(R, C, V)).

    % Modified from FOL existence+uniqueness (4 lines) to #count:
    % (was: \forall R, C. \exists V. sudoku(R, C, V).
    %        \forall R, C, V1, V2. (\impl (\and sudoku(R, C, V1) sudoku(R, C, V2)) (= V1 V2)).)
    % 3. One Value per Cell
    \forall R, C. #count {Set_sudoku}(V) = 1.

    % Modified from FOL injectivity (3 lines) to #count:
    % (was: \forall R, V, C1, C2. (\impl (\and sudoku(R, C1, V) sudoku(R, C2, V)) (= C1 C2)).)
    % 4. Row: each value appears exactly once per row
    \forall R, V. #count {Set_sudoku}(C) = 1.

    % Modified from FOL injectivity (3 lines) to #count:
    % (was: \forall C, V, R1, R2. (\impl (\and sudoku(R1, C, V) sudoku(R2, C, V)) (= R1 R2)).)
    % 5. Column: each value appears exactly once per column
    \forall C, V. #count {Set_sudoku}(R) = 1.

    % 6. Subgrid (unchanged - arithmetic grouping condition, no set operation applies)
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
