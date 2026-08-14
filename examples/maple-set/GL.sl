ExtDOM Index: INT. % 1..N

[
    % ========================================================
    % Block 1: The Greek Square (Value A)
    % ========================================================

    greek(R, C, A)? :- dom_Index(R), dom_Index(C), dom_Index(A).

    % Modified from FOL existence+uniqueness (4 lines) to #count:
    % (was: \forall R, C. (\impl (\and dom_Index(R) dom_Index(C)) (\exists A. greek(R, C, A))).
    %        \forall R, C, A1, A2. (\impl (\and greek(R, C, A1) greek(R, C, A2)) (= A1 A2)).)
    % 1. One Value per Cell
    \forall R, C. (\impl (\and dom_Index(R) dom_Index(C))
                         #count {Set_greek}(A) = 1).

    % Modified from FOL injectivity (3 lines) to #count:
    % (was: \forall R, A, C1, C2. (\impl (\and greek(R, C1, A) greek(R, C2, A)) (= C1 C2)).)
    % 2. Latin Property: Unique in Row
    \forall R, A. #count {Set_greek}(C) = 1.

    % Modified from FOL injectivity (3 lines) to #count:
    % (was: \forall C, A, R1, R2. (\impl (\and greek(R1, C, A) greek(R2, C, A)) (= R1 R2)).)
    % 3. Latin Property: Unique in Col
    \forall C, A. #count {Set_greek}(R) = 1.

    % 4. Symmetry Breaking (unchanged)
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

    % Modified from FOL existence+uniqueness (4 lines) to #count:
    % (was: \forall R, C. (\impl ...) + uniqueness)
    % 1. One Value per Cell
    \forall R, C. (\impl (\and dom_Index(R) dom_Index(C))
                         #count {Set_latin}(B) = 1).

    % Modified from FOL injectivity to #count:
    % 2. Latin Property: Unique in Row
    \forall R, B. #count {Set_latin}(C) = 1.

    % Modified from FOL injectivity to #count:
    % 3. Latin Property: Unique in Col
    \forall C, B. #count {Set_latin}(R) = 1.

    % 4. Symmetry Breaking (unchanged)
    \forall I. (\impl dom_Index(I) latin(1, I, I)).
]

[
    % ========================================================
    % Block 3: Orthogonality (unchanged - derived predicate + universal implication)
    % ========================================================

    product(A, B) :- greek(R, C, A), latin(R, C, B).

    \forall A, B.
        (\impl
            (\and dom_Index(A) dom_Index(B))
            product(A, B)
        ).
]
