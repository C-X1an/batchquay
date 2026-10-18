# Owned pages without cross-request prefix sharing

## Context and drivers
Request reuse and cancellation are observable correctness/security boundaries.

## Options
One contiguous cache per request; shared prefix cache; global unowned slab.

## Decision
Bind pages to complete owner tuple and allocation epoch, validate access, clear before reuse.

## Consequences
Paging exposes lifetime/fragmentation tradeoffs; no sharing removes a timing/ownership complication.

## Risks
Trusted native spans and host privilege remain outside the handle boundary.

## Revisit when
Revisit sharing only with a new threat model, authority partition and specific measurement benefit.
