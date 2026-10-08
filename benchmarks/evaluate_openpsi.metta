; Matched selector evaluation over PeTTa-OpenPSI's native rule matching and
; action application. Both modes use exactly the same bounded traversal.
!(import! &self ../../other_hyperon/PeTTa-OpenPSI/main/mind-agents/action-planner/action-planner-v2)
!(import! &self ../../other_hyperon/PeTTa-OpenPSI/main/mind-agents/action-planner/action-planner-v1)
!(import! &self ../../other_hyperon/PeTTa-OpenPSI/main/mind-agents/action-planner/prism-openpsi)

(= (OpenPsiEval.AddRule $space $id $from $action $to $weight)
   (add-atom $space
       ((: $id ((TTV 1 (STV 0.8 0.7))
                 (IMPLICATION_LINK (AND_LINK ((Goal $from 0.9 0.6) $action))
                                   (Goal $to 1.0 1.0)))) $weight)))

(= (OpenPsiEval.AddDecoys $space $n)
   (if (<= $n 0)
       ()
       (let $_ (OpenPsiEval.AddRule $space $n init $n $n 9)
            (OpenPsiEval.AddDecoys $space (- $n 1)))))

(= (OpenPsiEval.Select $mode $candidates $goal $space $visited)
   (if (== $mode PRISM)
       (PRISM.OpenPsi.Select $candidates $goal $space $visited)
       (let ($distance $nativePair)
            (findMinDistance $candidates $goal 1000 () $space)
            $nativePair)))

(= (OpenPsiEval.Plan $mode $state $goal $space $budget $visited $steps)
   (if (== $state $goal)
       (Result Success $steps)
       (if (<= $budget 0)
           (Result Budget $steps)
           (let* (($actions (getApplicableActions $state $space))
                  ($candidates (applyCurrentActions $actions $state () $space))
                  ($pick (OpenPsiEval.Select $mode $candidates $goal $space $visited)))
                 (if (== $pick ())
                     (Result DeadEnd $steps)
                     (let* (($action (car-atom $pick))
                            (($next) (cdr-atom $pick)))
                           (if (is-member $next $visited)
                               (Result Cycle $steps)
                               (OpenPsiEval.Plan $mode $next $goal $space
                                                 (- $budget 1)
                                                 (cons-atom $state $visited)
                                                 (+ $steps 1)))))))))

(= (OpenPsiEval.Run $case $mode $space $state $goal $budget)
   (let* (($start (py-call (time.perf_counter)))
          ($result (OpenPsiEval.Plan $mode $state $goal $space $budget () 0))
          ($end (py-call (time.perf_counter))))
         (println! (OPENPSI_EVAL $case $mode $result (- $end $start)))))

(= (OpenPsiEval.Paired $case $space $state $goal $budget $repeats)
   (if (<= $repeats 0)
       ()
       (let* (($_ (OpenPsiEval.Run $case Native $space $state $goal $budget))
              ($_ (OpenPsiEval.Run $case PRISM $space $state $goal $budget)))
             (OpenPsiEval.Paired $case $space $state $goal $budget (- $repeats 1)))))

(= (OpenPsiEval.Goals $goals $space)
   (if (== $goals ())
       ()
       (let* (($goal (car-atom $goals))
              ($rest (cdr-atom $goals))
              ($_ (OpenPsiEval.Paired $goal $space Conversation-Started $goal 15 3)))
             (OpenPsiEval.Goals $rest $space))))

(= (OpenPsiEval.CopyRules $rules $target)
   (if (== $rules ())
       ()
       (let* (($rule (car-atom $rules))
              ($rest (cdr-atom $rules))
              ($_ (add-atom $target $rule)))
             (OpenPsiEval.CopyRules $rest $target))))

; Trigger Janus/Python module loading outside timed observations.
!(bind! &openpsiWarmup (new-space))
!(OpenPsiEval.AddRule &openpsiWarmup direct init finish target 1)
!(OpenPsiEval.Run warmup PRISM &openpsiWarmup init target 4)

