---
name: playbook
description: Use this skill when the user asks to create, review, improve, trim, audit, or standardize an AGENTS.md file, or to derive agent instructions from a codebase. Produces compact, repo-specific, LLM-optimized AGENTS.md files and, when useful, companion authoring guidance such as AGENTS_MD_GUIDELINE.md.
---

# Playbook

`AGENTS.md` is an instruction file for coding agents. Optimize it for fast machine consumption, not for human onboarding.

## Goals

Produce an `AGENTS.md` that is:
- Repo-specific
- High-signal
- Short and scannable
- Directive and unambiguous
- Derived from the actual codebase
- Focused on behavior-changing guidance

When the user asks for a companion guideline document such as `AGENTS_MD_GUIDELINE.md`, make that file human-oriented and explanatory. Keep `AGENTS.md` itself LLM-oriented and compressed.

Examples in this skill are illustrative only. Do not copy example terms, commands, or paths into the target `AGENTS.md`. Derive concrete wording from the target repository.

## Core Principles

- **LLM-first**: prioritize scanability, precision, and token efficiency over prose.
- **Repo-specific**: include local conventions, footguns, and canonical workflows.
- **Behavior-changing only**: every line should change what an agent does.
- **Low duplication**: do not restate README/setup/architecture docs unless the point is critical and easy to miss.
- **Stable over volatile**: prefer durable rules over fast-changing operational details.
- **Directive over descriptive**: write commands and constraints, not background essays.
- **Interactive when needed**: if high-impact maintenance policy is not clear from the repo, ask the user a few targeted questions before finalizing `AGENTS.md`.

## What Belongs in AGENTS.md

Include items like:
- Canonical domain terminology
- Monorepo or subproject boundary rules
- Generated-file / codegen warnings
- Files or directories that should not be edited directly
- Canonical validation commands
- Build, lint, test, or typecheck entry points the repo expects
- Repo-specific environment or configuration gotchas
- Preferred source of truth when multiple plausible options exist
- Existing dependency or pattern constraints
- Maintenance posture when it is explicit or user-confirmed (for example: clean refactors vs backward compatibility)
- Expensive mistakes agents are likely to make

Good examples:
- Use `<CanonicalDomainTerm>` as the canonical domain term.
- Do not hand-edit generated outputs such as protobuf/grpc stubs.
- Use the repo's canonical local validation command and full verification command.
- Match the conventions of the local package or subproject before editing.
- Prefer clean refactors over backward-compatible shims for internal code.
- Preserve public API or CLI compatibility unless the task explicitly allows breaking changes.

## What Does Not Belong in AGENTS.md

Exclude items like:
- Generic engineering advice
- Obvious facts visible from `ls`, manifests, imports, or framework files
- Full setup instructions better suited for `README.md`
- Long architecture explanations
- Vague recommendations without actionability
- Repeated content from other docs unless it prevents a likely mistake
- Details that are likely to go stale quickly

Bad examples:
- Write clean code.
- Use best practices.
- Run tests before committing.
- This repo has a backend and frontend.
- This project uses Python.

## Selection Heuristic

Keep a candidate line only if at least one is true:
- An agent is likely to miss it from quick code inspection.
- Getting it wrong would be expensive.
- It encodes a repo-specific convention.
- It changes where or how the agent should edit.
- It changes which commands the agent should run.
- It establishes canonical terminology.
- It prevents work in the wrong directory, package, or generated output.

Remove a candidate line if all are true:
- Easy to infer quickly from the codebase
- Low-cost if omitted
- Already covered better elsewhere
- Generic rather than repo-specific

## Discovery Workflow

Before writing or editing `AGENTS.md`:

1. Inspect the repo root docs and manifests.
2. Inspect validation entry points such as build files, CI workflows, package scripts, and lint/typecheck config.
3. Inspect codegen paths, generated artifacts, and build scripts.
4. Identify domain terminology that must remain consistent.
5. Identify subproject boundaries and local conventions.
6. Identify env vars, configuration, or runtime requirements that are easy to miss.
7. Reduce findings to short imperative bullets.
8. Remove anything obvious, generic, or duplicated.
9. Order items by importance and likelihood of mistakes.

Do not invent constraints. Derive them from the repository and existing docs.

## Interactive Clarification

