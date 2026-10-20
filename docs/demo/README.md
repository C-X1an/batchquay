# Actual local demonstration

Run `make demo` and open `.local-runs/demo/report.html`. The report, raw trace and screenshots here were regenerated from the actual native child process with deterministic synthetic weights. They are a recorded example, not useful generated language or a live inference service.

Follow admission, capacity denial, cancellation, decode rounds and the final zero resource counters. The source identity is embedded in the trace and rendered footer. Cancellation stops later output for that request generation.

The recorded browser check used sandbox-enabled Chrome on Windows, loading the owned HTML via `set_content`; desktop/mobile layout, keyboard entry, exact source identity and screenshots passed. It did not test a hosted URL or certify full accessibility. The separate interactive browser inspection used a temporary loopback static-file server. Browser-test dependencies are isolated and hash-locked in requirements-browser.lock.
