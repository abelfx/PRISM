;; PRISM Gate 1.2 Test: Exception Safety and Fallback
;; Uses prism-score (our Prolog FFI bridge) instead of raw py-call

!(import! &self (library lib_import))
!(import_prolog_functions_from_file "prism/ffi/prism_ffi.pl" (prism-score))

(= (PriorityRankGoal $Goal ()) -99999.0)
(= (PriorityRankGoal $Goal (Sentence ($x (stv $f $c)) $Ev1))
   (if (== $Goal ())
       $c
       (let $score (prism-score (Sentence ($x (stv $f $c)) $Ev1) $Goal)
            (if (== $score Error)
                $c
                $score))))

;; Test Case 1: Empty Goal -> Falls back to raw confidence 0.77
!(let $s (Sentence ((Inheritance A B) (stv 0.9 0.77)) (1))
   (let $score (PriorityRankGoal () $s)
     (println! (FALLBACK_NO_GOAL: $score (if (== $score 0.77) "PASS" "FAIL")))))

;; Test Case 2: Active goal -> Scorer computes a positive score
!(let $s (Sentence ((Inheritance A B) (stv 0.9 0.85)) (1))
   (let $score (PriorityRankGoal (Inheritance A C) $s)
     (println! (GUIDED_SCORE: $score (if (> $score 0.0) "PASS" "FAIL")))))

;; Test Case 3: Empty item
!(let $score (PriorityRankGoal (Inheritance A C) ())
   (println! (EMPTY_ITEM_GUARD: $score (if (== $score -99999.0) "PASS" "FAIL"))))
