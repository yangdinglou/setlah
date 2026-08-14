ExtDOM Tile: INT. % 1..15
ExtDOM Pos: INT.  % 1..16
ExtDOM Time: INT. % 0..k

% Domain Predicates for Grounding
ExtPred is_tile: (Tile).
ExtPred is_pos: (Pos).
ExtPred is_time: (Time).

ExtPred adj: (Pos, Pos).
ExtPred init_at: (Tile, Pos).

Const k: INT.

[
    % ========================================================
    % 1. Guess: State and Actions
    % ========================================================

    at(Tile, P, T)? :- is_tile(Tile), is_pos(P), is_time(T).
    move(Tile, T)? :- is_tile(Tile), is_time(T), (< T k).

    % ========================================================
    % 2. State Consistency
    % ========================================================

    % Each Tile is at exactly one Position (merged existence + uniqueness)
    \forall T, Tile.
        (\and
            (\exists P. at(Tile, P, T))
            (\forall P1, P2. (\impl (\and at(Tile, P1, T) at(Tile, P2, T)) (= P1 P2)))
        ).

    % Each Position has at most one Tile (the remaining one is Empty)
    \forall T, P, Tile1, Tile2.
        (\impl (\and at(Tile1, P, T) at(Tile2, P, T))
               (= Tile1 Tile2)).

    % ========================================================
    % 3. Initial State & Goal State
    % ========================================================

    % T=0 must match input
    \forall Tile, P. (\impl init_at(Tile, P) at(Tile, P, 0)).

    % T=k must be sorted (Tile i at Pos i)
    \forall Tile.
        (\impl is_tile(Tile)
               at(Tile, Tile, k)).

    % ========================================================
    % 4. Transition Dynamics
    % ========================================================

    % Exactly one move per step (merged at-least-one + at-most-one)
    \forall T.
            (\and
                (\exists Tile. move(Tile, T))
                (\neg (\exists Tile1, Tile2.
                    (\and move(Tile1, T) move(Tile2, T) (!= Tile1 Tile2))
                ))
            ).

    % --- Sliding Logic ---

    % Precondition: The moved tile must be adjacent to the Empty spot
    \forall T, Tile, P_tile, P_empty.
        (\impl
            (\and
                move(Tile, T)
                at(Tile, P_tile, T)
                is_pos(P_empty)
                (\neg (\exists T2. at(T2, P_empty, T)))
            )
            adj(P_tile, P_empty)
        ).

    % Effect: The moved tile lands in the Empty spot at T+1
    \forall T, Tile, P_empty.
        (\impl
            (\and
                move(Tile, T)
                is_pos(P_empty)
                (\neg (\exists T2. at(T2, P_empty, T)))
                (< T k)
            )
            at(Tile, P_empty, (+ T 1))
        ).

    % Inertia: If a tile is NOT moved, it stays in the same position
    \forall T, Tile, P.
        (\impl
            (\and
                at(Tile, P, T)
                (\neg move(Tile, T))
                (< T k)
            )
            at(Tile, P, (+ T 1))
        ).
]
