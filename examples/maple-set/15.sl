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

    % Modified from FOL existence+uniqueness (5 lines) to #count:
    % (was: \forall T, Tile. (\impl (\and is_time(T) is_tile(Tile)) (\exists P. at(Tile, P, T))).
    %        \forall T, Tile, P1, P2. (\impl (\and at(Tile, P1, T) at(Tile, P2, T)) (= P1 P2)).)
    % Each Tile is at exactly one Position per time step
    \forall T, Tile.
        (\impl (\and is_time(T) is_tile(Tile))
               #count {Set_at}(P) = 1).

    % Modified from FOL injectivity (3 lines) to #count:
    % (was: \forall T, P, Tile1, Tile2. (\impl (\and at(Tile1, P, T) at(Tile2, P, T)) (= Tile1 Tile2)).)
    % Each Position has at most one Tile (the remaining one is Empty)
    \forall T, P. #count {Set_at}(Tile) <= 1.

    % ========================================================
    % 3. Initial State & Goal State (unchanged)
    % ========================================================

    \forall Tile, P. (\impl init_at(Tile, P) at(Tile, P, 0)).

    \forall Tile.
        (\impl is_tile(Tile)
               at(Tile, Tile, k)).

    % ========================================================
    % 4. Transition Dynamics (unchanged - temporal/frame axioms, no set operation applies)
    % ========================================================

    % Exactly one move per step (split for compiler compatibility)
    % At least one move
    \forall T.
        (\impl
            (\and is_time(T) (< T k))
            (\exists Tile. move(Tile, T))
        ).
    % At most one move
    \forall T.
        (\impl
            (\and is_time(T) (< T k))
            (\neg (\exists Tile1, Tile2.
                (\and move(Tile1, T) move(Tile2, T) (!= Tile1 Tile2))
            ))
        ).

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

    % Inertia: If a tile is NOT moved, it stays
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
