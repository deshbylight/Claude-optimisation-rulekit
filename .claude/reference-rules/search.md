---
description: Before writing new logic or adding a module/service/manager/helper library — search the project, then the frameworks and libraries in use, then public prior art; license check before reusing code
load: on-demand
---

# Search before create

## Forbidden

- A new module / service / manager / "helper" library without searching the project first.
- A parallel implementation beside an existing system.
- Writing a non-trivial algorithm or mechanism from scratch before checking the frameworks in use
  and public prior art.
- Running the full project → framework → web search for a local helper (file-private, a few lines):
  checking the project code and the APIs it already uses is enough.
- Copying third-party code with no license or a license incompatible with the project; copying
  without a source comment.

## Must

- Order: project (Grep, docs, decision records) → frameworks/libraries already in use (their source
  or docs) → web (official docs, issue trackers, public repositories, papers).
- Prefer extending an existing system; reuse a framework mechanism when it fits the project
  architecture (project decisions win).
- The web step applies to new mechanisms/algorithms; skip it for glue code, small fixes and
  project-specific wiring.
- Report what was found (path or URL, fit, license) in the proposal before writing code.
- Borrowed code: a license compatible with the project (permissive ones: MIT/BSD/Apache-2.0/zlib/
  Unlicense/CC0); adapt to project style; comment `Adapted from <URL> (<license>)`.
