# One actor and conservative reservation

## Context and drivers
Cancellation and bounded admission need a precise linearization point.

## Options
Thread-per-request, coroutine swarm, distributed queue, dynamic overcommit.

## Decision
Single actor; reserve maximum request footprint at admission; prefill chunk <=4; one decode grant per round.

## Consequences
Simple lifecycle proofs; lower utilization and throughput than optimized batching.

## Risks
Blocking output or long kernels block progress; grant fairness is not latency fairness.

## Revisit when
Revisit after mixed-workload evidence establishes a bottleneck and preserves cancellation semantics.
