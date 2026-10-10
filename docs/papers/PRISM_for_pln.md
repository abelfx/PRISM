# PRISM — Implementation Specification

**Programmable Reduction & Inference Search Manager**
**Implementation Companion to the PRISM Proposal (rev. 4)**

---

## Table of Contents

1. [Scope & Conventions](#1-scope--conventions)
2. [Baseline: How PLN Works Today (Exact Code Walk)](#2-baseline-how-pln-works-today)
3. [Modification 1: Goal-Threading ($Goal Parameter)](#3-modification-1-goal-threading)
4. [Modification 2: The PriorityRank / PriorityRankNeg Hook](#4-modification-2-the-priorityrank-hook)
5. [Stage 0: Indexed Premise Pre-Filter](#5-stage-0-indexed-premise-pre-filter)
6. [Tier 1: Fast Heuristic Scorer](#6-tier-1-fast-heuristic-scorer)
7. [Tier 2: Strategic LLM Reasoner](#7-tier-2-strategic-llm-reasoner)
8. [The Search Algorithm: Learned A*](#8-the-search-algorithm-learned-a)
9. [Bidirectional Search & Meet-in-the-Middle](#9-bidirectional-search--meet-in-the-middle)
10. [Score Memoization & FFI Caching](#10-score-memoization--ffi-caching)
11. [Python Scorer Module (`scorer.py`)](#11-python-scorer-module)
12. [Evaluation Harness & Benchmarks](#12-evaluation-harness--benchmarks)
13. [File Manifest & Directory Layout](#13-file-manifest--directory-layout)
14. [Week-by-Week Build Order](#14-week-by-week-build-order)

---

## 1. Scope & Conventions

**What this document is:**
A line-level implementation specification for PRISM. Every MeTTa modification references the exact function name and line number in `trueagi-io/PLN/lib_pln.metta` (tag `v0.9`, commit `4405956`). Every Python module is specified with its interface, data structures, and algorithmic pseudocode.

**What this document is not:**
A re-explanation of the research motivation. For that, see the PRISM Proposal (rev. 4).

**File references:**
- `lib_pln.metta` always means `PLN/lib_pln.metta` in the `trueagi-io/PLN` repository.
- Line numbers are from tag `v0.9`.

**Notation:**
- `STV(s, c)` = Simple Truth Value with strength `s` and confidence `c`.
- `$` prefix = MeTTa variable.
- `Sentence` = PLN's internal unit: `(Sentence (<statement> (stv <s> <c>)) <evidence-stamp>)`.

---

## 2. Baseline: How PLN Works Today

### 2.1 The Derivation Loop (`PLN.Derive`)

**Location:** `lib_pln.metta:377–397`

PLN's core inference engine is a single recursive MeTTa function. Here is its exact structure, annotated:

```metta
;; lib_pln.metta:377-397  (verbatim, with annotations)

(= (PLN.Derive $Tasks $Beliefs $steps $maxsteps $taskqueuesize $beliefqueuesize)

   ;; STEP 1: Termination check
   (if (or (> $steps $maxsteps) (== $Tasks ()))
       ($Tasks $Beliefs)                    ;; Return current state

       ;; STEP 2: Select the highest-priority task from the task queue
       (let (Sentence $x $Ev1) (BestCandidate PriorityRank () $Tasks)

            ;; STEP 3: Generate all derivations of this task against all beliefs
            (let $derivations
                 (collapse
                   (superpose
                     (;; 3a: Binary rules — try selected task against EVERY belief
                      (let* (((Sentence $y $Ev2) (superpose $Beliefs)))
                            (if (StampDisjoint $Ev1 $Ev2)
                                (let $stamp (msort (append $Ev1 $Ev2))
                                     (superpose
                                       ((case (|- $x $y)
                                              ((($Txy $TVxy)
                                                (Sentence ($Txy $TVxy) $stamp))))
                                        (case (|- $y $x)
                                              ((($Tyx $TVyx)
                                                (Sentence ($Tyx $TVyx) $stamp)))))))
                                (empty)))
                      ;; 3b: Unary rules — try selected task alone
                      (case (|- $x) ((($T3 $TV3) (Sentence ($T3 $TV3) $Ev1)))))))

                 ;; STEP 4: Merge derivations into queues and prune to size limits
                 (progn
                   (println! (SELECTED (Sentence $x $Ev1)))
                   (PLN.Derive
                     (LimitSize
                       (exclude-item (Sentence $x $Ev1)
                                     (ConcatUnique $Tasks $derivations))
                       $taskqueuesize)
                     (LimitSize (ConcatUnique $Beliefs $derivations)
                                $beliefqueuesize)
                     (+ $steps 1) $maxsteps
                     $taskqueuesize $beliefqueuesize))))))
```

### 2.2 Task Selection: `BestCandidate` + `PriorityRank`

**Location:** `lib_pln.metta:350–363`

```metta
;; lib_pln.metta:351-359 — generic linear-scan priority queue
(= (BestCandidate $evaluateCandidateFunction $bestCandidate $tuple)
   (if (== $tuple ())
       $bestCandidate
       (let* (($head (car-atom $tuple))
              ($tail (cdr-atom $tuple)))
             (if (> ($evaluateCandidateFunction $head)
                    ($evaluateCandidateFunction $bestCandidate))
                 (BestCandidate $evaluateCandidateFunction $head $tail)
                 (BestCandidate $evaluateCandidateFunction $bestCandidate $tail)))))

;; lib_pln.metta:362-363 — the scoring function (PRISM's target)
(= (PriorityRank (Sentence ($x (stv $f $c)) $Ev1)) $c)   ;; ← returns raw confidence
(= (PriorityRank ()) -99999.0)                             ;; ← base case for empty
```

**Critical observation:** `BestCandidate` takes its scoring function as a *first-class parameter* (`$evaluateCandidateFunction`). This is what makes the hook possible — `PriorityRank` is passed by name, not inlined.

### 2.3 Queue Pruning: `LimitSize` + `PriorityRankNeg`

**Location:** `lib_pln.metta:366–374`

```metta
;; lib_pln.metta:366-367 — negated priority (find the WORST item to evict)
(= (PriorityRankNeg (Sentence ($x (stv $f $c)) $Ev1)) (- 0.0 $c))
(= (PriorityRankNeg ()) -99999.0)

;; lib_pln.metta:370-374 — trim queue to size by evicting lowest-priority items
(= (LimitSize $L $size)
   (if (< (length $L) $size)
       $L
       (let $lowestPriorityItem (BestCandidate PriorityRankNeg () $L)
            (LimitSize (exclude-item $lowestPriorityItem $L) $size))))
```

**Performance note:** `LimitSize` calls `BestCandidate PriorityRankNeg` once per evicted item. If the queue has `N` items and the limit is `K`, this performs `(N - K)` full linear scans, each calling `PriorityRankNeg` on every remaining item. Total calls to `PriorityRankNeg`: **O((N − K) × N)**. If `PriorityRankNeg` crosses an FFI boundary on every call, this becomes the dominant cost. See [§10](#10-score-memoization--ffi-caching).

### 2.4 The Query Interface: `PLN.Query`

**Location:** `lib_pln.metta:416–431`

```metta
;; lib_pln.metta:416-421
(= (PLN.Query $Tasks $Beliefs $term $maxsteps $taskqueuesize $beliefqueuesize)
   (BestConfidenceCandidate
    (collapse
      (let ($TasksRet $BeliefsRet)
           (PLN.Derive $Tasks $Beliefs $maxsteps $taskqueuesize $beliefqueuesize)
           (case (superpose $BeliefsRet)
                 (((Sentence ($Term $TV) $Ev)
                   (case (== $Term $term)
                         ((True ($TV $Ev)))))))))))
```

**The goal-blindness bug:** `$term` is available here but is **never passed** to `PLN.Derive`. The derivation engine runs with zero knowledge of what conclusion is being sought. All goal-filtering happens *after* derivation completes, by scanning the belief buffer for `$Term == $term`.

---

## 3. Modification 1: Goal-Threading

### 3.1 Design Decision: Optional Parameter with Arity Overloading

The `$Goal` parameter is added as an **optional trailing argument** using MeTTa's arity-based dispatch. Existing callers that don't supply a goal continue to work unchanged.

### 3.2 Modified `PLN.Query`

```metta
;; PRISM — Modified PLN.Query: now forwards $term as $Goal into PLN.Derive
(= (PLN.Query $Tasks $Beliefs $term $maxsteps $taskqueuesize $beliefqueuesize)
   (BestConfidenceCandidate
    (collapse
      (let ($TasksRet $BeliefsRet)
           ;; ↓↓↓ NEW: pass $term as the 7th argument (the Goal) ↓↓↓
           (PLN.Derive $Tasks $Beliefs $maxsteps $taskqueuesize $beliefqueuesize $term)
           (case (superpose $BeliefsRet)
                 (((Sentence ($Term $TV) $Ev)
                   (case (== $Term $term)
                         ((True ($TV $Ev)))))))))))

;; Convenience overloads — unchanged signatures, unchanged behavior
(= (PLN.Query $kb $term $maxsteps $taskqueuesize $beliefqueuesize)
   (PLN.Query $kb $kb $term $maxsteps $taskqueuesize $beliefqueuesize))

(= (PLN.Query $kb $term $maxsteps)
   (PLN.Query $kb $term $maxsteps (PLN.Config.TaskQueueSize) (PLN.Config.BeliefQueueSize)))

(= (PLN.Query $kb $term)
   (PLN.Query $kb $term (PLN.Config.MaxSteps)))
```

### 3.3 Modified `PLN.Derive`

```metta
;; PRISM — Legacy 6-arg overload: defaults $Goal to () (undirected mode)
(= (PLN.Derive $Tasks $Beliefs $steps $maxsteps $taskqueuesize $beliefqueuesize)
   (PLN.Derive $Tasks $Beliefs $steps $maxsteps $taskqueuesize $beliefqueuesize ()))

;; PRISM — New 7-arg signature: goal-aware derivation
(= (PLN.Derive $Tasks $Beliefs $steps $maxsteps $taskqueuesize $beliefqueuesize $Goal)
   (if (or (> $steps $maxsteps) (== $Tasks ()))
       ($Tasks $Beliefs)
       ;; ↓↓↓ CHANGE: PriorityRank now receives $Goal ↓↓↓
       (let (Sentence $x $Ev1) (BestCandidate (PriorityRankGoal $Goal) () $Tasks)
            (let $derivations
                 (collapse
                   (superpose
                     ((let* (((Sentence $y $Ev2) (superpose $Beliefs)))
                            (if (StampDisjoint $Ev1 $Ev2)
                                (let $stamp (msort (append $Ev1 $Ev2))
                                     (superpose
                                       ((case (|- $x $y)
                                              ((($Txy $TVxy) (Sentence ($Txy $TVxy) $stamp))))
                                        (case (|- $y $x)
                                              ((($Tyx $TVyx) (Sentence ($Tyx $TVyx) $stamp)))))))
                                (empty)))
                      (case (|- $x) ((($T3 $TV3) (Sentence ($T3 $TV3) $Ev1)))))))
                 (progn (println! (SELECTED (Sentence $x $Ev1)))
                        (PLN.Derive
                          ;; ↓↓↓ CHANGE: LimitSize also uses goal-aware pruning ↓↓↓
                          (LimitSizeGoal
                            (exclude-item (Sentence $x $Ev1)
                                          (ConcatUnique $Tasks $derivations))
                            $taskqueuesize $Goal)
                          (LimitSizeGoal
                            (ConcatUnique $Beliefs $derivations)
                            $beliefqueuesize $Goal)
                          (+ $steps 1) $maxsteps
                          $taskqueuesize $beliefqueuesize
                          $Goal))))))                ;; ↓↓↓ $Goal threaded to recursion

;; Convenience overloads that feed into the 7-arg version
(= (PLN.Derive $Tasks $Beliefs $maxsteps $taskqueuesize $beliefqueuesize)
   (PLN.Derive $Tasks $Beliefs 1 $maxsteps $taskqueuesize $beliefqueuesize ()))

(= (PLN.Derive $Tasks $Beliefs $maxsteps $taskqueuesize $beliefqueuesize $Goal)
   (PLN.Derive $Tasks $Beliefs 1 $maxsteps $taskqueuesize $beliefqueuesize $Goal))

(= (PLN.Derive $Tasks $Beliefs $maxsteps)
   (PLN.Derive $Tasks $Beliefs $maxsteps (PLN.Config.TaskQueueSize)
                                          (PLN.Config.BeliefQueueSize)))

(= (PLN.Derive $Tasks $Beliefs)
   (PLN.Derive $Tasks $Beliefs (PLN.Config.MaxSteps)))
```

### 3.4 Why `PriorityRankGoal` Instead of Modifying `PriorityRank` In-Place

`BestCandidate` calls its scoring function as `($evaluateCandidateFunction $head)` — it passes **one argument** (the candidate). But our scorer needs **two** arguments (the candidate + the goal).

Solution: **partial application via a wrapper.** `(PriorityRankGoal $Goal)` returns a *function* that, when applied to a Sentence by `BestCandidate`, calls the scorer with both the Sentence and the captured `$Goal`:

```metta
;; PRISM — Goal-curried scoring function for BestCandidate
;; BestCandidate calls: ($evaluateCandidateFunction $head)
;; With $evaluateCandidateFunction = (PriorityRankGoal $Goal),
;; this evaluates as: ((PriorityRankGoal $Goal) $head) = (PriorityRankGoal $Goal $head)

;; Base case: empty candidate
(= ((PriorityRankGoal $Goal) ()) -99999.0)

;; Sentence with goal: call Python scorer via py.call
(= ((PriorityRankGoal $Goal) (Sentence ($x (stv $f $c)) $Ev1))
   (if (== $Goal ())
       $c     ;; No goal supplied → fall back to raw confidence (undirected mode)
       (let $score (py.call scorer score_candidate
                           (Sentence ($x (stv $f $c)) $Ev1) $Goal)
            (if (== $score Error)
                $c     ;; Python error → graceful fallback to raw confidence
                $score))))

;; Negated version for LimitSize (evicts lowest-scored items)
(= ((PriorityRankNegGoal $Goal) ()) -99999.0)

(= ((PriorityRankNegGoal $Goal) (Sentence ($x (stv $f $c)) $Ev1))
   (- 0.0 ((PriorityRankGoal $Goal) (Sentence ($x (stv $f $c)) $Ev1))))
```

### 3.5 Modified `LimitSize`

```metta
;; PRISM — Goal-aware queue pruning
(= (LimitSizeGoal $L $size $Goal)
   (if (< (length $L) $size)
       $L
       (let $lowestPriorityItem (BestCandidate (PriorityRankNegGoal $Goal) () $L)
            (LimitSizeGoal (exclude-item $lowestPriorityItem $L) $size $Goal))))
```

---

## 4. Modification 2: The PriorityRank Hook

### 4.1 What Changes in `lib_pln.metta`

| Original (lib_pln.metta) | PRISM Replacement | Lines Affected |
|---|---|---|
| `PriorityRank` (2 clauses) | `PriorityRankGoal` (2 clauses + py.call) | 362–363 |
| `PriorityRankNeg` (2 clauses) | `PriorityRankNegGoal` (2 clauses, wrapping above) | 366–367 |
| `LimitSize` (1 function) | `LimitSizeGoal` (1 function, uses above) | 370–374 |
| `PLN.Derive` 6-arg (1 function) | `PLN.Derive` 7-arg + 6-arg legacy overload | 377–397 |
| `PLN.Query` (1 function) | Modified to pass `$term` as `$Goal` | 416–421 |

### 4.2 What Does NOT Change

- **All inference rules** (`|-` clauses, lines 210–323): Untouched.
- **All truth-value formulas** (`Truth_Deduction`, `Truth_Induction`, etc., lines 65–205): Untouched.
- **`BestCandidate`** (lines 351–359): Untouched — it already accepts any scoring function.
- **`StampDisjoint`**, **`ConcatUnique`**, and all utility functions: Untouched.
- **All existing examples and tests**: Work unchanged via the 6-arg legacy overload.

---

## 5. Stage 0: Indexed Premise Pre-Filter

### 5.1 Status: Conditional (Not Built Upfront)

Stage 0 modifies the `(superpose $Beliefs)` call inside `PLN.Derive` (line 382). Unlike the PriorityRank hook (which is a drop-in replacement outside the derivation body), Stage 0 changes the derivation body itself. It is built **only if** Week 1–2 benchmarks show that frontier size on the KG multi-hop domain actually reaches problematic levels.

### 5.2 Design (If Built)

**Index structure:** A Python-side dictionary mapping structural keys to lists of Sentence atoms.

```python
# prism/stage0_index.py

from collections import defaultdict

class PremiseIndex:
    """
    Indexes beliefs by their structural pattern for fast backward lookup.

    Key: (link_type, target_concept) — e.g., ("Inheritance", "Bird")
    Value: list of Sentence atoms whose statement matches that pattern
    """

    def __init__(self):
        self._index = defaultdict(list)

    def add(self, sentence):
        """Index a Sentence by its structural pattern."""
        statement = sentence.statement  # e.g., (Inheritance Raven Bird)
        if len(statement) >= 3:
            link_type = statement[0]     # "Inheritance"
            # Index by (link_type, second_arg) and (link_type, third_arg)
            self._index[(link_type, statement[1])].append(sentence)
            self._index[(link_type, statement[2])].append(sentence)

    def lookup(self, goal, rule_type="deduction"):
        """
        Given a goal like (Inheritance A C), find beliefs that could
        participate in a deduction chain toward it.

        For deduction (A→B, B→C ⊢ A→C):
          - Find beliefs matching (Inheritance A $B) — shares first arg with goal
          - Find beliefs matching (Inheritance $B C) — shares second arg with goal
        """
        if len(goal) < 3:
            return []

        link_type = goal[0]
        candidates_left  = self._index.get((link_type, goal[1]), [])
        candidates_right = self._index.get((link_type, goal[2]), [])
        return candidates_left + candidates_right

    def rebuild(self, all_beliefs):
        """Rebuild the index from scratch (called when beliefs change significantly)."""
        self._index.clear()
        for sentence in all_beliefs:
            self.add(sentence)
```

### 5.3 MeTTa Integration (If Built)

The `(superpose $Beliefs)` call at line 382 would be conditionally replaced:

```metta
;; Instead of: (superpose $Beliefs)
;; Use:
(superpose (if (== $Goal ())
               $Beliefs                                     ;; undirected: scan all
               (py.call stage0_index lookup_beliefs ($Goal $Beliefs))))  ;; goal-aware: indexed
```

---

## 6. Tier 1: Fast Heuristic Scorer

### 6.1 v1: Symbolic/Structural Heuristic (Weeks 3–6)

No training data required. Computes a score based on three signals:

#### Signal 1: Structural Overlap with Goal

**Definition:** Let `S` be the candidate statement and `G` be the goal statement. The structural overlap is the fraction of atoms in `G` that also appear in `S`.

```
overlap(S, G) = |atoms(S) ∩ atoms(G)| / |atoms(G)|
```

**Example:**
- Candidate: `(Inheritance Alice Ancestor-of-Bob)`
- Goal: `(Inheritance Alice Ancestor-of-Carol)`
- `atoms(S) = {Inheritance, Alice, Ancestor-of-Bob}`
- `atoms(G) = {Inheritance, Alice, Ancestor-of-Carol}`
- `overlap = |{Inheritance, Alice}| / |{Inheritance, Alice, Ancestor-of-Carol}| = 2/3 ≈ 0.667`

#### Signal 2: Expected Confidence of Result

**Definition:** For a candidate with premise truth values `(stv s₁ c₁)` and `(stv s₂ c₂)`, the expected conclusion confidence is bounded above by:

```
expected_confidence ≤ min(c₁, c₂)
```

This is a conservative estimate: actual PLN formulas (e.g., `Truth_Deduction`) always produce a conclusion confidence ≤ the minimum of the premise confidences.

#### Signal 3: Chain-Distance Discount

**Definition:** For a candidate at derivation depth `d`, apply a geometric discount:

```
depth_discount = γ^d     where γ = 0.9 (tunable)
```

#### Combined Score (v1)

```
score_v1(candidate, goal) = α · overlap(S, G)
                          + β · expected_confidence
                          + δ · depth_discount
```

Where `α = 0.5`, `β = 0.3`, `δ = 0.2` are tunable weights.

### 6.2 v1 Python Implementation

```python
# prism/tier1_v1.py — Symbolic/structural heuristic scorer

def atomize(expr):
    """Extract individual atom names from a MeTTa expression."""
    if isinstance(expr, str):
        return {expr}
    if isinstance(expr, (list, tuple)):
        atoms = set()
        for sub in expr:
            atoms |= atomize(sub)
        return atoms
    return {str(expr)}

def structural_overlap(statement, goal):
    """Fraction of goal atoms present in the candidate statement."""
    s_atoms = atomize(statement)
    g_atoms = atomize(goal)
    if not g_atoms:
        return 0.0
    return len(s_atoms & g_atoms) / len(g_atoms)

def expected_confidence(stv):
    """Conservative upper bound on conclusion confidence."""
    return stv[1]  # confidence component

def score_candidate(sentence, goal, depth=0,
                    alpha=0.5, beta=0.3, delta=0.2, gamma=0.9):
    """
    Tier 1 v1 scoring function.

    Parameters
    ----------
    sentence : tuple — (statement, (stv, strength, confidence), evidence_stamp)
    goal     : tuple — the target statement (e.g., (Inheritance Alice Ancestor-of-Carol))
    depth    : int   — current derivation depth
    alpha, beta, delta : float — weight parameters
    gamma    : float — depth discount factor

    Returns
    -------
    float — score (higher = more promising)
    """
    statement = sentence[0]
    stv = sentence[1]  # (stv, strength, confidence)

    overlap = structural_overlap(statement, goal)
    conf    = expected_confidence(stv)
    disc    = gamma ** depth

    return alpha * overlap + beta * conf + delta * disc
```

### 6.3 v2: Trained Embedding / GNN Model (Week 11)

Built once search traces from Weeks 5–10 provide training data.

#### Training Data Format

Each training example is a tuple:

```
(candidate_sentence, goal, outcome)
```

Where `outcome ∈ {1, 0}`:
- `1` = this candidate was on a path that reached the goal
- `0` = this candidate was explored but led to a dead end

#### Model Architecture (v2)

```
Input: [candidate_embedding ⊕ goal_embedding ⊕ stv_features]
   ↓
Dense(128, ReLU)
   ↓
Dense(64, ReLU)
   ↓
Dense(1, Sigmoid) → score ∈ [0, 1]
```

- **Candidate/Goal embedding:** Atom names are mapped to learned embeddings (initialized from atom2vec or random).
- **STV features:** `[strength, confidence, depth, queue_position]` — 4 floats.
- **Training:** Binary cross-entropy loss, Adam optimizer.
- **Inference latency target:** < 0.5ms per candidate on CPU (a single forward pass through a 3-layer MLP).

---

## 7. Tier 2: Strategic LLM Reasoner

### 7.1 When Tier 2 Is Invoked

Tier 2 fires under exactly two conditions:

1. **Stall detection:** The top-scored candidate from Tier 1 has been below a threshold `τ_stall` for `k_stall` consecutive derivation steps (default: `τ_stall = 0.2`, `k_stall = 5`).
2. **Explicit subgoal request:** The A* search determines that the shortest estimated path exceeds a depth threshold `D_max` (default: `D_max = 10`).

### 7.2 Prompt Template

```text
You are a logical reasoning assistant for a probabilistic inference engine (PLN).

CURRENT GOAL:
{goal_statement}

KNOWN FACTS (top-10 by relevance):
{formatted_beliefs}

DERIVATIONS ATTEMPTED SO FAR (last 5):
{recent_derivation_log}

The forward search has stalled. Please suggest:
1. An intermediate SUBGOAL that would bridge known facts toward the goal.
   Format: (LinkType ConceptA ConceptB)
2. Which known fact is most likely to be a useful starting premise.

Respond in this exact JSON format:
{
  "subgoal": "(LinkType ConceptA ConceptB)",
  "suggested_premise": "(LinkType ConceptX ConceptY)",
  "reasoning": "brief explanation"
}
```

### 7.3 Python Implementation

```python
# prism/tier2_llm.py — Strategic LLM reasoner

import json

class Tier2Reasoner:
    def __init__(self, model_name="meta-llama/Llama-3.1-8B-Instruct",
                 stall_threshold=0.2, stall_steps=5):
        self.model_name = model_name
        self.stall_threshold = stall_threshold
        self.stall_steps = stall_steps
        self._consecutive_low_scores = 0
        self._client = None  # Lazy-loaded LLM client

    def check_stall(self, top_score):
        """Track consecutive low-scoring steps. Returns True if stalled."""
        if top_score < self.stall_threshold:
            self._consecutive_low_scores += 1
        else:
            self._consecutive_low_scores = 0
        return self._consecutive_low_scores >= self.stall_steps

    def decompose_goal(self, goal, beliefs, recent_derivations):
        """
        Call the LLM to decompose a goal into subgoals.

        Returns
        -------
        dict with keys: 'subgoal', 'suggested_premise', 'reasoning'
        or None if the LLM call fails
        """
        prompt = self._build_prompt(goal, beliefs, recent_derivations)

        try:
            response = self._call_llm(prompt)
            parsed = json.loads(response)
            self._consecutive_low_scores = 0  # Reset stall counter
            return parsed
        except Exception as e:
            print(f"[PRISM Tier 2] LLM call failed: {e}")
            return None

    def _build_prompt(self, goal, beliefs, recent_derivations):
        formatted_beliefs = "\n".join(
            f"  {i+1}. {b}" for i, b in enumerate(beliefs[:10])
        )
        formatted_derivations = "\n".join(
            f"  {i+1}. {d}" for i, d in enumerate(recent_derivations[-5:])
        )
        return PROMPT_TEMPLATE.format(
            goal_statement=goal,
            formatted_beliefs=formatted_beliefs,
            recent_derivation_log=formatted_derivations
        )

    def _call_llm(self, prompt):
        """Call the LLM. Implementation depends on local vs API setup."""
        # Placeholder — real implementation uses vLLM, ollama, or an API
        if self._client is None:
            self._init_client()
        return self._client.generate(prompt, max_tokens=256)

    def _init_client(self):
        """Lazy-initialize the LLM client."""
        try:
            import ollama
            self._client = ollama.Client()
        except ImportError:
            raise RuntimeError(
                "No LLM backend available. Install ollama or set up an API endpoint."
            )
```

---

## 8. The Search Algorithm: Learned A*

### 8.1 Formal Definition

**State space:**
- A *state* `s` is the current `(Tasks, Beliefs)` pair — the full derivation context.
- An *action* `a` is a `(rule, premise_set)` pair — a single inference step.
- A *transition* `T(s, a) → s'` applies the rule to the premises, producing a new derived Sentence and updated queues.

**Evaluation function:**

```
f(n) = g(n) + h(n)
```

- **g(n):** Path cost from the root state to node `n`.

  ```
  g(n) = Σᵢ cost(aᵢ)
  ```

  Where `cost(aᵢ) = 1 − confidence(conclusion_of_aᵢ)`. High-confidence steps are cheap; low-confidence steps are expensive.

- **h(n):** Heuristic estimate of remaining cost from `n` to goal `G`.

  ```
  h(n) = 1 − score_tier1(top_candidate_at_n, G)
  ```

  Where `score_tier1` is Tier 1's output (v1 symbolic or v2 learned). When `score_tier1` is high (promising), `h(n)` is low (close to goal).

### 8.2 Search Loop Pseudocode

```python
# prism/search.py — Learned A* search engine

import heapq
from prism.tier1_v1 import score_candidate
from prism.tier2_llm import Tier2Reasoner
from prism.cache import ScoreCache

def prism_search(initial_tasks, initial_beliefs, goal, config):
    """
    Learned A* search over PLN derivation space.

    Parameters
    ----------
    initial_tasks   : list of Sentence — initial task queue
    initial_beliefs : list of Sentence — initial belief buffer
    goal            : tuple — target statement
    config          : dict — {max_steps, task_queue_size, belief_queue_size, ...}

    Returns
    -------
    (result_beliefs, proof_trace) or (None, trace) if goal not reached
    """
    cache = ScoreCache()
    tier2 = Tier2Reasoner()
    proof_trace = []

    # Priority queue: (f_score, step_count, state)
    # state = (tasks, beliefs, g_cost, depth, derivation_history)
    initial_state = (initial_tasks, initial_beliefs, 0.0, 0, [])
    pq = [(0.0, 0, initial_state)]
    visited = set()
    step = 0

    while pq and step < config['max_steps']:
        f_score, _, (tasks, beliefs, g_cost, depth, history) = heapq.heappop(pq)
        step += 1

        # Check if goal is already derived
        for belief in beliefs:
            if matches_goal(belief, goal):
                return beliefs, history + [belief]

        # Generate candidate derivations
        candidates = generate_candidates(tasks, beliefs)

        if not candidates:
            continue

        # Score all candidates with Tier 1
        scored = []
        for candidate in candidates:
            score = cache.get_or_compute(
                candidate, goal,
                lambda c, g: score_candidate(c, g, depth=depth)
            )
            scored.append((score, candidate))

        scored.sort(key=lambda x: -x[0])  # Descending by score

        # Check for stall → invoke Tier 2
        top_score = scored[0][0] if scored else 0.0
        if tier2.check_stall(top_score):
            subgoal_result = tier2.decompose_goal(
                goal, beliefs, history[-5:]
            )
            if subgoal_result and subgoal_result.get('subgoal'):
                # Insert subgoal as a new backward target
                proof_trace.append(('tier2_subgoal', subgoal_result))
                # TODO: Add subgoal to backward search frontier

        # Expand top-k candidates
        top_k = scored[:config.get('top_k', 5)]
        for score, candidate in top_k:
            new_beliefs, new_tasks = apply_candidate(candidate, tasks, beliefs, config)
            action_cost = 1.0 - get_conclusion_confidence(candidate)
            new_g = g_cost + action_cost
            h = 1.0 - score  # Tier 1 score inverted as heuristic distance
            new_f = new_g + h
            new_state = (new_tasks, new_beliefs, new_g, depth + 1,
                         history + [candidate])
            state_hash = hash_state(new_beliefs)
            if state_hash not in visited:
                visited.add(state_hash)
                heapq.heappush(pq, (new_f, step, new_state))

    return None, proof_trace  # Goal not reached within budget
```

---

## 9. Bidirectional Search & Meet-in-the-Middle

### 9.1 Forward Frontier

The standard `PLN.Derive` loop, guided by Tier 1. Produces derived Sentences moving outward from known premises.

### 9.2 Backward Frontier

Initiated by Tier 2 when it proposes subgoals. Each subgoal becomes a target for backward search:

```python
def backward_step(subgoal, beliefs, rules):
    """
    Given a subgoal, find beliefs and rules that could produce it.

    For subgoal (Inheritance A C):
      - Look for rules where the conclusion pattern matches (Inheritance A C)
      - For Deduction: need (Inheritance A $B) and (Inheritance $B C)
      - Check beliefs for partial matches
    """
    backward_candidates = []
    for rule in rules:
        required_premises = rule.decompose(subgoal)
        for premises in required_premises:
            # Check which premises are already in beliefs
            available = [p for p in premises if any(matches(p, b) for b in beliefs)]
            missing   = [p for p in premises if p not in available]
            backward_candidates.append({
                'rule': rule,
                'available_premises': available,
                'missing_premises': missing,  # These become new subgoals
                'completeness': len(available) / len(premises)
            })
    return backward_candidates
```

### 9.3 Meet-in-the-Middle Termination

```python
def check_connection(forward_beliefs, backward_subgoals):
    """
    Check if any forward-derived fact satisfies a backward subgoal.

    Returns the connecting Sentence if found, None otherwise.
    """
    for belief in forward_beliefs:
        for subgoal in backward_subgoals:
            if matches_goal(belief, subgoal):
                return belief, subgoal
    return None
```

When a connection is found, the proof trace is constructed by chaining:
`[initial premises] → [forward derivations] → [connection point] ← [backward subgoal chain] ← [goal]`

---

## 10. Score Memoization & FFI Caching

### 10.1 The Problem

`LimitSize` trims a queue of `N` items to size `K` by repeatedly finding and removing the worst-scoring item. Each removal calls `BestCandidate`, which calls `PriorityRankNegGoal` on every item in the remaining list. Without caching:

```
Total FFI calls = (N - K) × N ≈ O(N²)
```

For `N = 100` and `K = 10`: **~8,100 Python calls** per single derivation step, per queue.

### 10.2 Solution: Score Cache

```python
# prism/cache.py — Score memoization

class ScoreCache:
    """
    Caches Tier 1 scores keyed on (sentence_hash, goal_hash).
    Scores are immutable during a single queue-sorting operation
    because truth values and evidence stamps don't change during sorting.
    """

    def __init__(self):
        self._cache = {}

    def get_or_compute(self, sentence, goal, compute_fn):
        key = (self._hash_sentence(sentence), self._hash_goal(goal))
        if key not in self._cache:
            self._cache[key] = compute_fn(sentence, goal)
        return self._cache[key]

    def invalidate_sentence(self, sentence):
        """Called when a Sentence is revised (truth value changes)."""
        prefix = self._hash_sentence(sentence)
        self._cache = {k: v for k, v in self._cache.items() if k[0] != prefix}

    def clear(self):
        """Clear all cached scores (e.g., between derivation runs)."""
        self._cache.clear()

    @staticmethod
    def _hash_sentence(sentence):
        return hash(str(sentence))

    @staticmethod
    def _hash_goal(goal):
        return hash(str(goal))
```

### 10.3 MeTTa-Side Caching

On the MeTTa side, the py.call scorer is called once per Sentence at queue-insertion time, and the result is stored as a MeTTa atom:

```metta
;; Cache pattern: store score alongside the Sentence
;; When a new derivation is added to the queue, compute and memoize its score
(= (ScoreAndCache $sentence $Goal)
   (let $score (py.call scorer score_candidate ($sentence $Goal))
        (CachedScore $sentence $Goal $score)))
```

`BestCandidate` then reads cached scores instead of calling `py.call`:

```metta
(= ((PriorityRankGoalCached $Goal) (CachedScore $sentence $Goal $score))
   $score)
(= ((PriorityRankGoalCached $Goal) (Sentence ($x (stv $f $c)) $Ev1))
   $c)  ;; Fallback for uncached sentences: raw confidence
```

---

## 11. Python Scorer Module

### 11.1 Module Interface

```python
# prism/scorer.py — Main entry point called via py.call from MeTTa

from prism.tier1_v1 import score_candidate as _score_v1
from prism.cache import ScoreCache

_cache = ScoreCache()
_tier1_version = "v1"  # Switch to "v2" after Week 11 training

def score_candidate(sentence, goal):
    """
    Called from MeTTa via: (py.call scorer score_candidate ($sentence $goal))

    Returns a float score. On any error, returns the string "Error"
    so the MeTTa-side fallback (raw confidence) activates.
    """
    try:
        if _tier1_version == "v1":
            return _cache.get_or_compute(
                sentence, goal,
                lambda s, g: _score_v1(s, g)
            )
        else:
            from prism.tier1_v2 import score_candidate as _score_v2
            return _cache.get_or_compute(
                sentence, goal,
                lambda s, g: _score_v2(s, g)
            )
    except Exception as e:
        print(f"[PRISM scorer] Error: {e}")
        return "Error"

def clear_cache():
    """Called between derivation runs to reset memoized scores."""
    _cache.clear()
```

---

## 12. Evaluation Harness & Benchmarks

### 12.1 Synthetic Transitive Chain Generator

```python
# prism/benchmarks/transitive_chain.py

def generate_chain(depth, base_strength=0.9, base_confidence=0.9):
    """
    Generate a transitive inference chain of given depth.

    For depth=5, generates:
      (Inheritance A B) (stv 0.9 0.9)
      (Inheritance B C) (stv 0.9 0.9)
      (Inheritance C D) (stv 0.9 0.9)
      (Inheritance D E) (stv 0.9 0.9)
      (Inheritance E F) (stv 0.9 0.9)

    Goal: (Inheritance A F)
    Known-correct proof: deduction chain of depth 4

    Also generates N_distractor distractor facts to increase branching factor.
    """
    import string
    nodes = list(string.ascii_uppercase[:depth + 1])  # A, B, C, ..., F

    # Chain facts
    chain_facts = []
    for i in range(depth):
        chain_facts.append({
            'statement': f'(Inheritance {nodes[i]} {nodes[i+1]})',
            'stv': f'(stv {base_strength} {base_confidence})',
            'evidence_id': str(i + 1)
        })

    # STV declarations
    stv_decls = [f'(= (STV {n}) (stv {1.0/(depth+1):.4f} 0.9))' for n in nodes]

    # Goal
    goal = f'(Inheritance {nodes[0]} {nodes[-1]})'

    return {
        'chain_facts': chain_facts,
        'stv_declarations': stv_decls,
        'goal': goal,
        'optimal_proof_depth': depth - 1,
        'nodes': nodes
    }

def generate_with_distractors(depth, n_distractors=50):
    """Add random unrelated facts to increase the branching factor."""
    import random
    base = generate_chain(depth)

    distractor_concepts = [f'X{i}' for i in range(n_distractors)]
    distractors = []
    for i in range(n_distractors):
        a = random.choice(distractor_concepts)
        b = random.choice(distractor_concepts)
        if a != b:
            s = round(random.uniform(0.1, 1.0), 2)
            c = round(random.uniform(0.3, 0.95), 2)
            distractors.append({
                'statement': f'(Inheritance {a} {b})',
                'stv': f'(stv {s} {c})',
                'evidence_id': str(100 + i)
            })

    base['distractor_facts'] = distractors
    base['total_facts'] = len(base['chain_facts']) + len(distractors)
    return base
```

### 12.2 Metrics Collector

```python
# prism/benchmarks/metrics.py

class MetricsCollector:
    """Collects evaluation metrics during a guided search run."""

    def __init__(self):
        self.steps_taken = 0
        self.rules_fired = 0
        self.rules_on_proof_path = 0
        self.tier1_calls = 0
        self.tier2_calls = 0
        self.py_call_latencies = []
        self.goal_reached = False
        self.wall_clock_start = None
        self.wall_clock_end = None
        self.frontier_sizes = []

    def record_step(self, candidates_count, selected_on_proof_path):
        self.steps_taken += 1
        self.rules_fired += 1
        self.frontier_sizes.append(candidates_count)
        if selected_on_proof_path:
            self.rules_on_proof_path += 1

    @property
    def waste_ratio(self):
        """Fraction of fired rules that didn't contribute to proof."""
        if self.rules_fired == 0:
            return 0.0
        return 1.0 - (self.rules_on_proof_path / self.rules_fired)

    @property
    def wall_clock_seconds(self):
        if self.wall_clock_start and self.wall_clock_end:
            return self.wall_clock_end - self.wall_clock_start
        return None

    @property
    def avg_frontier_size(self):
        if not self.frontier_sizes:
            return 0.0
        return sum(self.frontier_sizes) / len(self.frontier_sizes)

    def summary(self):
        return {
            'steps': self.steps_taken,
            'rules_fired': self.rules_fired,
            'rules_on_proof_path': self.rules_on_proof_path,
            'waste_ratio': f'{self.waste_ratio:.2%}',
            'wall_clock_s': self.wall_clock_seconds,
            'tier1_calls': self.tier1_calls,
            'tier2_calls': self.tier2_calls,
            'avg_frontier_size': f'{self.avg_frontier_size:.1f}',
            'goal_reached': self.goal_reached,
            'avg_py_call_latency_ms': (
                f'{sum(self.py_call_latencies)/len(self.py_call_latencies)*1000:.2f}'
                if self.py_call_latencies else 'N/A'
            )
        }
```

---

## 13. File Manifest & Directory Layout

```
PLN/                              # trueagi-io/PLN (modified in-place)
├── lib_pln.metta                 # Modified: §3, §4
├── examples/                     # Unchanged (used for smoke tests only)
├── ruletests/                    # Unchanged (regression tests)
└── test.sh                       # Extended to run PRISM regression tests

prism/                            # New directory: PRISM implementation
├── __init__.py
├── scorer.py                     # §11 — Main py.call entry point
├── cache.py                      # §10 — Score memoization
├── tier1_v1.py                   # §6.2 — Symbolic/structural heuristic
├── tier1_v2.py                   # §6.3 — Trained embedding model (Week 11)
├── tier2_llm.py                  # §7 — Strategic LLM reasoner
├── search.py                     # §8 — Learned A* search engine
├── bidirectional.py              # §9 — Backward chaining & meet-in-middle
├── stage0_index.py               # §5 — Indexed premise pre-filter (conditional)
├── metta_bridge.py               # Utilities for MeTTa ↔ Python data conversion
├── config.py                     # Tunable parameters (α, β, δ, γ, τ_stall, etc.)
│
├── benchmarks/
│   ├── transitive_chain.py       # §12.1 — Synthetic chain generator
│   ├── kg_multihop.py            # KG multi-hop dataset loader
│   ├── metrics.py                # §12.2 — Metrics collector
│   ├── run_benchmark.py          # End-to-end benchmark driver
│   └── results/                  # Benchmark output (JSON + plots)
│
├── training/                     # Week 11 stretch goal
│   ├── collect_traces.py         # Extract training data from search logs
│   ├── train_tier1_v2.py         # Train the embedding/GNN model
│   └── model/                    # Saved model checkpoints
│
└── tests/
    ├── test_tier1_v1.py           # Unit tests for symbolic scorer
    ├── test_cache.py              # Unit tests for memoization
    ├── test_search.py             # Integration tests for A* loop
    ├── test_soundness.py          # Verify all conclusions match PLN recalc
    └── test_fallback.py           # Verify graceful degradation on py.call failure
```

---

## 14. Week-by-Week Build Order

| Week | Deliverable | Files Created/Modified | Pass/Fail Gate |
|------|------------|----------------------|----------------|
| **1** | `py.call` latency benchmark; `PriorityRankGoal` swap implemented and tested | `lib_pln.metta`, `scorer.py`, `cache.py`, benchmark script | py.call round-trip < 1ms; all existing `ruletests/*.metta` still pass |
| **2** | Synthetic benchmark domains; unguided baseline numbers | `benchmarks/transitive_chain.py`, `benchmarks/metrics.py`, `benchmarks/run_benchmark.py` | Transitive chains D∈[5,20] generate and run under unguided PLN; baseline waste ratios recorded |
| **3–4** | Tier 1 v1 symbolic heuristic; optional `$Goal` threading; Stage 0 (if needed) | `tier1_v1.py`, modified `lib_pln.metta` (§3), optionally `stage0_index.py` | `score_candidate` returns sensible scores; goal-aware PLN.Query produces same conclusions as baseline (soundness) |
| **5–6** | A* search loop; search trace logging | `search.py`, `config.py` | Guided search on D=5 chain reaches goal in fewer steps than unguided; traces logged to JSON |
| **7** | Forward-only evaluation on controlled domains | `benchmarks/results/` | Waste ratio reduced ≥20% vs baseline; wall-clock not slower than unguided |
| **8** | Tier 2 LLM integration; backward chaining; bidirectional termination | `tier2_llm.py`, `bidirectional.py` | Tier 2 fires on stall; subgoals produced; at least one bidirectional connection demonstrated |
| **9** | Scaling tests; cross-domain generalization | Updated benchmarks | Sub-linear waste growth with AtomSpace size; cross-domain > random baseline |
| **10** | Soundness verification; robustness & fallback testing | `tests/test_soundness.py`, `tests/test_fallback.py` | 100% soundness on all benchmark runs; scorer failure degrades gracefully |
| **11** | Train Tier 1 v2 on collected traces; compare v1 vs v2 | `training/`, `tier1_v2.py` | v2 shortlist accuracy ≥ v1 on held-out traces |
| **12** | Final benchmark report; demo | Report document, presentation materials | All metrics documented; reproducible benchmark script |

---

*This document is the implementation companion to the PRISM Proposal (rev. 4). It specifies every code change, algorithm, and data structure needed to build PRISM against the live `trueagi-io/PLN` codebase.*
