# Original CPU kernel instead of a framework wrapper

## Context and drivers
The portfolio needs numerical and lifetime evidence, not another API integration.

## Options
Wrap llama.cpp/Candle; build GPU kernels; use a hosted API.

## Decision
C++20 original scalar CPU math plus independently expressed NumPy oracle.

## Consequences
Local inspectability and error diagnosis outweigh throughput; FP64 reductions are explicit.

## Risks
Scalar code is slow and broad model compatibility is absent.

## Revisit when
Revisit after real checkpoint correctness and profiling show one measured kernel bottleneck.
