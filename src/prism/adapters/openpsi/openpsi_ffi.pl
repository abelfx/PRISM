%% Safe optional bridge.  OpenPsi supplies both the rule atoms and candidates.
:- use_module(library(janus)).

'prism-openpsi-best'(Successors, Goal, Rules, Visited, Result) :-
    catch(
        (   copy_term([Successors, Goal, Rules, Visited], [S0, G0, R0, V0]),
            term_attvars([S0, G0, R0, V0], Vars),
            maplist(del_attrs, Vars),
            numbervars([S0, G0, R0, V0], 0, _),
            py_call('prism.adapters.openpsi.selection':best_successor(S0, G0, R0, V0), Pick),
            (   Pick == @(none) -> Result = 'Error'
            ;   is_list(Pick) -> Result = Pick
            ;   Result = 'Error'
            )
        ),
        _,
        Result = 'Error'
    ).
