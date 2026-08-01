# Debug

Use this playbook to find the root cause of incorrect behavior.

1. Capture the symptom, expected behavior, environment, and reproduction steps.
2. Reproduce the issue consistently or collect enough evidence to narrow it.
3. Check relevant logs, metrics, and traces for the affected time window and environment; correlate events by request, user, job, or trace ID.
4. Trace the failing flow through all relevant callers and boundaries.
5. Form one testable hypothesis at a time and verify it with evidence.
6. Fix the root cause at the narrowest shared point.
7. Add a regression check that fails without the fix.
8. Run affected checks and document any remaining uncertainty.

Do not expose secrets or sensitive data while collecting evidence. Do not change behavior based only on an unverified guess.