; Direct one-step case: both should succeed. This exposes pure ranking overhead.
!(bind! &openpsiDirect (new-space))
!(OpenPsiEval.AddRule &openpsiDirect direct init finish target 1)
!(OpenPsiEval.Paired direct &openpsiDirect init target 4 20)

; Unreachable goal: PRISM must fall back and cannot improve the outcome.
!(bind! &openpsiMissing (new-space))
!(OpenPsiEval.AddRule &openpsiMissing only init idle deadend 1)
!(OpenPsiEval.Paired missing &openpsiMissing init target 4 20)

; A real two-action route hidden by locally tied, goal-irrelevant rules.
!(bind! &openpsiNoisy (new-space))
!(OpenPsiEval.AddRule &openpsiNoisy first init explore middle 2)
!(OpenPsiEval.AddRule &openpsiNoisy second middle finish target 2)
!(OpenPsiEval.AddDecoys &openpsiNoisy 5)
!(OpenPsiEval.Paired noisy5 &openpsiNoisy init target 4 20)

!(bind! &openpsiNoisy20 (new-space))
!(OpenPsiEval.AddRule &openpsiNoisy20 first init explore middle 2)
!(OpenPsiEval.AddRule &openpsiNoisy20 second middle finish target 2)
!(OpenPsiEval.AddDecoys &openpsiNoisy20 20)
!(OpenPsiEval.Paired noisy20 &openpsiNoisy20 init target 4 20)

!(bind! &openpsiNoisy50 (new-space))
!(OpenPsiEval.AddRule &openpsiNoisy50 first init explore middle 2)
!(OpenPsiEval.AddRule &openpsiNoisy50 second middle finish target 2)
!(OpenPsiEval.AddDecoys &openpsiNoisy50 50)
!(OpenPsiEval.Paired noisy50 &openpsiNoisy50 init target 4 20)

; The repository's own conversation-rule graph, not generated benchmark facts.
!(bind! &openpsiConversation (new-space))
!(addRulesToSpace &openpsiConversation)
!(OpenPsiEval.Paired conversation2 &openpsiConversation Conversation-Started Receive-User-Response 10 5)
!(OpenPsiEval.Paired conversationDeep &openpsiConversation Conversation-Started Understand-User-Interests 15 5)
!(let $plan (PRISM.OpenPsi.Plan Conversation-Started Understand-User-Interests
                                 &openpsiConversation 15)
   (println! (OPENPSI_CONVERSATION_PLAN $plan)))

; Prespecified reachable targets from the repository's conversation rules.
!(OpenPsiEval.Goals
  (Send-Greeting Receive-User-Response Understand-Initial-Mood
   Understand-Initial-Context Explore-Mood-Details Ask-Daily-Activities
   Learn-Activity-Details Understand-Hobby-Preferences Understand-Future-Goals
   Summarize-User-Preferences Understand-User-Interests Ask-Recent-Events
   Learn-Recent-Event-Details Understand-Event-Impact Explore-Event-Emotions
   Understand-Event-Significance Propose-Related-Topics Receive-Topic-Choice
   Discuss-Chosen-Topic Off-Topic-Discussion Irrelevant-Topic)
  &openpsiConversation)

; Same repository rules in reverse insertion order: selection-order probe.
!(bind! &openpsiConversationReverse (new-space))
!(OpenPsiEval.CopyRules (reverse (collapse (get-atoms &openpsiConversation)) ())
                         &openpsiConversationReverse)
!(OpenPsiEval.Paired reverseDeep &openpsiConversationReverse
                          Conversation-Started Understand-User-Interests 15 5)
!(OpenPsiEval.Paired reverseOffTopic &openpsiConversationReverse
                          Conversation-Started Off-Topic-Discussion 15 5)
