;; PRISM Gate 1.4 Test: Goal-Directed Task Prioritization Hook
!(import! &self (library lib_import))
!(git-import! "https://github.com/trueagi-io/PLN.git")
!(import! &self (library PLN lib_pln))

;; Define a mini Knowledge Base with two competing paths:
;; Path 1 (Irrelevant): Animal -> LivingThing (high confidence 0.95, but irrelevant to goal)
;; Path 2 (Goal-relevant): Alice -> Person -> Mortal (moderate confidence 0.80, highly relevant to goal)

(= (STV Alice) (stv 0.1 1.0))
(= (STV Person) (stv 0.1 1.0))
(= (STV Mortal) (stv 0.1 1.0))
(= (STV Animal) (stv 0.1 1.0))
(= (STV LivingThing) (stv 0.1 1.0))

(= (test-kb) (
    (Sentence ((Inheritance Animal LivingThing) (stv 0.95 0.95)) (1))
    (Sentence ((Inheritance Alice Person) (stv 0.90 0.80)) (2))
    (Sentence ((Inheritance Person Mortal) (stv 0.90 0.80)) (3))
))

;; Goal is (Inheritance Alice Mortal)
;; Under unguided PLN (Goal = ()), (Inheritance Animal LivingThing) has confidence 0.95 vs 0.80,
;; so Animal->LivingThing would be selected first.
;; Under PRISM guidance, Alice->Person and Person->Mortal overlap with the goal (Alice, Mortal),
;; so PRISM scores them higher and selects them first!

!(let $goal (Inheritance Alice Mortal)
   (let $tasks (test-kb)
     (let $best-guided (BestCandidate (PriorityRankGoal $goal) () $tasks)
       (let $best-unguided (BestCandidate (PriorityRankGoal ()) () $tasks)
         (println! (HOOK_VERIFICATION:
                     (goal: $goal)
                     (unguided_pick_selected_raw_conf: $best-unguided)
                     (prism_guided_pick_selected_overlap: $best-guided)))))))
