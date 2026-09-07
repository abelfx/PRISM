;; PRISM Gate 1.2 Test: Exception Safety and Fallback

(= (PriorityRankGoal $Goal ()) -99999.0)
(= (PriorityRankGoal $Goal (Sentence ($x (stv $f $c)) $Ev1))
   (if (== $Goal ())
       $c
       (let $score (py-call (scorer.score_candidate (Sentence ($x (stv $f $c)) $Ev1) $Goal))
            (if (== $score Error)
                $c
                $score))))

;; Test Case 1: Empty Goal -> Falls back to raw confidence 0.77
!(let $s (Sentence ((Inheritance A B) (stv 0.9 0.77)) (1))
   (let $score (PriorityRankGoal () $s)
     (println! (FALLBACK_NO_GOAL: $score (if (== $score 0.77) "PASS" "FAIL")))))

;; Test Case 2: Malformed sentence with goal -> Scorer catches exception and returns float or "Error" which falls back to $c
!(let $s (Sentence ((Inheritance A B) (stv 0.9 0.85)) (1))
   (let $score (PriorityRankGoal (Inheritance A C) $s)
     (println! (GUIDED_SCORE: $score (if (> $score 0.0) "PASS" "FAIL")))))

;; Test Case 3: Empty item
!(let $score (PriorityRankGoal (Inheritance A C) ())
   (println! (EMPTY_ITEM_GUARD: $score (if (== $score -99999.0) "PASS" "FAIL"))))
