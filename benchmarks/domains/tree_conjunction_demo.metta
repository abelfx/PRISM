;; Auto-generated PRISM Benchmark Tree Conjunction Domain
;; Left Depth: 2 | Right Depth: 2 | Distractors: 0 | Guided: True
!(import! &self (library lib_import))
!(git-import! "https://github.com/trueagi-io/PLN.git")
!(import! &self (library PLN lib_pln))

;; STV Declarations for concepts
(= (STV A) (stv 0.2 0.9))
(= (STV M) (stv 0.2 0.9))
(= (STV Z) (stv 0.2 0.9))
(= (STV L1) (stv 0.2 0.9))
(= (STV R1) (stv 0.2 0.9))

;; Knowledge Base
(= (kb) (
    (Sentence ((Inheritance A L1) (stv 0.9 0.9)) (1))
    (Sentence ((Inheritance L1 M) (stv 0.9 0.9)) (2))
    (Sentence ((Inheritance M R1) (stv 0.9 0.9)) (3))
    (Sentence ((Inheritance R1 Z) (stv 0.9 0.9)) (4))
))

;; Target Goal: (Inheritance A Z)
!(println! (BENCHMARK_TARGET_GOAL: (Inheritance A Z)))
!(println! (BENCHMARK_RESULT: (PLN.Query (kb) (Inheritance A Z) 80 30 100)))
