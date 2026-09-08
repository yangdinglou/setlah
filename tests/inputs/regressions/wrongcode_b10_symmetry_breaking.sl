% B10 reproducer: a block with one symmetric uniqueness pair (the singleton k) made
% the symmetry-breaking pass rewrite every "not X = Y" of every integrity constraint
% in the block to "X < Y", here in a constraint that is not symmetric in X and Y.
% With wrongcode_b10.lp (p(2), q(1)) the program must force r(2, 1); the unfixed
% compiler left half the answer sets without it. Both lowerings were affected.
ExtDOM S: INT.
ExtPred p: (S).
ExtPred q: (S).

[
    k(X)? :- dom_S(X).
    (\exists X. k(X)).
    (\forall X, Y. (\impl (\and k(X) k(Y)) (= X Y))).
    r(X, Y)? :- dom_S(X), dom_S(Y).
    (\forall X, Y. (\impl (\and p(X) q(Y) (\neg (= X Y))) r(X, Y))).
]
