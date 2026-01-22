# Copilot instructions for this repo

## Architecture overview
- Sanic app factory lives in [src/testbench_requirement_service/app.py](../src/testbench_requirement_service/app.py); it wires middleware, exception handlers, routes, and static swagger assets.
- HTTP routes in [src/testbench_requirement_service/routes.py](../src/testbench_requirement_service/routes.py) call `get_requirement_reader()` to delegate all data access to a reader.
- Reader abstraction is `AbstractRequirementReader` in [src/testbench_requirement_service/readers/abstract_reader.py](../src/testbench_requirement_service/readers/abstract_reader.py); concrete readers live under [src/testbench_requirement_service/readers](../src/testbench_requirement_service/readers):
  - JSONL reader reads `.jsonl` baselines and `UserDefinedAttributes.json` (see [src/testbench_requirement_service/readers/jsonl/reader.py](../src/testbench_requirement_service/readers/jsonl/reader.py)).
  - Excel reader reads `.properties` configs and Excel/CSV/TXT files (see [src/testbench_requirement_service/readers/excel/reader.py](../src/testbench_requirement_service/readers/excel/reader.py)).
  - Jira reader wraps the Jira API and custom fields (see [src/testbench_requirement_service/readers/jira/reader.py](../src/testbench_requirement_service/readers/jira/reader.py)).
- Data contracts are Pydantic v2 models in [src/testbench_requirement_service/models/requirement.py](../src/testbench_requirement_service/models/requirement.py) and validated settings in [src/testbench_requirement_service/models/config.py](../src/testbench_requirement_service/models/config.py).

## Configuration + data flow
- CLI entrypoint is Click in [src/testbench_requirement_service/cli.py](../src/testbench_requirement_service/cli.py). `testbench-requirement-service start` builds `AppConfig`, then `create_app()`.
- Config loading prefers TOML with section `[testbench-requirement-service]` (see [src/testbench_requirement_service/utils/config.py](../src/testbench_requirement_service/utils/config.py)); legacy `config.py` is still supported.
- `Settings.reader_config_path` is validated to exist; if you introduce new config paths in code or tests, ensure the file exists before settings are loaded.
- Reader config loading is centralized in [src/testbench_requirement_service/readers/utils.py](../src/testbench_requirement_service/readers/utils.py): `.toml` or `.properties` only, with optional section prefix.

## Auth + middleware conventions
- Basic Auth is enforced globally in middleware except `/`, `/docs`, `/static`, `/openapi.yaml`, `/favicon.ico` (see [src/testbench_requirement_service/middlewares.py](../src/testbench_requirement_service/middlewares.py)). Route handlers that should be protected also use `@protected` (see [src/testbench_requirement_service/utils/auth.py](../src/testbench_requirement_service/utils/auth.py)).
- Request/response logging uses `MAX_LOG_BODY` Sanic config for truncation; keep payload size in mind when adding routes.

## Dependency gates
- Excel and Jira readers are optional; `create_app()` calls dependency checks based on `READER_CLASS` (see [src/testbench_requirement_service/utils/dependencies.py](../src/testbench_requirement_service/utils/dependencies.py)). If you add a new reader type with extras, mirror this pattern.

## Developer workflows
- Linting is via Invoke tasks in [tasks.py](../tasks.py): `invoke lint` runs mypy + ruff + robocop on Robot tests.
- Tests are Robot Framework suites under [tests/robot](../tests/robot); `invoke test` writes results to [results](../results).

## Examples of common patterns
- Routes validate JSON with Pydantic and surface `BadRequest` on `ValidationError` (see [src/testbench_requirement_service/routes.py](../src/testbench_requirement_service/routes.py)).
- Reader implementations return Pydantic models and use `model_dump()` to serialize to JSON (see [src/testbench_requirement_service/readers/jsonl/reader.py](../src/testbench_requirement_service/readers/jsonl/reader.py)).