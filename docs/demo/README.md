# Actual local demonstration
Run `make demo` and open `.local-runs/demo/report.html`. The recorded `report.html` and screenshots in this directory are from the real native child process with deterministic tiny synthetic weights.

30 seconds: locate accepted request, capacity denial, cancelled request and final zero resource counters. Two minutes: follow prefill and decode rounds; notice that cancellation stops future output. Five minutes: rerun an isolated request and an interleaved request, compare outputs, inspect page ownership tests and a selected negative control. No model API is involved.

Optional browser check: `python3 -m tools.browser_check`. The author environment restricts filesystem navigation; its browser QA loads the generated HTML via `set_content`, records this limitation, checks keyboard entry and mobile/desktop overflow, and captures the actual rendered output. It is not a hosted navigation or full accessibility certification.
