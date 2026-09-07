;; PRISM py-call Uncached Latency Benchmark

(= (uncached-benchmark-loop $i $n $base-statement $goal)
   (if (>= $i $n)
       "DONE"
       (let* (($sent (Sentence ((Inheritance Alice $i) (stv 0.9 0.8)) (1 2)))
              ($res (py-call (scorer.score_candidate $sent $goal))))
             (uncached-benchmark-loop (+ $i 1) $n $base-statement $goal))))

!(let $goal (Inheritance Alice TargetConcept)
   (let $_ (py-call (scorer.clear_cache))
     (let $t0 (py-call (time.perf_counter))
       (let $_ (uncached-benchmark-loop 0 1000 "test" $goal)
         (let $t1 (py-call (time.perf_counter))
           (let $total-sec (- $t1 $t0)
             (let $avg-ms (/ (* $total-sec 1000.0) 1000.0)
               (println! (UNCACHED_BENCHMARK_RESULTS:
                           (iterations: 1000)
                           (total_seconds: $total-sec)
                           (avg_latency_ms: $avg-ms)
                           (throughput_calls_per_sec: (/ 1000.0 $total-sec)))))))))))

!(println! (UNCACHED_CACHE_STATS: (py-call (scorer.cache_stats))))
