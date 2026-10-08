; Runs OpenPsi's real getApplicableActions/applyCurrentActions against a live space.
!(import! &self ../../../other_hyperon/PeTTa-OpenPSI/main/mind-agents/action-planner/action-planner-v2)
!(import! &self ../../../other_hyperon/PeTTa-OpenPSI/main/mind-agents/action-planner/prism-openpsi)

!(bind! &prismPsiRules (new-space))

!(add-atom &prismPsiRules
    ((: first ((TTV 1 (STV 0.8 0.7))
               (IMPLICATION_LINK (AND_LINK ((Goal init 0.9 0.6) explore))
                                 (Goal middle 1.0 1.0)))) 2))
!(add-atom &prismPsiRules
    ((: decoy ((TTV 1 (STV 0.9 0.9))
               (IMPLICATION_LINK (AND_LINK ((Goal init 0.9 0.6) idle))
                                 (Goal deadend 1.0 1.0)))) 9))
!(add-atom &prismPsiRules
    ((: second ((TTV 1 (STV 0.8 0.7))
                (IMPLICATION_LINK (AND_LINK ((Goal middle 0.9 0.6) finish))
                                  (Goal target 1.0 1.0)))) 2))

!(let $candidates (applyCurrentActions (getApplicableActions init &prismPsiRules)
                                       init () &prismPsiRules)
   (let $pick (prism-openpsi-best $candidates target
                   (collapse (get-atoms &prismPsiRules)) ())
        (println! (PRISM_OPENPSI_PICK $pick))))
!(let $candidates (applyCurrentActions (getApplicableActions init &prismPsiRules)
                                       init () &prismPsiRules)
   (let $pick (findMinDistance $candidates target 1000 () &prismPsiRules)
        (println! (OPENPSI_NATIVE_PICK $pick))))
!(let $candidates (applyCurrentActions (getApplicableActions init &prismPsiRules)
                                       init () &prismPsiRules)
   (let $pick (PRISM.OpenPsi.Select $candidates absent &prismPsiRules ())
        (let ($distance $native)
             (findMinDistance $candidates absent 1000 () &prismPsiRules)
             (if (== $pick $native)
                 (println! PRISM_OPENPSI_FALLBACK_PASS)
                 (println! PRISM_OPENPSI_FALLBACK_FAIL)))))
!(let $plan (PRISM.OpenPsi.Plan init target &prismPsiRules 4)
   (if (== $plan (explore finish))
       (println! PRISM_OPENPSI_PASS)
       (println! PRISM_OPENPSI_FAIL)))
!(let $plan (PRISM.OpenPsi.Plan init target &prismPsiRules 1)
   (if (== $plan ())
       (println! PRISM_OPENPSI_BUDGET_PASS)
       (println! PRISM_OPENPSI_BUDGET_FAIL)))
