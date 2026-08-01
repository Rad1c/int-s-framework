# Tools

Tools are executable, reusable automation. If something cannot be run or is unlikely to be reused, it does not belong here.

## Required structure

```text
.claude/tools/<category>/<tool-name>/
├── tool.yaml
├── README.md
└── <entrypoint>
```

Each tool must declare its purpose, runtime, entrypoint, inputs, outputs, requirements, tags, and lifecycle in `tool.yaml`. `validate-tools` enforces this.

## Lifecycle

1. **Temporary** — create one-off automation under `.claude/workspace/generated/`.
2. **Candidate** — after repeated successful use, move it to `.claude/tools/candidate/<tool-name>/`.
3. **Official** — after review, documentation, and verification, move it to the relevant category and run `sync-registry`.

## Workflow

1. Search `.claude/registry.yaml` and this directory before writing anything.
2. Reuse a matching tool.
3. If none exists, create the smallest temporary version under `.claude/workspace/generated/`.
4. Verify it runs.
5. Propose promotion the second time you need it.

Skills explain how, knowledge explains why, playbooks define workflows, and templates shape documents. Tools run.
