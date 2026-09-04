ExtDOM Sort_string_0: INT.
ExtDOM Sort_scc_address_1: INT.
ExtDOM Sort_scc_thread_1: INT.
ExtDOM Sort_scc_event_1: INT.
ExtDOM Int: INT.

[
    inscc_address_0(X0)? :- dom_Sort_scc_address_1(X0).
    inscc_thread_0(X0)? :- dom_Sort_scc_thread_1(X0).
    inscc_event_0(X0)? :- dom_Sort_scc_event_1(X0).
    inscc_memoryevent_0(X0)? :- dom_Sort_scc_event_1(X0).
    inscc_read_0(X0)? :- dom_Sort_scc_event_1(X0).
    inscc_acquire_0(X0)? :- dom_Sort_scc_event_1(X0).
    inscc_write_0(X0)? :- dom_Sort_scc_event_1(X0).
    inscc_release_0(X0)? :- dom_Sort_scc_event_1(X0).
    inscc_fence_0(X0)? :- dom_Sort_scc_event_1(X0).
    inscc_fenceall_0(X0)? :- dom_Sort_scc_event_1(X0).
    inscc_fencesc_0(X0)? :- dom_Sort_scc_event_1(X0).
    indomain_0(X0)? :- dom_Sort_scc_event_1(X0).
    po_loc_0(X0, X1)? :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1).
    addr_0(X0, X1)? :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1).
    data_0(X0, X1)? :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1).
    fr_0(X0, X1)? :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1).
    indomain_1(X0)? :- dom_Sort_scc_event_1(X0).
    rf_0(X0, X1)? :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1).
    indomain_2(X0)? :- dom_Sort_scc_event_1(X0).
    sc_0(X0, X1)? :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1).
    start_0(X0, Y)? :- dom_Sort_scc_thread_1(X0), dom_Sort_scc_event_1(Y).
    po_0(X0, Y)? :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(Y).
    address_0(X0, Y)? :- dom_Sort_scc_event_1(X0), dom_Sort_scc_address_1(Y).
    rmw_0(X0, Y)? :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(Y).
    co_0(X0, Y)? :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(Y).
    d_closurenest1_0(X0, Y)? :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(Y).
    d_closurenest2_0(X0, Y)? :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(Y).
    d_closurenest4_0(X0, Y)? :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(Y).
    d_exprdefn_5(X0)? :- dom_Sort_scc_address_1(X0).
    d_closurenest1_1(X0, Y)? :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(Y).
    d_closurenest2_1(X0, Y)? :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(Y).
    d_closurenest4_1(X0, Y)? :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(Y).
    d_exprdefn_13(X0, X1)? :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1).
    d_exprdefn_17(X0, X1)? :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1).
    d_sum_def_0(X0, Y)? :- dom_Sort_scc_address_1(X0), dom_Int(Y).
    ite_120(X0, Y)? :- dom_Sort_scc_address_1(X0), dom_Int(Y).
    d_sum_def_1(X0, Y)? :- dom_Sort_scc_thread_1(X0), dom_Int(Y).
    ite_128(X0, Y)? :- dom_Sort_scc_thread_1(X0), dom_Int(Y).
    d_sum_def_2(X0, Y)? :- dom_Sort_scc_event_1(X0), dom_Int(Y).
    ite_136(X0, Y)? :- dom_Sort_scc_event_1(X0), dom_Int(Y).
    d_sum_def_3(X0, Y)? :- dom_Sort_scc_event_1(X0), dom_Int(Y).
    ite_144(X0, Y)? :- dom_Sort_scc_event_1(X0), dom_Int(Y).
    d_exprdefn_25(X0, X1)? :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1).
    d_scalartc_0(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), indomain_0(X0), dom_Sort_scc_event_1(F_13), d_closurenest1_0(X0, F_13), (= X1 F_13).
    d_scalartc_0(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), indomain_0(X0), dom_Sort_scc_event_1(F_14), d_closurenest1_0(X0, F_14), indomain_0(F_14), dom_Sort_scc_event_1(F_17), d_closurenest2_0(X0, F_17), (= X1 F_17).
    d_scalartc_0(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), indomain_0(X0), dom_Sort_scc_event_1(F_14), d_closurenest1_0(X0, F_14), indomain_0(F_14), dom_Sort_scc_event_1(F_18), d_closurenest2_0(X0, F_18), indomain_0(F_18), dom_Sort_scc_event_1(F_19), dom_Sort_scc_event_1(F_20), d_closurenest1_0(X0, F_19), d_closurenest2_0(F_19, F_20), (= X1 F_20).
    d_scalartc_0(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), indomain_0(X0), dom_Sort_scc_event_1(F_14), d_closurenest1_0(X0, F_14), indomain_0(F_14), dom_Sort_scc_event_1(F_18), d_closurenest2_0(X0, F_18), indomain_0(F_18), dom_Sort_scc_event_1(F_21), dom_Sort_scc_event_1(F_22), d_closurenest1_0(X0, F_21), d_closurenest2_0(F_21, F_22), indomain_0(F_22), dom_Sort_scc_event_1(F_25), d_closurenest4_0(X0, F_25), (= X1 F_25).
    d_scalartc_0(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), indomain_0(X0), dom_Sort_scc_event_1(F_14), d_closurenest1_0(X0, F_14), indomain_0(F_14), dom_Sort_scc_event_1(F_18), d_closurenest2_0(X0, F_18), indomain_0(F_18), dom_Sort_scc_event_1(F_21), dom_Sort_scc_event_1(F_22), d_closurenest1_0(X0, F_21), d_closurenest2_0(F_21, F_22), indomain_0(F_22), dom_Sort_scc_event_1(F_26), d_closurenest4_0(X0, F_26), indomain_0(F_26), dom_Sort_scc_event_1(F_27), dom_Sort_scc_event_1(F_28), d_closurenest1_0(X0, F_27), d_closurenest4_0(F_27, F_28), (= X1 F_28).
    d_scalartc_0(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), indomain_0(X0), dom_Sort_scc_event_1(F_14), d_closurenest1_0(X0, F_14), indomain_0(F_14), dom_Sort_scc_event_1(F_18), d_closurenest2_0(X0, F_18), indomain_0(F_18), dom_Sort_scc_event_1(F_21), dom_Sort_scc_event_1(F_22), d_closurenest1_0(X0, F_21), d_closurenest2_0(F_21, F_22), indomain_0(F_22), dom_Sort_scc_event_1(F_26), d_closurenest4_0(X0, F_26), indomain_0(F_26), dom_Sort_scc_event_1(F_29), dom_Sort_scc_event_1(F_30), d_closurenest1_0(X0, F_29), d_closurenest4_0(F_29, F_30), indomain_0(F_30), dom_Sort_scc_event_1(F_31), dom_Sort_scc_event_1(F_32), d_closurenest2_0(X0, F_31), d_closurenest4_0(F_31, F_32), (= X1 F_32).
    d_scalartc_1(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), (= X1 X0).
    d_scalartc_1(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), indomain_0(X0), dom_Sort_scc_event_1(F_34), d_closurenest1_0(X0, F_34), (= X1 F_34).
    d_scalartc_1(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), indomain_0(X0), dom_Sort_scc_event_1(F_35), d_closurenest1_0(X0, F_35), indomain_0(F_35), dom_Sort_scc_event_1(F_36), d_closurenest2_0(X0, F_36), (= X1 F_36).
    d_scalartc_1(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), indomain_0(X0), dom_Sort_scc_event_1(F_35), d_closurenest1_0(X0, F_35), indomain_0(F_35), dom_Sort_scc_event_1(F_37), d_closurenest2_0(X0, F_37), indomain_0(F_37), dom_Sort_scc_event_1(F_38), dom_Sort_scc_event_1(F_39), d_closurenest1_0(X0, F_38), d_closurenest2_0(F_38, F_39), (= X1 F_39).
    d_scalartc_1(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), indomain_0(X0), dom_Sort_scc_event_1(F_35), d_closurenest1_0(X0, F_35), indomain_0(F_35), dom_Sort_scc_event_1(F_37), d_closurenest2_0(X0, F_37), indomain_0(F_37), dom_Sort_scc_event_1(F_40), dom_Sort_scc_event_1(F_41), d_closurenest1_0(X0, F_40), d_closurenest2_0(F_40, F_41), indomain_0(F_41), dom_Sort_scc_event_1(F_42), d_closurenest4_0(X0, F_42), (= X1 F_42).
    d_scalartc_1(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), indomain_0(X0), dom_Sort_scc_event_1(F_35), d_closurenest1_0(X0, F_35), indomain_0(F_35), dom_Sort_scc_event_1(F_37), d_closurenest2_0(X0, F_37), indomain_0(F_37), dom_Sort_scc_event_1(F_40), dom_Sort_scc_event_1(F_41), d_closurenest1_0(X0, F_40), d_closurenest2_0(F_40, F_41), indomain_0(F_41), dom_Sort_scc_event_1(F_43), d_closurenest4_0(X0, F_43), indomain_0(F_43), dom_Sort_scc_event_1(F_44), dom_Sort_scc_event_1(F_45), d_closurenest1_0(X0, F_44), d_closurenest4_0(F_44, F_45), (= X1 F_45).
    d_scalartc_1(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), indomain_0(X0), dom_Sort_scc_event_1(F_35), d_closurenest1_0(X0, F_35), indomain_0(F_35), dom_Sort_scc_event_1(F_37), d_closurenest2_0(X0, F_37), indomain_0(F_37), dom_Sort_scc_event_1(F_40), dom_Sort_scc_event_1(F_41), d_closurenest1_0(X0, F_40), d_closurenest2_0(F_40, F_41), indomain_0(F_41), dom_Sort_scc_event_1(F_43), d_closurenest4_0(X0, F_43), indomain_0(F_43), dom_Sort_scc_event_1(F_46), dom_Sort_scc_event_1(F_47), d_closurenest1_0(X0, F_46), d_closurenest4_0(F_46, F_47), indomain_0(F_47), dom_Sort_scc_event_1(F_48), dom_Sort_scc_event_1(F_49), d_closurenest2_0(X0, F_48), d_closurenest4_0(F_48, F_49), (= X1 F_49).
    d_exprdefn_2(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), addr_0(X0, X1).
    d_exprdefn_2(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), data_0(X0, X1).
    d_scalartc_2(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), indomain_2(X0), dom_Sort_scc_event_1(F_58), d_closurenest1_1(X0, F_58), (= X1 F_58).
    d_scalartc_2(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), indomain_2(X0), dom_Sort_scc_event_1(F_59), d_closurenest1_1(X0, F_59), indomain_2(F_59), dom_Sort_scc_event_1(F_62), d_closurenest2_1(X0, F_62), (= X1 F_62).
    d_scalartc_2(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), indomain_2(X0), dom_Sort_scc_event_1(F_59), d_closurenest1_1(X0, F_59), indomain_2(F_59), dom_Sort_scc_event_1(F_63), d_closurenest2_1(X0, F_63), indomain_2(F_63), dom_Sort_scc_event_1(F_64), dom_Sort_scc_event_1(F_65), d_closurenest1_1(X0, F_64), d_closurenest2_1(F_64, F_65), (= X1 F_65).
    d_scalartc_2(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), indomain_2(X0), dom_Sort_scc_event_1(F_59), d_closurenest1_1(X0, F_59), indomain_2(F_59), dom_Sort_scc_event_1(F_63), d_closurenest2_1(X0, F_63), indomain_2(F_63), dom_Sort_scc_event_1(F_66), dom_Sort_scc_event_1(F_67), d_closurenest1_1(X0, F_66), d_closurenest2_1(F_66, F_67), indomain_2(F_67), dom_Sort_scc_event_1(F_70), d_closurenest4_1(X0, F_70), (= X1 F_70).
    d_scalartc_2(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), indomain_2(X0), dom_Sort_scc_event_1(F_59), d_closurenest1_1(X0, F_59), indomain_2(F_59), dom_Sort_scc_event_1(F_63), d_closurenest2_1(X0, F_63), indomain_2(F_63), dom_Sort_scc_event_1(F_66), dom_Sort_scc_event_1(F_67), d_closurenest1_1(X0, F_66), d_closurenest2_1(F_66, F_67), indomain_2(F_67), dom_Sort_scc_event_1(F_71), d_closurenest4_1(X0, F_71), indomain_2(F_71), dom_Sort_scc_event_1(F_72), dom_Sort_scc_event_1(F_73), d_closurenest1_1(X0, F_72), d_closurenest4_1(F_72, F_73), (= X1 F_73).
    d_scalartc_2(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), indomain_2(X0), dom_Sort_scc_event_1(F_59), d_closurenest1_1(X0, F_59), indomain_2(F_59), dom_Sort_scc_event_1(F_63), d_closurenest2_1(X0, F_63), indomain_2(F_63), dom_Sort_scc_event_1(F_66), dom_Sort_scc_event_1(F_67), d_closurenest1_1(X0, F_66), d_closurenest2_1(F_66, F_67), indomain_2(F_67), dom_Sort_scc_event_1(F_71), d_closurenest4_1(X0, F_71), indomain_2(F_71), dom_Sort_scc_event_1(F_74), dom_Sort_scc_event_1(F_75), d_closurenest1_1(X0, F_74), d_closurenest4_1(F_74, F_75), indomain_2(F_75), dom_Sort_scc_event_1(F_76), dom_Sort_scc_event_1(F_77), d_closurenest2_1(X0, F_76), d_closurenest4_1(F_76, F_77), (= X1 F_77).
    d_closureaux_sort_scc_event_1_0(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), indomain_2(X1), dom_Sort_scc_event_1(F_78), co_0(X1, F_78), (= X0 F_78).
    tc_79(X0, X1) :- d_closureaux_sort_scc_event_1_0(X0, X1).
    tc_79(X0, X2) :- d_closureaux_sort_scc_event_1_0(X0, X1), tc_79(X1, X2).
    d_exprdefn_6(X0) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(F_106), po_0(X0, F_106), addr_0(X0, F_106).
    d_exprdefn_6(X0) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(F_107), po_0(X0, F_107), data_0(X0, F_107).
    d_closureaux_sort_scc_event_1_1(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), sc_0(X0, X1).
    tc_114(X0, X1) :- d_closureaux_sort_scc_event_1_1(X0, X1).
    tc_114(X0, X2) :- d_closureaux_sort_scc_event_1_1(X0, X1), tc_114(X1, X2).
    d_closureaux_sort_scc_event_1_2(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), sc_0(X1, X0).
    tc_115(X0, X1) :- d_closureaux_sort_scc_event_1_2(X0, X1).
    tc_115(X0, X2) :- d_closureaux_sort_scc_event_1_2(X0, X1), tc_115(X1, X2).
    d_exprdefn_10(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), fr_0(X0, X1), (= X0 X1).
    d_exprdefn_10(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), fr_0(X0, X1), d_scalartc_0(X0, X1).
    d_exprdefn_10(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), fr_0(X0, X1), d_scalartc_0(X1, X0).
    d_exprdefn_11(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), d_exprdefn_10(X0, X1).
    d_exprdefn_12(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), d_exprdefn_11(X0, X1).
    d_exprdefn_14(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), rf_0(X0, X1), (= X0 X1).
    d_exprdefn_14(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), rf_0(X0, X1), d_scalartc_0(X0, X1).
    d_exprdefn_14(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), rf_0(X0, X1), d_scalartc_0(X1, X0).
    d_exprdefn_15(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), d_exprdefn_14(X0, X1).
    d_exprdefn_16(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), d_exprdefn_15(X0, X1).
    d_closureaux_sort_scc_event_1_3(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), dom_Sort_scc_event_1(E_116), dom_Sort_scc_event_1(E_117), dom_Sort_scc_event_1(E_118), d_exprdefn_13(X0, E_118), d_scalartc_0(E_118, E_117), d_exprdefn_17(E_117, E_116), d_scalartc_0(E_116, X1).
    tc_119(X0, X1) :- d_closureaux_sort_scc_event_1_3(X0, X1).
    tc_119(X0, X2) :- d_closureaux_sort_scc_event_1_3(X0, X1), tc_119(X1, X2).
    d_closureaux_sort_scc_event_1_4(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), rf_0(X0, X1).
    d_closureaux_sort_scc_event_1_4(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), indomain_2(X0), dom_Sort_scc_event_1(F_152), co_0(X0, F_152), (= X1 F_152).
    d_closureaux_sort_scc_event_1_4(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), fr_0(X0, X1).
    d_closureaux_sort_scc_event_1_4(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), po_loc_0(X0, X1).
    tc_153(X0, X1) :- d_closureaux_sort_scc_event_1_4(X0, X1).
    tc_153(X0, X2) :- d_closureaux_sort_scc_event_1_4(X0, X1), tc_153(X1, X2).
    d_closureaux_sort_scc_event_1_5(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), d_exprdefn_17(X0, X1).
    d_closureaux_sort_scc_event_1_5(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), d_exprdefn_2(X0, X1).
    tc_154(X0, X1) :- d_closureaux_sort_scc_event_1_5(X0, X1).
    tc_154(X0, X2) :- d_closureaux_sort_scc_event_1_5(X0, X1), tc_154(X1, X2).
    tc_161(X0, X1) :- sc_0(X0, X1).
    tc_161(X0, X2) :- sc_0(X0, X1), tc_161(X1, X2).
    d_closureaux_sort_scc_event_1_7(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), po_loc_0(X0, X1), inscc_write_0(X1).
    tc_162(X0, X1) :- d_closureaux_sort_scc_event_1_7(X0, X1).
    tc_162(X0, X2) :- d_closureaux_sort_scc_event_1_7(X0, X1), tc_162(X1, X2).
    d_exprdefn_26(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), d_exprdefn_17(X0, X1).
    d_exprdefn_26(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), indomain_1(X0), dom_Sort_scc_event_1(F_159), rmw_0(X0, F_159), (= X1 F_159).
    d_exprdefn_26(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), d_exprdefn_25(X0, X1).
    d_closureaux_sort_scc_event_1_6(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), d_exprdefn_26(X0, X1).
    tc_163(X0, X1) :- d_closureaux_sort_scc_event_1_6(X0, X1).
    tc_163(X0, X2) :- d_closureaux_sort_scc_event_1_6(X0, X1), tc_163(X1, X2).
    d_exprdefn_29(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), dom_Sort_scc_event_1(E_167), d_scalartc_0(X0, E_167), inscc_fencesc_0(E_167), d_scalartc_0(E_167, X1).
    d_exprdefn_30(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), dom_Sort_scc_event_1(E_164), dom_Sort_scc_event_1(E_165), dom_Sort_scc_event_1(E_166), d_exprdefn_13(X0, E_166), d_exprdefn_29(E_166, E_165), d_exprdefn_17(E_165, E_164), d_exprdefn_29(E_164, X1).
    d_closureaux_sort_scc_event_1_8(X0, X1) :- dom_Sort_scc_event_1(X0), dom_Sort_scc_event_1(X1), d_exprdefn_30(X0, X1).
    tc_168(X0, X1) :- d_closureaux_sort_scc_event_1_8(X0, X1).
    tc_168(X0, X2) :- d_closureaux_sort_scc_event_1_8(X0, X1), tc_168(X1, X2).
    (\impl dom_Sort_scc_event_1 (V_X0_24) (\or (\neg indomain_1 (V_X0_24)) (\and (\and (\and indomain_0 (V_X0_24) d_exprdefn_6 (V_X0_24)) (\and inscc_memoryevent_0 (V_X0_24) (\and (\forall F_108. (\impl (\and dom_Sort_scc_event_1 (F_108) po_0 (V_X0_24, F_108)) inscc_memoryevent_0 (F_108))) (\forall F_109. (\impl (\and dom_Sort_scc_address_1 (F_109) address_0 (V_X0_24, F_109)) (\forall F_110. (\impl (\and dom_Sort_scc_event_1 (F_110) po_0 (V_X0_24, F_110)) (\forall F_111. (\impl (\and dom_Sort_scc_address_1 (F_111) address_0 (F_110, F_111)) (= F_109 F_111)))))))))) (\forall F_112. (\impl (\and dom_Sort_scc_event_1 (F_112) rmw_0 (V_X0_24, F_112)) (\forall F_113. (\impl (\and dom_Sort_scc_event_1 (F_113) po_0 (V_X0_24, F_113)) (= F_112 F_113)))))))).
]
