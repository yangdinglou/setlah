ExtDOM Request: INT.
ExtDOM Db_request_id: INT.
ExtDOM Node: INT.
ExtDOM Response: INT.

[
    pre_db_response_sent(X0, X1)? :- dom_Db_request_id(X0), dom_Response(X1).
    db_response_sent(X0, X1)? :- dom_Db_request_id(X0), dom_Response(X1).
    match(X0, X1)? :- dom_Request(X0), dom_Response(X1).
    db_request_sent(X0, X1)? :- dom_Db_request_id(X0), dom_Request(X1).
    t(X0, X1)? :- dom_Db_request_id(X0), dom_Node(X1).
    request_sent(X0, X1)? :- dom_Node(X0), dom_Request(X1).
    response_sent(X0, X1)? :- dom_Node(X0), dom_Response(X1).
    response_received(X0, X1)? :- dom_Node(X0), dom_Response(X1).
    k_pre_fml_p(X)? :- dom_Response(X).
    (\exists X. k_pre_fml_p(X)).
    (\forall X, Y. (\impl (\and k_pre_fml_p(X) k_pre_fml_p(Y)) (= X Y))).
    k_pre_fml_i(X)? :- dom_Db_request_id(X).
    (\exists X. k_pre_fml_i(X)).
    (\forall X, Y. (\impl (\and k_pre_fml_i(X) k_pre_fml_i(Y)) (= X Y))).
    k_pre_fml_r(X)? :- dom_Request(X).
    (\exists X. k_pre_fml_r(X)).
    (\forall X, Y. (\impl (\and k_pre_fml_r(X) k_pre_fml_r(Y)) (= X Y))).
    k_d1(X)? :- dom_Db_request_id(X).
    (\exists X. k_d1(X)).
    (\forall X, Y. (\impl (\and k_d1(X) k_d1(Y)) (= X Y))).
    aux_0(V_N_NODE, V_P_RESPONSE) :- dom_Request(V_R_REQUEST), request_sent(V_N_NODE, V_R_REQUEST), match(V_R_REQUEST, V_P_RESPONSE).

    % assert 0
    (\forall V_N_NODE, V_P_RESPONSE. (\impl (\and dom_Node(V_N_NODE) dom_Response(V_P_RESPONSE)) (\impl response_received(V_N_NODE, V_P_RESPONSE) aux_0(V_N_NODE, V_P_RESPONSE)))).
    % assert 1
    (\forall V_N1_NODE, V_RES1_RESPONSE. (\impl (\and dom_Node(V_N1_NODE) dom_Response(V_RES1_RESPONSE)) (\or response_sent(V_N1_NODE, V_RES1_RESPONSE) (\neg response_received(V_N1_NODE, V_RES1_RESPONSE))))).
    % assert 2
    (\forall V_D1_DB_REQUEST_ID, V_REQ1_REQUEST, V_RES1_RESPONSE. (\impl (\and dom_Db_request_id(V_D1_DB_REQUEST_ID) dom_Request(V_REQ1_REQUEST) dom_Response(V_RES1_RESPONSE)) (\or match(V_REQ1_REQUEST, V_RES1_RESPONSE) (\neg db_request_sent(V_D1_DB_REQUEST_ID, V_REQ1_REQUEST)) (\neg pre_db_response_sent(V_D1_DB_REQUEST_ID, V_RES1_RESPONSE))))).
    % assert 3
    (\forall V_D1_DB_REQUEST_ID, V_N1_NODE, V_REQ1_REQUEST. (\impl (\and dom_Db_request_id(V_D1_DB_REQUEST_ID) dom_Node(V_N1_NODE) dom_Request(V_REQ1_REQUEST)) (\or request_sent(V_N1_NODE, V_REQ1_REQUEST) (\neg db_request_sent(V_D1_DB_REQUEST_ID, V_REQ1_REQUEST)) (\neg t(V_D1_DB_REQUEST_ID, V_N1_NODE))))).
    % assert 4
    (\forall V_D1_DB_REQUEST_ID, V_N1_NODE. (\impl (\and dom_Db_request_id(V_D1_DB_REQUEST_ID) dom_Node(V_N1_NODE)) (\exists V_REQ1_REQUEST. (\and dom_Request(V_REQ1_REQUEST) (\or (\and request_sent(V_N1_NODE, V_REQ1_REQUEST) db_request_sent(V_D1_DB_REQUEST_ID, V_REQ1_REQUEST)) (\neg t(V_D1_DB_REQUEST_ID, V_N1_NODE))))))).
    % assert 5
    (\forall V_D1_DB_REQUEST_ID, V_RES1_RESPONSE. (\impl (\and dom_Db_request_id(V_D1_DB_REQUEST_ID) dom_Response(V_RES1_RESPONSE)) (\exists V_REQ1_REQUEST. (\and dom_Request(V_REQ1_REQUEST) (\or (\and match(V_REQ1_REQUEST, V_RES1_RESPONSE) db_request_sent(V_D1_DB_REQUEST_ID, V_REQ1_REQUEST)) (\neg pre_db_response_sent(V_D1_DB_REQUEST_ID, V_RES1_RESPONSE))))))).
    % assert 6
    (\forall V_N1_NODE, V_RES1_RESPONSE. (\impl (\and dom_Node(V_N1_NODE) dom_Response(V_RES1_RESPONSE)) (\exists V_REQ1_REQUEST. (\and dom_Request(V_REQ1_REQUEST) (\or (\and match(V_REQ1_REQUEST, V_RES1_RESPONSE) request_sent(V_N1_NODE, V_REQ1_REQUEST)) (\neg response_sent(V_N1_NODE, V_RES1_RESPONSE))))))).
    % assert 7
    (\forall V_D1_DB_REQUEST_ID, V_N1_NODE, V_RES1_RESPONSE. (\impl (\and dom_Db_request_id(V_D1_DB_REQUEST_ID) dom_Node(V_N1_NODE) dom_Response(V_RES1_RESPONSE)) (\exists V_REQ1_REQUEST. (\and dom_Request(V_REQ1_REQUEST) (\or (\and match(V_REQ1_REQUEST, V_RES1_RESPONSE) request_sent(V_N1_NODE, V_REQ1_REQUEST)) (\neg pre_db_response_sent(V_D1_DB_REQUEST_ID, V_RES1_RESPONSE)) (\neg t(V_D1_DB_REQUEST_ID, V_N1_NODE))))))).
    % assert 8
    (\forall V_D1_DB_REQUEST_ID. (\impl dom_Db_request_id(V_D1_DB_REQUEST_ID) (\exists V_N1_NODE. (\and dom_Node(V_N1_NODE) (\forall V_RES1_RESPONSE. (\impl dom_Response(V_RES1_RESPONSE) (\forall V_REQ1_REQUEST. (\impl dom_Request(V_REQ1_REQUEST) (\or (\and request_sent(V_N1_NODE, V_REQ1_REQUEST) t(V_D1_DB_REQUEST_ID, V_N1_NODE)) (\neg db_request_sent(V_D1_DB_REQUEST_ID, V_REQ1_REQUEST))))))))))).
    % assert 9
    (\forall V_D1_DB_REQUEST_ID. (\impl dom_Db_request_id(V_D1_DB_REQUEST_ID) (\exists V_N1_NODE. (\and dom_Node(V_N1_NODE) (\forall V_RES1_RESPONSE. (\impl dom_Response(V_RES1_RESPONSE) (\forall V_REQ1_REQUEST. (\impl dom_Request(V_REQ1_REQUEST) (\or t(V_D1_DB_REQUEST_ID, V_N1_NODE) (\neg pre_db_response_sent(V_D1_DB_REQUEST_ID, V_RES1_RESPONSE))))))))))).
    % assert 10
    (\forall V_D1_DB_REQUEST_ID, V_N1_NODE, V_N2_NODE. (\impl (\and dom_Db_request_id(V_D1_DB_REQUEST_ID) dom_Node(V_N1_NODE) dom_Node(V_N2_NODE)) (\impl (\neg (= V_N1_NODE V_N2_NODE)) (\or (\neg t(V_D1_DB_REQUEST_ID, V_N1_NODE)) (\neg t(V_D1_DB_REQUEST_ID, V_N2_NODE)))))).
    % assert 11
    (\forall K_PRE_FML_I, K_PRE_FML_R. (\impl (\and k_pre_fml_i(K_PRE_FML_I) k_pre_fml_r(K_PRE_FML_R)) db_request_sent(K_PRE_FML_I, K_PRE_FML_R))).
    % assert 12
    (\forall K_PRE_FML_P, K_PRE_FML_R. (\impl (\and k_pre_fml_p(K_PRE_FML_P) k_pre_fml_r(K_PRE_FML_R)) match(K_PRE_FML_R, K_PRE_FML_P))).
    % assert 13
    % (trivially true; dropped)
    % assert 14
    (\forall K_PRE_FML_I, K_PRE_FML_P. (\impl (\and k_pre_fml_i(K_PRE_FML_I) k_pre_fml_p(K_PRE_FML_P)) (\forall V_V0_DB_REQUEST_ID, V_V1_RESPONSE. (\impl (\and dom_Db_request_id(V_V0_DB_REQUEST_ID) dom_Response(V_V1_RESPONSE)) (\impl (\and (= V_V0_DB_REQUEST_ID K_PRE_FML_I) (= V_V1_RESPONSE K_PRE_FML_P)) db_response_sent(V_V0_DB_REQUEST_ID, V_V1_RESPONSE)))))).
    % assert 15
    (\forall K_PRE_FML_I. (\impl k_pre_fml_i(K_PRE_FML_I) (\forall V_V0_DB_REQUEST_ID, V_V1_RESPONSE. (\impl (\and dom_Db_request_id(V_V0_DB_REQUEST_ID) dom_Response(V_V1_RESPONSE)) (\impl (\neg (= V_V0_DB_REQUEST_ID K_PRE_FML_I)) (\impl db_response_sent(V_V0_DB_REQUEST_ID, V_V1_RESPONSE) pre_db_response_sent(V_V0_DB_REQUEST_ID, V_V1_RESPONSE))))))).
    % assert 16
    (\forall K_PRE_FML_I. (\impl k_pre_fml_i(K_PRE_FML_I) (\forall V_V0_DB_REQUEST_ID, V_V1_RESPONSE. (\impl (\and dom_Db_request_id(V_V0_DB_REQUEST_ID) dom_Response(V_V1_RESPONSE)) (\impl (\neg (= V_V0_DB_REQUEST_ID K_PRE_FML_I)) (\impl pre_db_response_sent(V_V0_DB_REQUEST_ID, V_V1_RESPONSE) db_response_sent(V_V0_DB_REQUEST_ID, V_V1_RESPONSE))))))).
    % assert 17
    (\forall K_PRE_FML_P. (\impl k_pre_fml_p(K_PRE_FML_P) (\forall V_V0_DB_REQUEST_ID, V_V1_RESPONSE. (\impl (\and dom_Db_request_id(V_V0_DB_REQUEST_ID) dom_Response(V_V1_RESPONSE)) (\impl (\neg (= V_V1_RESPONSE K_PRE_FML_P)) (\impl db_response_sent(V_V0_DB_REQUEST_ID, V_V1_RESPONSE) pre_db_response_sent(V_V0_DB_REQUEST_ID, V_V1_RESPONSE))))))).
    % assert 18
    (\forall K_PRE_FML_P. (\impl k_pre_fml_p(K_PRE_FML_P) (\forall V_V0_DB_REQUEST_ID, V_V1_RESPONSE. (\impl (\and dom_Db_request_id(V_V0_DB_REQUEST_ID) dom_Response(V_V1_RESPONSE)) (\impl (\neg (= V_V1_RESPONSE K_PRE_FML_P)) (\impl pre_db_response_sent(V_V0_DB_REQUEST_ID, V_V1_RESPONSE) db_response_sent(V_V0_DB_REQUEST_ID, V_V1_RESPONSE))))))).
    % assert 19
    (\forall K_D1. (\impl k_d1(K_D1) (\neg (\exists V_N1_NODE. (\and dom_Node(V_N1_NODE) (\forall V_RES1_RESPONSE. (\impl dom_Response(V_RES1_RESPONSE) (\forall V_REQ1_REQUEST. (\impl dom_Request(V_REQ1_REQUEST) (\or t(K_D1, V_N1_NODE) (\neg db_response_sent(K_D1, V_RES1_RESPONSE)))))))))))).
]
