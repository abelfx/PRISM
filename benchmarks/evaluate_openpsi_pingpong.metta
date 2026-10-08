; The two rule atoms are copied verbatim from PeTTa-OpenPSI's
; use-cases/ping-pong/test/ping-pong-v3-test.metta. Do not run its interactive
; mainLoop here; this isolates the repository-owned planning schema.
!(import! &self ../../other_hyperon/PeTTa-OpenPSI/main/mind-agents/action-planner/action-planner-v2)
!(import! &self ../../other_hyperon/PeTTa-OpenPSI/main/mind-agents/action-planner/prism-openpsi)
!(bind! &pingpongRules (new-space))

!(add-atom &pingpongRules
    ((: r_return
        ((TTV 0 (STV 1.0 1.0))
         (IMPLICATION_LINK
             (AND_LINK ((Goal (ball heading-to-agent) 1.0 1.0) act-ping))
             (Goal (ball heading-to-opponent) 1.0 1.0)))) 1.0))
!(add-atom &pingpongRules
    ((: r_wait
        ((TTV 0 (STV 1.0 1.0))
         (IMPLICATION_LINK
             (AND_LINK ((Goal (ball heading-to-opponent) 1.0 1.0) act-wait))
             (Goal (ball heading-to-agent) 1.0 1.0)))) 1.0))

!(let* (($actions (getApplicableActions (ball heading-to-agent) &pingpongRules))
        ($pairs (applyCurrentActions $actions (ball heading-to-agent) () &pingpongRules))
        (($nativeDistance $native) (findMinDistance $pairs (ball heading-to-opponent) 1000 () &pingpongRules))
        ($prism (PRISM.OpenPsi.Select $pairs (ball heading-to-opponent) &pingpongRules ())))
       (println! (PINGPONG_RESULT $actions $pairs $native $prism)))

!(let* (($actions (getApplicableActions (ball heading-to-agent) &pingpongRules))
        ($pairs (applyCurrentActions $actions (ball heading-to-agent) () &pingpongRules))
        (($nativeDistance $native) (findMinDistance $pairs (ball unknown) 1000 () &pingpongRules))
        ($prism (PRISM.OpenPsi.Select $pairs (ball unknown) &pingpongRules ())))
       (println! (PINGPONG_UNREACHABLE $native $prism)))
