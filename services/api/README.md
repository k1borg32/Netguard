# NetGuard API

API jest zorganizowane w pionowe wycinki funkcjonalne (Vertical Slice Architecture)
z lekkim CQRS. Pełny opis struktury i zasad rozbudowy: [ARCHITECTURE.md](ARCHITECTURE.md).

Każdy przypadek użycia znajduje się w `app/features/<obszar>/<operacja>/`:
`controller.py`, `request.py`, `command.py` albo `query.py`, `handler.py`,
`response.py` i lokalne `dependencies.py`. Pliki powstają tylko tam, gdzie są potrzebne.

Handlery wykonują zapytania bezpośrednio przez asynchroniczne sesje SQLAlchemy.
Domena zawiera modele Pythona; definicje tabel i mapowania ORM są w infrastrukturze.
Zależności składa FastAPI `Depends`, lokalnie w każdym wycinku.

## Konfiguracja i uruchomienie

Zainstaluj zależności z `requirements.txt`. Ustaw `DATABASE_URL` oraz `JWT_SECRET`
w środowisku albo w głównym pliku `.env`. Sekret JWT powinien być losowy i prywatny.
AuthX 1.7.1 używa HS256. Access token jest ważny 15 minut, refresh token 7 dni.

Z katalogu `services/api`, po aktywacji środowiska:

```powershell
python -m app.app
```

Ten sposób uruchomienia ustawia na Windows pętlę zdarzeń wymaganą przez psycopg async.
Kontener Linux nadal uruchamia `uvicorn app.app:app --host 0.0.0.0 --port 8000`.
Dokumentacja HTTP jest dostępna pod `/docs`, a schemat pod `/openapi.json`.

API korzysta z istniejącego schematu bazy. Nie wykonuje automatycznych migracji.
Tabela `auth_refresh_sessions` znajduje się w `db/init/001_schema.sql`;
nowy wolumen bazy tworzy ją automatycznie. Istniejąca baza bez tej tabeli wymaga
osobnego zastosowania jej definicji i indeksów z tego pliku.
Nie uruchamiaj całego skryptu bootstrap na istniejącej bazie.

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
| `GET /health/ping` | Brak | 200, `{"status": "ok"}` |
| `POST /api/v1/auth/login` | JSON: `username`, `password` | 200, para tokenów |
| `POST /api/v1/auth/register` | Access token administratora; JSON: `username`, `password`, opcjonalnie `role` | 201, użytkownik bez hasha hasła |
| `POST /api/v1/auth/refresh` | `Authorization: Bearer <refresh_token>` | 200, nowa para tokenów |
| `POST /api/v1/auth/logout` | `Authorization: Bearer <refresh_token>` | 204 |
| `GET /api/v1/auth/me` | `Authorization: Bearer <access_token>` | 200, `user_id`, `username`, `role` |

Domyślna rola nowego konta to `user`; przypisanie `admin` wymaga bieżących uprawnień administratora.
Uprawnienia pochodzą z rekordu użytkownika w bazie.
Nieprawidłowe uwierzytelnienie daje 401, brak uprawnień 403, istniejący login 409, niepoprawny JSON 422.
Błędy SQLAlchemy są mapowane na ogólny komunikat 503.
Odpowiedzi walidacji nie zawierają wartości wejściowych, aby nie ujawniać haseł.

W bazie zapisywany jest wyłącznie SHA-256 refresh tokenu. Rotacja usuwa starą sesję i zapisuje nową
w jednej transakcji. Ponowne użycie starego tokenu zwraca 401, również przy równoczesnych żądaniach.
Wylogowanie usuwa wskazaną sesję. Access token pozostaje ważny do wygaśnięcia.
Wygasłe rekordy sesji są odrzucane; moduł nie dodaje zadania okresowego ich czyszczenia.

## Zakres weryfikacji

Refaktor obejmuje wyłącznie API. Na tym etapie nie dodawano, nie migrowano ani nie uruchamiano testów.
Istniejące testy korzystające ze starych importów wymagają dostosowania do nowej architektury.
