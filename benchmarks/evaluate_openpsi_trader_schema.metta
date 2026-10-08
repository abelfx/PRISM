; Negative compatibility probe: load the repository's actual trader schemas.
; The current OpenPsi adapter is for IMPLICATION_LINK/Goal-state rules, while
; the trader uses IMPLICATION with Context/Action and Goal(STV ...).
!(import! &self ../../other_hyperon/PeTTa-OpenPSI/main/mind-agents/action-planner/action-planner-v2)
!(import! &self ../../other_hyperon/PeTTa-OpenPSI/main/mind-agents/action-planner/prism-openpsi)
!(import! &self ../../other_hyperon/PeTTa-OpenPSI/use-cases/metta-trader/schemas)
!(bind! &traderRules (new-space))
!(initializeSpace &traderRules)
!(let* (($rules (collapse (get-atoms &traderRules)))
        ($actions (getApplicableActions (PLANET A) &traderRules))
        ($candidates (applyCurrentActions $actions (PLANET A) () &traderRules))
        ($prism (PRISM.OpenPsi.Select $candidates (PLANET B) &traderRules ())))
       (println! (TRADER_SCHEMA_RESULT (size-atom $rules) $actions $candidates $prism)))
