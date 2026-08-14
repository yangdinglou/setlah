#const k=0.

dom_Tile(1..15). is_tile(1..15).
dom_Pos(1..16). is_pos(1..16).
dom_Time(0). is_time(0).

% The goal state itself is a useful zero-move sanity instance.
init_at(1,1). init_at(2,2). init_at(3,3). init_at(4,4).
init_at(5,5). init_at(6,6). init_at(7,7). init_at(8,8).
init_at(9,9). init_at(10,10). init_at(11,11). init_at(12,12).
init_at(13,13). init_at(14,14). init_at(15,15).

% Orthogonal adjacency on the 4x4 board (both directions).
adj(1,2). adj(2,1). adj(2,3). adj(3,2). adj(3,4). adj(4,3).
adj(5,6). adj(6,5). adj(6,7). adj(7,6). adj(7,8). adj(8,7).
adj(9,10). adj(10,9). adj(10,11). adj(11,10). adj(11,12). adj(12,11).
adj(13,14). adj(14,13). adj(14,15). adj(15,14). adj(15,16). adj(16,15).
adj(1,5). adj(5,1). adj(2,6). adj(6,2). adj(3,7). adj(7,3). adj(4,8). adj(8,4).
adj(5,9). adj(9,5). adj(6,10). adj(10,6). adj(7,11). adj(11,7). adj(8,12). adj(12,8).
adj(9,13). adj(13,9). adj(10,14). adj(14,10). adj(11,15). adj(15,11). adj(12,16). adj(16,12).
