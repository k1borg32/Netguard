# Uwierzytelnianie NetGuard API

Kontroler HTTP znajduje się w `app/api/controllers/auth_controller.py`.
Handlery w `app/features/auth` przyjmują komendy/zapytania oraz protokoły repozytorium,
hashera i wystawcy tokenów przez konstruktor. Nie zależą od FastAPI, psycopg ani AuthX.

## Dependency Injection

Osobny pakiet `app/di` jest miejscem kompozycji zależności:

- `database.py`: połączenie na żądanie i powiązanie `AuthRepository` z `PsycopgAuthRepository`.
- `security.py`: AuthX, hasher Argon2, wystawca tokenów i ich cykl życia.
- `auth.py`: fabryki handlerów z zależnościami wstrzykiwanymi przez konstruktor.
- `__init__.py`: publiczne funkcje `get_*`, używane przez kontrolery i testy.

`authentication.py` w module DI podłącza zależności HTTP i `require_roles()`.
Weryfikacja i odczyt JWT przez AuthX są w `app/infrastructure/security/authentication.py`,
który nie importuje modułu DI. Kontrolery HTTP są w `app/api/controllers`, także dla health.
Warstwa `features` importuje wyłącznie kontrakty z `abstraction` i kod aplikacyjny.
Tylko moduł `app/di` wiąże protokoły z implementacjami infrastruktury.
Nowe implementacje i handlery składaj przez analogiczne funkcje w pakiecie DI.
Kontrolery i handlery nie tworzą repozytoriów ani usług bezpieczeństwa.
Kompozycję realizuje standardowe FastAPI `Depends`, bez dodatkowego kontenera DI.
Połączenia są tworzone i zamykane dla każdego żądania; AuthX i hasher są współdzielone.
Handlery i wystawca tokenów są tworzone przy rozwiązywaniu zależności.

W testach podmieniaj dokładnie funkcję dostawcy importowaną z publicznego modułu:

```python
from app.di import get_auth_repository

app.dependency_overrides[get_auth_repository] = lambda: repository
```

Testy integracyjne korzystają z prawdziwego repozytorium oraz testowej konfiguracji połączenia.

## Konfiguracja i migracja

Zainstaluj zależności z `requirements.txt`. Ustaw `DATABASE_URL` oraz `JWT_SECRET`
w środowisku albo w głównym pliku `.env`. Sekret JWT powinien być losowy i prywatny.
AuthX 1.7.1 używa HS256. Access token jest ważny 15 minut, refresh token 7 dni.

Tabela `users` jest wykorzystywana bez zmian. Brakującą tabelę sesji dodaje
`db/init/002_auth_refresh_sessions.sql`. Nowy wolumen bazy wykona ten plik automatycznie.
Dla istniejącego wolumenu uruchom z głównego katalogu repozytorium w PowerShell:

```powershell
Get-Content ./db/init/002_auth_refresh_sessions.sql -Raw | docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1'
```

Migracja nie usuwa istniejących danych ani nie odtwarza bazy.

## Pierwszy administrator

W katalogu `services/api`, po aktywacji środowiska:

```powershell
python -m app.infrastructure.bootstrap_admin
```

Albo z głównego katalogu, gdy kontener API jest uruchomiony:

```powershell
docker compose exec api python -m app.infrastructure.bootstrap_admin
```

Polecenie pyta o login i dwukrotnie o hasło. Hasło nie jest przekazywane jako argument.
Hasło musi mieć 12–1024 znaków, a login 1–128 znaków bez białych znaków.
Bootstrap odmawia utworzenia konta, jeżeli istnieje już administrator.
Blokada tabeli zabezpiecza także równoczesne wywołania polecenia.
Kolejne konta tworzy administrator przez endpoint rejestracji.

## Endpointy

| Metoda i ścieżka | Dane / uwierzytelnianie | Wynik |
| --- | --- | --- |
| `POST /api/v1/auth/login` | JSON: `username`, `password` | 200, para tokenów |
| `POST /api/v1/auth/register` | Access token administratora; JSON: `username`, `password`, opcjonalnie `role` | 201, użytkownik bez hasha hasła |
| `POST /api/v1/auth/refresh` | `Authorization: Bearer <refresh_token>` | 200, nowa para tokenów |
| `POST /api/v1/auth/logout` | `Authorization: Bearer <refresh_token>` | 204 |
| `GET /api/v1/auth/me` | `Authorization: Bearer <access_token>` | 200, `user_id`, `username`, `role` |

Domyślna rola nowego konta to `user`; przypisanie `admin` wymaga bieżących uprawnień administratora.
Uprawnienia pochodzą z rekordu użytkownika w bazie, a nie z deklaracji klienta lub roli w JWT.
Nieprawidłowe uwierzytelnienie daje 401, brak uprawnień 403, istniejący login 409, niepoprawny JSON 422.
Błędy infrastruktury bazy są mapowane na ogólny komunikat 503.
Odpowiedzi walidacji nie zawierają wartości wejściowych, aby nie ujawniać haseł.

W bazie zapisywany jest wyłącznie SHA-256 refresh tokenu. Rotacja usuwa starą sesję i zapisuje nową
w jednej transakcji. Ponowne użycie starego tokenu zwraca 401, również przy równoczesnych żądaniach.
Wylogowanie usuwa wskazaną sesję. Access token pozostaje ważny do wygaśnięcia, zgodnie z zakresem MVP.
Wygasłe rekordy sesji są odrzucane; moduł nie dodaje zadania okresowego ich czyszczenia.

## Testy

Z głównego katalogu repozytorium, przy działającym Docker Desktop:

```powershell
python -m pytest -q
```

Testy API uruchamiają własny, tymczasowy kontener TimescaleDB. Baza powstaje raz na sesję,
wykorzystuje pełne skrypty `db/init`, jest czyszczona przed i po każdym teście,
a po sesji kontener zostaje usunięty. Testy wykonują się kolejno.
Nie trzeba uruchamiać stosu aplikacji ani ustawiać `TEST_DATABASE_URL`.

Testy jednostkowe bez Dockera:

```powershell
python -m pytest -m "not integration" -q
```

Strukturę katalogów, fixtures i przykłady seedowania opisuje [instrukcja testów](tests/README.md).
