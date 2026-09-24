%% prism_ffi.pl — Safe Python FFI bridge for PRISM
%%
%% Provides 'prism-score'/3 which safely calls scorer.score_candidate
%% through Janus, handling attributed variables and uninstantiated terms
%% that would otherwise crash py_call/3.
%%
%% Loaded via PeTTa's standard consult mechanism — does NOT modify metta.pl.

:- use_module(library(janus)).

%% prism-score(+Sentence, +Goal, -Result)
%%   Calls scorer.score_candidate(Sentence, Goal) via Janus.
%%   Returns the float score on success, or the atom 'Error' on any failure
%%   (uninstantiated variables, attributed variables, Python exceptions, etc.)
'prism-score'(Sentence, Goal, Result) :-
    catch(
        (   copy_term([Sentence, Goal], [SSentence, SGoal]),
            strip_attrs(SSentence),
            strip_attrs(SGoal),
            numbervars(SSentence, 0, N),
            numbervars(SGoal, N, _),
            py_call('prism.core.scorer':score_candidate(SSentence, SGoal), R0),
            Result = R0
        ),
        _,
        Result = 'Error'
    ).

%% strip_attrs(+Term)
%%   Recursively remove all attributes from variables in Term.
%%   This prevents Janus from choking on PeTTa's internal petta_swrite_name
%%   attributes attached to logic variables.
strip_attrs(Term) :-
    term_attvars(Term, Vars),
    maplist([V]>>del_attrs(V), Vars).


%% prism-filter-beliefs(+Candidate, +Goal, +Beliefs, -Result)
%%   Calls scorer.filter_beliefs(Candidate, Goal, Beliefs) via Janus.
%%   Returns the filtered list of beliefs on success, or the original Beliefs on failure.
'prism-filter-beliefs'(Candidate, Goal, Beliefs, Result) :-
    catch(
        (   copy_term([Candidate, Goal, Beliefs], [SCand, SGoal, SBeliefs]),
            strip_attrs(SCand),
            strip_attrs(SGoal),
            strip_attrs(SBeliefs),
            numbervars(SCand, 0, N1),
            numbervars(SGoal, N1, N2),
            numbervars(SBeliefs, N2, _),
            py_call('prism.core.scorer':filter_beliefs(SCand, SGoal, SBeliefs), R0),
            (   is_list(R0)
            ->  Result = R0
            ;   Result = Beliefs
            )
        ),
        _,
        Result = Beliefs
    ).
