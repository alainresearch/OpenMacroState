# Contribution lanes

OpenMacroState keeps the stable core small. Most new work should enter through
one of three contracts rather than by changing the runtime:

1. **Connector** — collect source bytes and normalize frozen artifacts.
2. **Model adapter** — consume a frozen snapshot and return versioned outputs.
3. **Case pack** — declare a cutoff, admissible evidence, targets, baselines,
   reveal data, and scoring rules.

Templates under this directory are intentionally small. A generated template
must pass its offline contract test before the contributor adds domain logic.

Planned commands:

```text
oms contrib new connector my-source
oms contrib new model my-model
oms contrib new case my-event
oms contrib check .
```

Until those commands are implemented, copy the closest template directory and
replace every `CHANGE_ME` value.
