ExtDOM Request: INT.
ExtDOM Node: INT.
ExtDOM Db_request_id: INT.
ExtDOM Response: INT.

[
    pre_response_received(X0, X1)? :- dom_Node(X0), dom_Response(X1).
    response_received(X0, X1)? :- dom_Node(X0), dom_Response(X1).
    response_sent(X0, X1)? :- dom_Node(X0), dom_Response(X1).
    t(X0, X1)? :- dom_Db_request_id(X0), dom_Node(X1).
    db_response_sent(X0, X1)? :- dom_Db_request_id(X0), dom_Response(X1).
    db_request_sent(X0, X1)? :- dom_Db_request_id(X0), dom_Request(X1).
    request_sent(X0, X1)? :- dom_Node(X0), dom_Request(X1).
    match(X0, X1)? :- dom_Request(X0), dom_Response(X1).
    k_pre_fml_p(X)? :- dom_Response(X).
    (\exists X. k_pre_fml_p(X)).
    (\forall X, Y. (\impl (\and k_pre_fml_p(X) k_pre_fml_p(Y)) (= X Y))).
    k_pre_fml_n(X)? :- dom_Node(X).
    (\exists X. k_pre_fml_n(X)).
    (\forall X, Y. (\impl (\and k_pre_fml_n(X) k_pre_fml_n(Y)) (= X Y))).
    k_res1(X)? :- dom_Response(X).
    (\exists X. k_res1(X)).
    (\forall X, Y. (\impl (\and k_res1(X) k_res1(Y)) (= X Y))).
    k_d1(X)? :- dom_Db_request_id(X).
    (\exists X. k_d1(X)).
    (\forall X, Y. (\impl (\and k_d1(X) k_d1(Y)) (= X Y))).
    k_req1(X)? :- dom_Request(X).
    (\exists X. k_req1(X)).
    (\forall X, Y. (\impl (\and k_req1(X) k_req1(Y)) (= X Y))).
    aux_0(V_N_NODE, V_P_RESPONSE) :- dom_Request(V_R_REQUEST), request_sent(V_N_NODE, V_R_REQUEST), match(V_R_REQUEST, V_P_RESPONSE).

    % assert 8
    (\forall V_D1_DB_REQUEST_ID. (\impl dom_Db_request_id(V_D1_DB_REQUEST_ID) (\exists V_N1_NODE. (\and dom_Node(V_N1_NODE) (\forall V_RES1_RESPONSE. (\impl dom_Response(V_RES1_RESPONSE) (\forall V_REQ1_REQUEST. (\impl dom_Request(V_REQ1_REQUEST) (\or (\and request_sent(V_N1_NODE, V_REQ1_REQUEST) t(V_D1_DB_REQUEST_ID, V_N1_NODE)) (\neg db_request_sent(V_D1_DB_REQUEST_ID, V_REQ1_REQUEST))))))))))).

]
