# API architecture

One operation per folder: controller, request/response, command or query, and handler.
Handlers use `AsyncSession` directly; domain models are independent of HTTP and ORM.
Controllers instantiate handlers directly. Requests use FastAPI's body/query validation.
Use dependency injection only for infrastructure and authentication, never handlers or request DTOs.

- [Architecture and request sequence](../../Docs/BackendAndDataStorage/architecture/README.md)
- [Authentication and sequence diagrams](../../Docs/BackendAndDataStorage/auth/README.md)
