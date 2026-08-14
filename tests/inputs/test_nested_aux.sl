ExtDOM Index: INT. % 1..N

[
    % Simple predicates
    p(X, Y)? :- dom_Index(X), dom_Index(Y).
    q(X, Y)? :- dom_Index(X), dom_Index(Y).
    r(X, Y)? :- dom_Index(X), dom_Index(Y).
    s(X, Y)? :- dom_Index(X), dom_Index(Y).

    % Three-layer nested exists - requires 2 iterations of aux introduction:
    % forall A. (dom(A) => exists B. (p(A,B) and exists C. (q(B,C) and exists D. (r(C,D) and s(A,D)))))
    %
    % Iteration 1: innermost exists D → aux_0
    %   aux_0(A, C) :- r(C, D), s(A, D).
    %   formula: forall A. (dom(A) => exists B. (p(A,B) and exists C. (q(B,C) and aux_0(A,C))))
    %
    % Iteration 2: exists C. (q(B,C) and aux_0(A,C)) → aux_1
    %   aux_1(A, B) :- q(B, C), aux_0(A, C).
    %   formula: forall A. (dom(A) => exists B. (p(A,B) and aux_1(A,B)))
    %
    % Final: exists B becomes aggregate
    %   :- dom(A), #count{B : p(A,B), aux_1(A,B)} = 0.
    
    \forall A. 
        (\impl dom_Index(A)
            (\exists B. 
                (\and p(A, B) 
                    (\exists C. 
                        (\and q(B, C) 
                            (\exists D. (\and r(C, D) s(A, D)))
                        )
                    )
                )
            )
        ).
]
