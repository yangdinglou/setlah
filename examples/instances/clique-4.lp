#const k=3.

dom_Node(1..4).
node(1..4).

% Nodes 1, 2, and 3 form a directed triangle. Node 4 is not in a 3-clique.
edge(1,2). edge(2,1).
edge(1,3). edge(3,1).
edge(2,3). edge(3,2).
edge(3,4). edge(4,3).
