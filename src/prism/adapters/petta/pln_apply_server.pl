%% Persistent PeTTa worker for PRISM search.
%% Loads lib_pln.metta once, then evaluates PLN.Apply requests on stdin.
%%
%% Protocol (line-oriented):
%%   >BOOT
%%   >RESET_STVS
%%   >EVAL
%%   ... MeTTa source ...
%%   >END
%%   >QUIT
%%
%% Replies:
%%   <OK
%%   <... result lines ...
%%   <END
%%   or
%%   <ERR
%%   <message
%%   <END

:- use_module(library(readutil)).

:- initialization(main, main).

main :-
    catch(run, Error, (print_message(error, Error), halt(1))),
    halt.

run :-
    getenv('PETTA_HOME', Home),
    working_directory(_, Home),
    atom_concat(Home, '/src/metta.pl', Metta),
    ensure_loaded(Metta),
    retractall(silent(_)),
    assertz(silent(true)),
    retractall(working_dir(_)),
    assertz(working_dir(Home)),
    atom_concat(Home, '/repos/PLN', PlnDir),
    asserta(library_path(PlnDir)),
    loop.

loop :-
    read_line_to_string(current_input, Line),
    ( Line == end_of_file -> true
    ; Line == ">QUIT" -> true
    ; Line == ">BOOT" ->
        catch((boot_lib_pln, reply_ok([])), Error, reply_error(Error)),
        loop
    ; Line == ">RESET_STVS" ->
        catch((reset_stvs, reply_ok([])), Error, reply_error(Error)),
        loop
    ; Line == ">EVAL" ->
        catch((read_eval_block(Code), eval_code(Code, Results), reply_ok(Results)),
              Error, reply_error(Error)),
        loop
    ; reply_error(unknown_command),
      loop
    ).

boot_lib_pln :-
    getenv('PETTA_HOME', Home),
    atom_concat(Home, '/repos/PLN/lib_pln.metta', LibPln),
    load_metta_file(LibPln, _).

reset_stvs :-
    catch(retractall('STV'(_, _)), _, true).

read_eval_block(Code) :-
    read_eval_lines(Lines),
    atomic_list_concat(Lines, '\n', Code).

read_eval_lines(Lines) :-
    read_line_to_string(current_input, Line),
    ( Line == end_of_file -> Lines = []
    ; Line == ">END" -> Lines = []
    ; read_eval_lines(Rest),
      Lines = [Line|Rest]
    ).

eval_code(Code, ResultsR) :-
    process_metta_string(Code, Results),
    maplist(safe_swrite, Results, ResultsR).

safe_swrite(Term, String) :-
    catch(swrite(Term, String), _, term_string(Term, String)).

reply_ok(Lines) :-
    writeln('<OK'),
    maplist(write_result_line, Lines),
    writeln('<END'),
    flush_output.

write_result_line(Line) :-
    format('<~w~n', [Line]).

reply_error(Error) :-
    writeln('<ERR'),
    format('<~w~n', [Error]),
    writeln('<END'),
    flush_output.
