# Test layout

Tests mirror the source area under either `unit` or `integration`:

```text
tests/
  unit/<domain>/{domain,application}/
  unit/shared/
  integration/<domain>/adapters/{http,postgres,redis}/
```

Use explicit fakes injected through ports in unit tests. Monkey patching is forbidden.
