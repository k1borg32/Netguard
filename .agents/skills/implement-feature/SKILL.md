---
name: implement-feature
description: Implement Netguard backend features and API endpoints with staged user approvals, integration tests and English PlantUML documentation. Use for feature implementation in the Netguard repository, including changes to API consumers required by a changed contract.
---

# Implement a Netguard feature

Work on one endpoint or independently reviewable use case at a time. Follow the user's current scope and preserve approvals already given in the conversation. Communicate in the user's language; write project content in English.

## Establish the working context

- Verify the Git root, remote, active branch, local changes and applicable `AGENTS.md` instructions. The intended repository is `k1borg32/Netguard`; an umbrella workspace or an old review checkout may be a different repository.
- Use the checkout and branch selected by the user. `services/backend_and_data_storage` was the branch used for the detections work; it is context, not an instruction to switch branches. Identify the working root and branch before editing.
- Preserve existing commits and unrelated work. Synchronize with `main` when requested, retaining the user's changes; do not reset or recreate the checkout to achieve this.
- Identify the feature's actual issue and current API contract from the repository and connected GitHub tools. Do not reuse the detections issue number for unrelated features.
- Track the current endpoint and approval stage across follow-up messages. Apply amendments to that work without restarting the workflow. Ask about unresolved product or contract choices when repository evidence cannot resolve them; continue independent work while waiting.

## Approval sequence

### 1. Implement one endpoint

Implement the production behavior and any necessary consumer compatibility changes. Inspect the data model and existing operations first. Formatting and static checks may run now; leave new tests and documentation for the next stage unless the user has already authorized them.

Present a concrete reviewable result: behavior, request and response changes, validation and error handling, relevant files, and any material limitation. Ask for approval of this implementation and stop before adding tests or documentation or starting another endpoint.

### 2. Add tests and documentation after approval

Read [Verification and documentation](references/verification.md). Add meaningful tests and concise technical documentation, run the appropriate checks and fix relevant failures.

Report the results and documentation location. Ask for approval before proceeding to the next endpoint. Do not treat silence or elapsed time as approval.

If the user already approved this stage or instructed "commit after documentation", complete the authorized work and commit at that point without requesting the same approval again. A request for a focused amendment does not authorize unrelated endpoints.

### 3. Continue only when authorized

Repeat stages 1 and 2 for the next endpoint after the second approval. A later explicit instruction can change this sequence; follow it and retain its authorization across turns.

## Implementation conventions

Read `services/api/ARCHITECTURE.md` and the closest existing operation. The current API uses vertical slices under `services/api/app/features/<area>/<operation>/`: controller, request/response, query or command, and handler. Assemble routes through the feature router.

- Controllers instantiate handlers directly. Dependency injection supplies infrastructure and authentication, not handlers or request DTOs.
- Handlers use `AsyncSession` directly. Keep domain models independent of HTTP and ORM; inspect `services/api/app/domain/` and the existing imperative mappings under `services/api/app/infrastructure/persistence/`. Do not introduce a repository or unit-of-work layer for an ordinary endpoint.
- Follow existing validation, exception and HTTP status conventions. Update OpenAPI metadata and preserve the agreed authentication contract; public endpoints do not acquire authentication implicitly.
- Inspect physical schema and producer behavior before querying relationships or adding migrations. For example, sampled detection trace IDs are not evidence that every matching flow is retained. Explain such limitations in the endpoint contract.
- For list operations, reuse the current pagination contract where applicable: `items`, `total`, `page`, `page_size`. Specify defaults, bounds and supported filters. Use a deterministic ordering with a unique tie-breaker and correct totals for empty or out-of-range pages. Distinguish a missing parent from an existing parent with no children.
- Preserve meaningful null values, including nullable ingestion timestamps. Update dashboard types, consumers, fixtures and affected stack tests when the response shape changes.
- Keep identifiers, comments, messages, test descriptions, documentation and diagrams in English. Check touched feature files for remaining Polish text, including words without accented characters.
- For framework, library, SDK or CLI documentation questions, use Context7: resolve the library ID first, then query documentation for the relevant concept. Business-logic debugging and ordinary refactoring do not require library lookup.

## Commits, pushes and CI

Commit or push when the user requests it; preserve authorization already provided. A commit request alone does not authorize a push. Stage only the feature's changes.

Use a short English commit message referencing only the actual feature issue, for example `RE #<issue> implement detection flows`. Do not add unrelated issue references or close an issue whose requested work is unfinished.

Push to the authorized current branch normally, without force. If the user asks to check the pipeline before pushing, perform the relevant checks from the current workflow first. A passing local subset is not a passing pipeline: distinguish local verification from remote CI, and associate remote results with the exact commit.

Conclude with the concrete changes, verification results and any authorized commit/push outcome. Do not claim skipped checks passed or silently move to another endpoint while approval is pending.
