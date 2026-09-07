;; PRISM py-call Round-Trip Latency & Throughput Benchmark

(= (benchmark-loop $i $n $sentence $goal)
   (if (>= $i $n)
       "DONE"
       (let $res (py-call (scorer.score_candidate $sentence $goal))
            (benchmark-loop (+ $i 1) $n $sentence $goal))))

!(let $test-sentence (Sentence ((Inheritance Alice Ancestor-of-Bob) (stv 0.9 0.8)) (1 2))
   (let $test-goal (Inheritance Alice Ancestor-of-Carol)
     (let $t0 (py-call (time.perf_counter))
       (let $_ (benchmark-loop 0 1000 $test-sentence $test-goal)
         (let $t1 (py-call (time.perf_counter))
           (let $total-sec (- $t1 $t0)
             (let $avg-ms (/ (* $total-sec 1000.0) 1000.0)
               (println! (BENCHMARK_RESULTS:
                           (iterations: 1000)
                           (total_seconds: $total-sec)
                           (avg_latency_ms: $avg-ms)
                           (throughput_calls_per_sec: (/ 1000.0 $total-sec)))))))))))

;; Test cache stats
!(println! (CACHE_STATS: (py-call (scorer.cache_stats))))

;; Test exception fallback
!(println! (EXCEPTION_HANDLING: (py-call (scorer.score_candidate (Sentence "malformed" ()) (Sentence "bad" ())))))
