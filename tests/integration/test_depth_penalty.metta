;; PRISM Gate 3.1 Test: Depth Penalty Verification in MeTTa
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

;; Test Case: Shallow (depth 0, stamp (1)) vs Deep (depth 2, stamp (1 2 3)) with same statement & STV
!(let $goal (Inheritance A C)
   (let $s_shallow (Sentence ((Inheritance A B) (stv 0.9 0.8)) (1))
     (let $s_deep (Sentence ((Inheritance A B) (stv 0.9 0.8)) (1 2 3))
       (let $score_shallow (PriorityRankGoal $goal $s_shallow)
         (let $score_deep (PriorityRankGoal $goal $s_deep)
           (println! (DEPTH_PENALTY_VERIFICATION:
                       (shallow_score: $score_shallow)
                       (deep_score: $score_deep)
                       (if (> $score_shallow $score_deep) "PASS" "FAIL"))))))))
