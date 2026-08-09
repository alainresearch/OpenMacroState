# Model adapter template

A model adapter accepts a frozen snapshot. It may not retrieve live data.
Provide a tiny snapshot fixture and three contract cases:

- normal execution;
- missing required input;
- structured model failure.

Every result must record the model version, parameters, seed, environment,
diagnostics, limitations, and produced artifacts.
