# Mandatory independently referenced public checkpoint

## Context and drivers
A random tiny model can pass despite a real-model incompatibility.

## Options
Only random fixtures; generated text judged by eye; remote model API reference.

## Decision
Pin SmolLM2-135M, safe local conversion and eager Transformers numerical comparison.

## Consequences
Public finite checkpoint, explicit numerical tolerance, no remote-code execution.

## Risks
Upstream dependency behavior and precision differences require current verification.

## Revisit when
Revisit only through a documented acceptance exception if the upstream artifact becomes unavailable.
