# Verification and documentation

Read this after implementation approval, or when the user requests tests, documentation or pipeline verification. Use the current `services/api/tests/README.md`, `pyproject.toml`, `.github/workflows/ci.yml` and feature documentation as the source of truth; do not freeze test counts or dependency versions in this skill.

## Test the actual behavior

- Put domain and request-validation tests in `services/api/tests/unit/`, and HTTP/database tests in `services/api/tests/integration/`.
- Follow the API test policy: no mocks, repository stubs, handler replacements, mocked SQLAlchemy sessions or `app.dependency_overrides`. Test SQL and HTTP behavior against the real application and database.
- Reuse the existing isolated Docker database fixtures. They initialize the production schema from `db/init/*.sql`, clean application tables before and after every test, and remove their own container at session end. Run sequentially, without pytest-xdist.
- Never point cleanup fixtures at the user's application database or reuse its volumes. The fixtures provide their own connection URL; the normal application stack and `.env` are unnecessary for API integration tests.
- Cover the changed contract with relevant cases: successful and empty responses, evidence and nullable values, deterministic ordering, filters and page totals, boundary and invalid parameters, missing resources, and the established unavailable-database response. Verify a read endpoint does not modify stored data when this is a meaningful risk.
- Each test seeds its own data and asserts observable behavior. Add only cases needed to verify the feature; avoid assertions that merely repeat implementation details.

## Run appropriate checks

Use the project's Python environment and installed development dependencies. From the verified repository root, typical checks are:

```text
python -m ruff check .
python -m ruff format --check .
python -m pytest services/api/tests/integration/test_<operation>.py -q
python -m pytest -q
```

Choose the real changed test files; the placeholder above is not an executable filename. Consult the current workflow if dependencies need installing. The default pytest selection currently excludes stack tests, so it does not establish that full CI passes.

When API consumer contracts change, verify the affected dashboard fixtures and the dashboard checks in `services/dashboard`: lint, component tests and build, using the Node version and lockfile in the current workflow.

For full pipeline verification, account for every relevant job, including secret scanning and the integration job's API tests, stack tests and processor scale/failure smoke test. Run stack checks in a dedicated isolated Compose project with separate test configuration, ports and volumes. Do not copy CI's teardown against the user's running application project or replace their `.env`.

Report exact completed checks, failures and unrun jobs. Repair relevant failures before a requested push. Do not bypass checks, change tests to hide a regression, or label unavailable checks as successful. Once checks pass, repeat or broaden them only for new changes or unresolved concerns. If remote CI is requested, inspect its results for the exact pushed commit.

## Document the endpoint

Update `Docs/BackendAndDataStorage/<area>/README.md`, with one concise technical section per endpoint. Include method and path, authentication, parameters and bounds, response fields, status codes and any meaningful data or query limitations. Give a compact example when it clarifies the contract.

Use English throughout. Update endpoint checklists only for work actually completed.

Use PlantUML sequence diagrams, not Mermaid. Store editable `.puml` sources and rendered `.svg` diagrams under the feature's `diagrams/` directory. Embed the SVG in the README and link to its source using relative paths. Keep the request/controller/handler/database flow consistent with the implementation, including important alternative responses.

Render with an available local PlantUML renderer, check syntax and inspect the rendered result for readability. Verify README links resolve. If rendering is unavailable, retain the source and report the missing verification rather than claiming the diagram was rendered.
