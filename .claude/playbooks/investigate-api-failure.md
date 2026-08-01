# Investigate API Failure

Use this playbook when an API request returns an unexpected `5xx` response.

1. **Read logs** — identify the failing request using its timestamp, route, environment, and correlation or trace ID.
2. **Check the stack trace** — find the first relevant application frame and preserve the original exception context.
3. **Locate the endpoint** — identify the route, HTTP method, request contract, and entry point.
4. **Locate the handler** — trace the call path through business logic, data access, and external dependencies.
5. **Reproduce** — repeat the failure with the smallest safe request in a non-production environment.
6. **Find the root cause** — verify the failing assumption or dependency with evidence.
7. **Fix** — change the narrowest shared point that caused the failure; preserve the API error contract.
8. **Regression tests** — add a check that fails before the fix, then run affected tests.

Do not copy secrets, tokens, or sensitive request data from logs. If reproduction is unsafe, diagnose from sanitized evidence.
