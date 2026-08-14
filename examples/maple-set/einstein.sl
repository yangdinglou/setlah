ExtDOM ID: INT.
ExtDOM Value: Symbol.

ExtPred is_house: (ID).
ExtPred is_color: (Value).
ExtPred is_nation: (Value).
ExtPred is_pet: (Value).
ExtPred is_drink: (Value).
ExtPred is_smoke: (Value).

[
    % ========================================================
    % Block 1: Color
    % ========================================================
    color(H, C)? :- is_house(H), is_color(C).

    % Modified from FOL existence+uniqueness+injectivity (3 constraints) to #count bijection:
    % (was: \forall H. \exists C. color(H, C).
    %        \forall H, C1, C2. (\impl (\and color(H, C1) color(H, C2)) (= C1 C2)).
    %        \forall H1, H2, C. (\impl (\and color(H1, C) color(H2, C)) (= H1 H2)).)
    \forall H. #count {Set_color}(C) = 1.
    \forall C. (\impl is_color(C) #count {Set_color}(H) = 1).

    % Clue 4 (unchanged - arithmetic adjacency)
    \exists H. (\and color(H, green) color((+ H 1), white)).
]

[
    % ========================================================
    % Block 2: Nation
    % ========================================================
    nation(H, N)? :- is_house(H), is_nation(N).

    % Modified from FOL existence+uniqueness+injectivity to #count bijection:
    % (was 3 FOL constraints)
    \forall H. #count {Set_nation}(N) = 1.
    \forall N. (\impl is_nation(N) #count {Set_nation}(H) = 1).

    % Clue 1 (unchanged)
    \forall H. (\impl nation(H, brit) color(H, red)).

    % Clue 9 (unchanged)
    (\neg (\neg nation(1, norwegian))).

    % Clue 14 (unchanged - existential with adjacency)
    \forall H1. (\impl nation(H1, norwegian)
        (\exists H2. (\and color(H2, blue)
            (\or (= H2 (+ H1 1)) (= H2 (- H1 1)))
        ))
    ).
]

[
    % ========================================================
    % Block 3: Pet
    % ========================================================
    pet(H, P)? :- is_house(H), is_pet(P).

    % Modified from FOL existence+uniqueness+injectivity to #count bijection:
    % (was 3 FOL constraints)
    \forall H. #count {Set_pet}(P) = 1.
    \forall P. (\impl is_pet(P) #count {Set_pet}(H) = 1).

    % Clue 2 (unchanged)
    \forall H. (\impl nation(H, swedish) pet(H, dog)).
]

[
    % ========================================================
    % Block 4: Drink
    % ========================================================
    drink(H, D)? :- is_house(H), is_drink(D).

    % Modified from FOL existence+uniqueness+injectivity to #count bijection:
    % (was 3 FOL constraints)
    \forall H. #count {Set_drink}(D) = 1.
    \forall D. (\impl is_drink(D) #count {Set_drink}(H) = 1).

    % Clue 3 (unchanged)
    \forall H. (\impl nation(H, dane) drink(H, tea)).

    % Clue 5 (unchanged)
    \forall H. (\impl color(H, green) drink(H, coffee)).

    % Clue 8 (unchanged)
    drink(3, milk).
]

[
    % ========================================================
    % Block 5: Smoke
    % ========================================================
    smoke(H, S)? :- is_house(H), is_smoke(S).

    % Modified from FOL existence+uniqueness+injectivity to #count bijection:
    % (was 3 FOL constraints)
    \forall H. #count {Set_smoke}(S) = 1.
    \forall S. (\impl is_smoke(S) #count {Set_smoke}(H) = 1).

    % Clue 6 (unchanged)
    \forall H. (\impl smoke(H, pallmall) pet(H, bird)).

    % Clue 7 (unchanged)
    \forall H. (\impl color(H, yellow) smoke(H, dunhill)).

    % Clue 10 (unchanged - existential with adjacency)
    \forall H1. (\impl smoke(H1, blends)
        (\exists H2. (\and pet(H2, cat)
            (\or (= H2 (+ H1 1)) (= H2 (- H1 1)))
        ))
    ).

    % Clue 11 (unchanged - existential with adjacency)
    \forall H1. (\impl pet(H1, horse)
        (\exists H2. (\and smoke(H2, dunhill)
            (\or (= H2 (+ H1 1)) (= H2 (- H1 1)))
        ))
    ).

    % Clue 12 (unchanged)
    \forall H. (\impl smoke(H, bluemaster) drink(H, beer)).

    % Clue 13 (unchanged)
    \forall H. (\impl nation(H, german) smoke(H, prince)).

    % Clue 15 (unchanged - existential with adjacency)
    \forall H1. (\impl smoke(H1, blends)
        (\exists H2. (\and drink(H2, water)
            (\or (= H2 (+ H1 1)) (= H2 (- H1 1)))
        ))
    ).
]
