ExtDOM Index: INT. % 1..N

[
    % ========================================================
    % Block 1: The Greek Square (Value A)
    % ========================================================

    % Rule: Guarded by domain predicates for safety
    greek(R, C, A)? :- dom_Index(R), dom_Index(C), dom_Index(A).

    % 1. One Value per Cell (merged existence + uniqueness)
    \forall R, C. (\and
        (\impl (\and dom_Index(R) dom_Index(C))
               (\exists A. greek(R, C, A)))
        (\forall A1, A2. (\impl (\and greek(R, C, A1) greek(R, C, A2)) (= A1 A2)))
    ).

    % 2. Latin Property: Unique in Row
    \forall R, A, C1, C2.
        (\impl (\and greek(R, C1, A) greek(R, C2, A))
               (= C1 C2)).

    % 3. Latin Property: Unique in Col
    \forall C, A, R1, R2.
        (\impl (\and greek(R1, C, A) greek(R2, C, A))
               (= R1 R2)).

    % 4. Symmetry Breaking: Fix first row/column
    \forall I.
        (\impl dom_Index(I)
               greek(1, I, I)).
    \forall I.
        (\impl dom_Index(I)
               greek(I, 1, I)).
]

[
    % ========================================================
    % Block 2: The Latin Square (Value B)
    % ========================================================

    latin(R, C, B)? :- dom_Index(R), dom_Index(C), dom_Index(B).

    % 1. One Value per Cell (merged existence + uniqueness)
    \forall R, C. (\and
        (\impl (\and dom_Index(R) dom_Index(C))
               (\exists B. latin(R, C, B)))
        (\forall B1, B2. (\impl (\and latin(R, C, B1) latin(R, C, B2)) (= B1 B2)))
    ).

    % 2. Latin Property: Unique in Row
    \forall R, B, C1, C2.
        (\impl (\and latin(R, C1, B) latin(R, C2, B)) (= C1 C2)).

    % 3. Latin Property: Unique in Col
    \forall C, B, R1, R2. (\impl (\and latin(R1, C, B) latin(R2, C, B)) (= R1 R2)).

    % 4. Symmetry Breaking: Fix first row
    \forall I. (\impl dom_Index(I) latin(1, I, I)).
]

[
    % ========================================================
    % Block 3: Orthogonality (Derived)
    % ========================================================

    % Definition: A pair (A,B) exists if it appears in some cell (R,C)
    product(A, B) :- greek(R, C, A), latin(R, C, B).

    % Constraint: Completeness
    \forall A, B.
        (\impl
            (\and dom_Index(A) dom_Index(B))
            product(A, B)
        ).
]