If the repository does not clearly answer high-impact maintenance questions, ask the user before finalizing `AGENTS.md`.

Ask only a few targeted questions. Do not turn this into a long survey.
- Default question budget: 0 if the repo is clear, otherwise at most 3-5 questions.
- Prefer multiple-choice or sharply scoped questions over open-ended prompts.
- Skip questions already answered by docs, release policy, migration patterns, or public interface guarantees.

High-value questions often include:
- Should the repo favor clean refactors or backward compatibility?
- Are public APIs, CLIs, protocols, or config formats expected to remain backward compatible?
- Should agents prefer minimal diffs or larger cleanups when touching old code?
- Are schema, migration, or data-shape changes acceptable without an explicit migration plan?
- Should new dependencies be avoided even when they would simplify the change?
- When tradeoffs appear, should agents prioritize simplicity, performance, security, reliability, or delivery speed?

Use the answers to create short directives in `AGENTS.md`.

Examples:
- Prefer code cleanliness over preserving backward compatibility in internal modules.
- Preserve public HTTP and CLI interfaces unless explicitly told otherwise.
- Prefer minimal diffs in release branches.
- Do not change database schemas without a migration plan.

Do not ask these questions if the repo already answers them clearly through docs, release policy, public API guarantees, migration patterns, or existing contributor guidance.

## Writing Style for AGENTS.md

Prefer:
- Short sections
- Bullet lists
- Imperative phrasing
- Exact commands, filenames, paths, and terms
- Highest-cost mistakes near the top
- Minimal rationale

Avoid:
- Long paragraphs
- Narrative explanations
- Redundant bullets
- Soft wording like "try to" or "consider"
- Broad policy statements without concrete action

Good:

```md
## Rules
- Use `<CanonicalDomainTerm>` as the canonical domain term.
- Do not hand-edit generated outputs in `<generated path>`.
- Match local package or subproject conventions before making changes.

## Validation
- Use `<local validation command>` for quick verification.
- Use `<full validation command>` for the full check path.
```

Bad:

```md
Historically this repository used multiple names for similar concepts, so when
updating the codebase please try to use newer terminology where appropriate.
Also be aware that some generated files exist and may need extra care.
```

## Recommended Shape

A strong default structure is:

```md
# AGENTS.md

Prefer `README.md` and the codebase for setup and architecture details.

## Rules
- ...
- ...

## Validation
- ...
- ...

## Notes
- ...
- ...
```

Alternative section names are fine. Optimize for scanability, not ceremony.

## Updating an Existing AGENTS.md

When editing an existing file:
- Preserve valid repo-specific guidance.
- Remove generic, obvious, or stale lines.
- Compress prose into direct bullets.
- Keep canonical commands and terminology intact.
- Avoid rewriting just for style if the current line is already sharp and correct.

## AGENTS.md vs AGENTS_MD_GUIDELINE.md

Use this split when both files exist:

### `AGENTS.md`
- For agents
- Short
- Directive
- Repo-specific
- Low-noise
- Meant to be skimmed quickly

### `AGENTS_MD_GUIDELINE.md`
- For humans authoring `AGENTS.md`
- Longer and explanatory
- Can include rationale, heuristics, anti-patterns, and templates
- Generalizable across repositories

## Review Checklist

Before finalizing an `AGENTS.md`, check:
- Is every line actionable?
- Is every line repo-specific or mistake-preventing?
- Are the validation commands canonical and current?
- Are generated-file and codegen warnings included where relevant?
- Are domain terms explicit?
- Does the file avoid obvious facts and generic advice?
- Can any bullet be shortened further?
- Is the file easy for an LLM to scan in seconds?

## Default Output Strategy

When the user asks for a new `AGENTS.md`:
1. Derive candidate rules from the codebase.
2. Identify any unresolved high-impact maintenance policies.
3. Ask a few targeted questions only if those policies are not clear.
4. Keep only high-value instructions.
5. Produce a compact final file.

When the user asks for a guideline document:
1. Explain the purpose of `AGENTS.md`.
2. Define inclusion and exclusion criteria.
3. Provide authoring heuristics and anti-patterns.
4. Include a lightweight template and review checklist.

## One-Sentence Standard

A good `AGENTS.md` is a compact, repo-specific instruction set that tells an agent what it is likely to get wrong, what conventions it must preserve, and how to validate changes.
