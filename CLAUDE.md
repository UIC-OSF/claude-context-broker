# Context discipline

- Search before reading.
- For full-file reads above the configured threshold, use the context-broker bulk-reader skill (`repo-read`) with
  a precise question and explicit paths.
- Treat `repo-read` as candidate evidence, not authority. Verify important
  findings with targeted reads before editing.
- Do not delegate architecture, security/authorization decisions, debugging
  root-cause analysis, or final review.
- Review diffs and run the project's checks before committing generated code.
