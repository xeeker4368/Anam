# Registry Schema Conventions

## Summary

Added a developer-facing document that defines conventions for Project Anam internal registry tables and services before adding additional registries.

## Files Changed

- `REGISTRY_SCHEMA_CONVENTIONS.md`
- `changelog/2026-04-29-registry-schema-conventions.md`

## Behavior Changed

- No runtime behavior changed.
- No database schema changed.
- No services were refactored.
- No runtime context was modified.

## Tests/Checks Run

- `git diff --check`
- Manual Markdown review

## Known Limitations

- The conventions are documentation only and are not enforced by code.
- Legacy `documents`, `tasks`, and `overnight_runs` remain unchanged.

## Follow-up Work

- Use these conventions when planning Research Ideas Foundation.
- Consider shared registry helpers later if service duplication becomes costly.

## Project Anam Alignment Check

- Did not modify runtime behavior.
- Did not modify database schema.
- Did not refactor services.
- Did not modify legacy tables.
- Did not rename `tir/`.
- Did not modify `soul.md`.
- Did not wire anything into runtime context.
- Did not modify `OPERATIONAL_GUIDANCE.md`.
