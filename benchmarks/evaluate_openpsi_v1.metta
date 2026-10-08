; Diagnostic only: actual feedback-loop default v1 planner on repository rules.
!(import! &self ../../other_hyperon/PeTTa-OpenPSI/main/mind-agents/action-planner/action-planner-v2)
!(import! &self ../../other_hyperon/PeTTa-OpenPSI/main/mind-agents/action-planner/action-planner-v1)
!(import! &self ../../other_hyperon/PeTTa-OpenPSI/main/mind-agents/action-planner/prism-openpsi)

!(bind! &openpsiV1Rules (new-space))
!(addRulesToSpace &openpsiV1Rules)

; Replay through OpenPsi's own action application; a list of actions alone
; does not prove that the planner reached the requested goal.
(= (OpenPsiV1.Replay $plan $state $goal $space)
   (if (== $plan ())
       (== $state $goal)
       (let* (($action (car-atom $plan))
              ($rest (cdr-atom $plan))
              ($successors (applyCurrentActions ($action) $state () $space)))
             (if (== $successors ())
                 False
                 (let* (($pair (car-atom $successors))
                        (($next) (cdr-atom $pair)))
                       (OpenPsiV1.Replay $rest $next $goal $space))))))

!(let $plan (planner &openpsiV1Rules Conversation-Started Receive-User-Response)
   (let $_ (println! (OPENPSI_V1_SHORT_PLAN $plan))
        (println! (OPENPSI_V1_SHORT_VALID
                    (OpenPsiV1.Replay $plan Conversation-Started
                                      Receive-User-Response &openpsiV1Rules)))))
!(let $plan (planner &openpsiV1Rules Conversation-Started Understand-User-Interests)
   (let $_ (println! (OPENPSI_V1_DEEP_PLAN $plan))
        (println! (OPENPSI_V1_DEEP_VALID
                    (OpenPsiV1.Replay $plan Conversation-Started
                                      Understand-User-Interests &openpsiV1Rules)))))
!(let $plan (PRISM.OpenPsi.Plan Conversation-Started Understand-User-Interests
                                 &openpsiV1Rules 15)
   (let $_ (println! (OPENPSI_PRISM_DEEP_PLAN $plan))
        (println! (OPENPSI_PRISM_DEEP_VALID
                    (OpenPsiV1.Replay $plan Conversation-Started
                                      Understand-User-Interests &openpsiV1Rules)))))
