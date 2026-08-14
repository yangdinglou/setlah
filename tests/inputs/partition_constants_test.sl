% Test file for partition with constants
% Example: For each clause, exactly one action (continue, add, drop) at time t

ExtDOM Clause : Symbol.
ExtPred cl : (Symbol, Symbol, Symbol).  % cl(I, L1, L2) - clause I with literals L1, L2

[
    % At each timestep t, for each clause I, exactly one action
    c(t, I)? :- cl(I, L1, L2).
    ac(t, I)? :- cl(I, L1, L2).
    dc(t, I)? :- cl(I, L1, L2).
    
    % Partition: each clause gets exactly one action
    % Note: Set_cl matches body predicate cl(...)
    (\partition Set_cl {{Set_c Set_ac Set_dc}}).
]
