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

    % Bijectivity: color is a bijection between houses and colors
    % (merged totality + functionality + injectivity)
        (\forall H. (\and
            (\exists C. color(H, C))
            (\forall C1, C2. (\impl (\and color(H, C1) color(H, C2)) (= C1 C2))))).
        (\forall H1, H2, C. (\impl (\and color(H1, C) color(H2, C)) (= H1 H2))).

    % Clue 4: The green house is on the left of the white house.
    \exists H. (\and color(H, green) color((+ H 1), white)).
]

[
    % ========================================================
    % Block 2: Nation
    % ========================================================
    nation(H, N)? :- is_house(H), is_nation(N).

    % Bijectivity (merged)
        (\forall H. (\and
            (\exists N. nation(H, N))
            (\forall N1, N2. (\impl (\and nation(H, N1) nation(H, N2)) (= N1 N2))))).
        (\forall H1, H2, N. (\impl (\and nation(H1, N) nation(H2, N)) (= H1 H2))).

    % Clue 1: The Brit lives in the red house.
    \forall H. (\impl nation(H, brit) color(H, red)).

    % Clue 9: The Norwegian lives in the first house.
    (\neg (\neg nation(1, norwegian))).

    % Clue 14: The Norwegian lives next to the blue house.
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

    % Bijectivity (merged)
        (\forall H. (\and
            (\exists P. pet(H, P))
            (\forall P1, P2. (\impl (\and pet(H, P1) pet(H, P2)) (= P1 P2))))).
        (\forall H1, H2, P. (\impl (\and pet(H1, P) pet(H2, P)) (= H1 H2))).

    % Clue 2: The Swede keeps dogs as pets.
    \forall H. (\impl nation(H, swedish) pet(H, dog)).
]

[
    % ========================================================
    % Block 4: Drink
    % ========================================================
    drink(H, D)? :- is_house(H), is_drink(D).

    % Bijectivity (merged)
        (\forall H. (\and
            (\exists D. drink(H, D))
            (\forall D1, D2. (\impl (\and drink(H, D1) drink(H, D2)) (= D1 D2))))).
        (\forall H1, H2, D. (\impl (\and drink(H1, D) drink(H2, D)) (= H1 H2))).

    % Clue 3: The Dane drinks tea.
    \forall H. (\impl nation(H, dane) drink(H, tea)).

    % Clue 5: The green house's owner drinks coffee.
    \forall H. (\impl color(H, green) drink(H, coffee)).

    % Clue 8: The man living in the center house drinks milk.
    drink(3, milk).
]

[
    % ========================================================
    % Block 5: Smoke
    % ========================================================
    smoke(H, S)? :- is_house(H), is_smoke(S).

    % Bijectivity (merged)
        (\forall H. (\and
            (\exists S. smoke(H, S))
            (\forall S1, S2. (\impl (\and smoke(H, S1) smoke(H, S2)) (= S1 S2))))).
        (\forall H1, H2, S. (\impl (\and smoke(H1, S) smoke(H2, S)) (= H1 H2))).

    % Clue 6: The person who smokes Pall Mall rears birds.
    \forall H. (\impl smoke(H, pallmall) pet(H, bird)).

    % Clue 7: The owner of the yellow house smokes Dunhill.
    \forall H. (\impl color(H, yellow) smoke(H, dunhill)).

    % Clue 10: The man who smokes Blends lives next to the one who keeps cats.
    \forall H1. (\impl smoke(H1, blends)
        (\exists H2. (\and pet(H2, cat)
            (\or (= H2 (+ H1 1)) (= H2 (- H1 1)))
        ))
    ).

    % Clue 11: The man who keeps horses lives next to the man who smokes Dunhill.
    \forall H1. (\impl pet(H1, horse)
        (\exists H2. (\and smoke(H2, dunhill)
            (\or (= H2 (+ H1 1)) (= H2 (- H1 1)))
        ))
    ).

    % Clue 12: The owner who smokes BlueMaster drinks beer.
    \forall H. (\impl smoke(H, bluemaster) drink(H, beer)).

    % Clue 13: The German smokes Prince.
    \forall H. (\impl nation(H, german) smoke(H, prince)).

    % Clue 15: The man who smokes Blends has a neighbor who drinks water.
    \forall H1. (\impl smoke(H1, blends)
        (\exists H2. (\and drink(H2, water)
            (\or (= H2 (+ H1 1)) (= H2 (- H1 1)))
        ))
    ).
]
