ExtDOM Node: INT.
ExtPred node: (Node).
ExtPred edge: (Node, Node).

% The target clique size (e.g., 5)
Const k: INT.

[
    % ========================================================
    % Block 1: Find a Clique of size >= k
    % ========================================================

    % 1. Guess: Select nodes for the clique
    in_clique(X)? :- node(X).

    % 2. Constraint: The Clique Property
    % "For any two distinct nodes X and Y, if both are in the clique, 
    % there must be an edge between them."
    (\neg (\exists X, Y.
        (\and
            in_clique(X)
            in_clique(Y)
            (!= X Y)
            (\neg edge(X, Y))
        )
    )).

    % 3. Constraint: Size Requirement
    % The count of selected nodes must be at least k.
    #count {Set_in_clique}(X) >= k.
]
