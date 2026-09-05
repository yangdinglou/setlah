ExtDOM Request: INT.
ExtDOM Db_request_id: INT.
ExtDOM Node: INT.
ExtDOM Response: INT.

[
    pre_db_response_sent(X0, X1)? :- dom_Db_request_id(X0), dom_Response(X1).
    db_response_sent(X0, X1)? :- dom_Db_request_id(X0), dom_Response(X1).
    k_pre_fml_p(X)? :- dom_Response(X).
    (\exists X. k_pre_fml_p(X)).
    (\forall X, Y. (\impl (\and k_pre_fml_p(X) k_pre_fml_p(Y)) (= X Y))).
    k_pre_fml_i(X)? :- dom_Db_request_id(X).
    (\exists X. k_pre_fml_i(X)).
    (\forall X, Y. (\impl (\and k_pre_fml_i(X) k_pre_fml_i(Y)) (= X Y))).
    % Ivy's frame axiom as written: post(V) = ite(V = K, new, pre(V)) under the witness guards
    (\forall K_PRE_FML_I, K_PRE_FML_P. (\impl (\and k_pre_fml_i(K_PRE_FML_I) k_pre_fml_p(K_PRE_FML_P)) (\forall V_V0_DB_REQUEST_ID, V_V1_RESPONSE. (\impl (\and dom_Db_request_id(V_V0_DB_REQUEST_ID) dom_Response(V_V1_RESPONSE)) (\and (\impl (\and (= V_V0_DB_REQUEST_ID K_PRE_FML_I) (= V_V1_RESPONSE K_PRE_FML_P)) db_response_sent(V_V0_DB_REQUEST_ID, V_V1_RESPONSE)) (\impl (\neg (= V_V0_DB_REQUEST_ID K_PRE_FML_I)) (\and (\impl db_response_sent(V_V0_DB_REQUEST_ID, V_V1_RESPONSE) pre_db_response_sent(V_V0_DB_REQUEST_ID, V_V1_RESPONSE)) (\impl pre_db_response_sent(V_V0_DB_REQUEST_ID, V_V1_RESPONSE) db_response_sent(V_V0_DB_REQUEST_ID, V_V1_RESPONSE)))) (\impl (\neg (= V_V1_RESPONSE K_PRE_FML_P)) (\and (\impl db_response_sent(V_V0_DB_REQUEST_ID, V_V1_RESPONSE) pre_db_response_sent(V_V0_DB_REQUEST_ID, V_V1_RESPONSE)) (\impl pre_db_response_sent(V_V0_DB_REQUEST_ID, V_V1_RESPONSE) db_response_sent(V_V0_DB_REQUEST_ID, V_V1_RESPONSE))))))))).
]
