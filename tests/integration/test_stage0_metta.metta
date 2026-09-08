!(import! &self (library lib_import))
!(import_prolog_functions_from_file "prism/ffi/prism_ffi.pl" (prism-score prism-filter-beliefs))

(= (PremiseFilter $Candidate $Goal $Beliefs)
   (if (or (== $Goal ()) (== $Candidate ()))
       $Beliefs
       (let $filtered (prism-filter-beliefs $Candidate $Goal $Beliefs)
            (if (or (== $filtered Error) (== $filtered ()))
                $Beliefs
                $filtered))))

;; Test Case 1: Unguided / Empty Goal returns all beliefs untouched
!(let $cand (Sentence ((Inheritance A B) (stv 0.9 0.9)) (1))
   (let $beliefs ((Sentence ((Inheritance B C) (stv 0.9 0.9)) (2))
                  (Sentence ((Inheritance X Y) (stv 0.9 0.9)) (3)))
     (let $res (PremiseFilter $cand () $beliefs)
       (println! (STAGE0_TEST1_NO_GOAL: $res (if (== $res $beliefs) "PASS" "FAIL"))))))

;; Test Case 2: Guided with Goal and Candidate filters out distractor
!(let $cand (Sentence ((Inheritance A B) (stv 0.9 0.9)) (1))
   (let $goal (Inheritance A C)
     (let $b_on (Sentence ((Inheritance B C) (stv 0.9 0.9)) (2))
       (let $b_dist (Sentence ((Inheritance Distractor1 Distractor2) (stv 0.9 0.9)) (3))
         (let $beliefs ($b_on $b_dist)
           (let $res (PremiseFilter $cand $goal $beliefs)
             (println! (STAGE0_TEST2_FILTERED: $res (if (== $res ($b_on)) "PASS" "FAIL")))))))))
