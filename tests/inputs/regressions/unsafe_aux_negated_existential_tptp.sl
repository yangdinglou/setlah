ExtDOM U: INT.
ExtPred one: (U).

[
    p_s_actual_world(X0)? :- dom_U(X0).
    p_s_agent(X0, X1, X2)? :- dom_U(X0), dom_U(X1), dom_U(X2).
    p_s_animate(X0, X1)? :- dom_U(X0), dom_U(X1).
    p_s_artifact(X0, X1)? :- dom_U(X0), dom_U(X1).
    p_s_at(X0, X1, X2)? :- dom_U(X0), dom_U(X1), dom_U(X2).
    p_s_burger(X0, X1)? :- dom_U(X0), dom_U(X1).
    p_s_entity(X0, X1)? :- dom_U(X0), dom_U(X1).
    p_s_event(X0, X1)? :- dom_U(X0), dom_U(X1).
    p_s_eventuality(X0, X1)? :- dom_U(X0), dom_U(X1).
    p_s_existent(X0, X1)? :- dom_U(X0), dom_U(X1).
    p_s_food(X0, X1)? :- dom_U(X0), dom_U(X1).
    p_s_furniture(X0, X1)? :- dom_U(X0), dom_U(X1).
    p_s_group(X0, X1)? :- dom_U(X0), dom_U(X1).
    p_s_guy(X0, X1)? :- dom_U(X0), dom_U(X1).
    p_s_hamburger(X0, X1)? :- dom_U(X0), dom_U(X1).
    p_s_human(X0, X1)? :- dom_U(X0), dom_U(X1).
    p_s_human_person(X0, X1)? :- dom_U(X0), dom_U(X1).
    p_s_impartial(X0, X1)? :- dom_U(X0), dom_U(X1).
    p_s_instrumentality(X0, X1)? :- dom_U(X0), dom_U(X1).
    p_s_living(X0, X1)? :- dom_U(X0), dom_U(X1).
    p_s_male(X0, X1)? :- dom_U(X0), dom_U(X1).
    p_s_man(X0, X1)? :- dom_U(X0), dom_U(X1).
    p_s_meat(X0, X1)? :- dom_U(X0), dom_U(X1).
    p_s_member(X0, X1, X2)? :- dom_U(X0), dom_U(X1), dom_U(X2).
    p_s_multiple(X0, X1)? :- dom_U(X0), dom_U(X1).
    p_s_nonexistent(X0, X1)? :- dom_U(X0), dom_U(X1).
    p_s_nonliving(X0, X1)? :- dom_U(X0), dom_U(X1).
    p_s_object(X0, X1)? :- dom_U(X0), dom_U(X1).
    p_s_organism(X0, X1)? :- dom_U(X0), dom_U(X1).
    p_s_present(X0, X1)? :- dom_U(X0), dom_U(X1).
    p_s_set(X0, X1)? :- dom_U(X0), dom_U(X1).
    p_s_singleton(X0, X1)? :- dom_U(X0), dom_U(X1).
    p_s_sit(X0, X1)? :- dom_U(X0), dom_U(X1).
    p_s_specific(X0, X1)? :- dom_U(X0), dom_U(X1).
    p_s_substance_matter(X0, X1)? :- dom_U(X0), dom_U(X1).
    p_s_table(X0, X1)? :- dom_U(X0), dom_U(X1).
    p_s_thing(X0, X1)? :- dom_U(X0), dom_U(X1).
    p_s_three(X0, X1)? :- dom_U(X0), dom_U(X1).
    p_s_unisex(X0, X1)? :- dom_U(X0), dom_U(X1).
    p_s_with(X0, X1, X2)? :- dom_U(X0), dom_U(X1), dom_U(X2).
    p_s_young(X0, X1)? :- dom_U(X0), dom_U(X1).
    sk_1(X)? :- dom_U(X).
    (\forall U. (\impl sk_1(U) (\exists V, W. (\and dom_U(V) dom_U(W) (\and p_s_table(U, V) (\forall X. (\impl dom_U(X) (\or (\neg p_s_member(U, X, W)) (\exists Y. (\and dom_U(Y) (\and (\forall Z. (\impl dom_U(Z) (\or (\neg p_s_member(U, Z, Y)) (\exists X1. (\and dom_U(X1) (\and p_s_event(U, X1) p_s_agent(U, X1, Z) p_s_present(U, X1) p_s_sit(U, X1) p_s_at(U, X1, V) p_s_with(U, X1, X))))))) p_s_three(U, Y) p_s_group(U, Y) (\forall X2. (\impl dom_U(X2) (\or (\neg p_s_member(U, X2, Y)) (\and p_s_guy(U, X2) p_s_young(U, X2))))))))))) p_s_group(U, W) (\forall X3. (\impl dom_U(X3) (\or (\neg p_s_member(U, X3, W)) p_s_hamburger(U, X3))))))))).
]
