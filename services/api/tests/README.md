# Testy API

Testy dzielimy na `unit/` i `integration/`. Nie używamy mocków, atrap repozytoriów,
podmian handlerów ani `app.dependency_overrides`.

## Unit

Testujemy modele z `app/domain` w pamięci: reguły domenowe, przejścia stanów
i relacje. Bez HTTP, bazy danych i Dockera. Obecne modele nie mają metod
biznesowych, więc przykłady sprawdzają spójność relacji konfiguracja–detekcja–alert.
Ograniczenia egzekwowane przez SQL wymagają testów integracyjnych.

## Integration

Testujemy cały przepływ przez `client`: HTTP → kontroler → handler → rzeczywiste
repozytorium, Argon2 i JWT → lokalna baza TimescaleDB → odpowiedź HTTP.

- Osobny projekt Docker Compose powstaje raz na sesję, na losowym lokalnym porcie.
- Schemat pochodzi z produkcyjnych skryptów `db/init/*.sql`.
- Nie korzystamy z aplikacyjnego `DATABASE_URL`, istniejącej bazy ani jej wolumenu.
- Przed i po **każdym** teście integracyjnym czyścimy wszystkie tabele aplikacji
  przez `TRUNCATE ... RESTART IDENTITY CASCADE`, również po nieudanym teście.
- Klient powstaje na każdy test, z cyklem startu i zamknięcia aplikacji.
- Po sesji usuwamy kontener i dane testowe.
- Testy wykonują się kolejno. Główny `conftest.py` odrzuca uruchomienie
  z workerami pytest-xdist (`-n auto`, `-n 2` itd.). Nie instalujemy xdist.
- Brak działającego Dockera lub błędny schemat powoduje błąd, a nie pominięcie testów.

Fixtures w `integration/conftest.py`:

| Fixture | Zakres | Przeznaczenie |
| --- | --- | --- |
| `database_url` | sesja | Tymczasowy lokalny kontener i jego adres |
| `api_environment` | sesja | Konfiguracja prawdziwych zależności API |
| `db` | test, automatyczna | Czyszczenie i rzeczywiste połączenie psycopg do asercji SQL |
| `client` | test | `TestClient` prawdziwej aplikacji |
| `create_user` | test | Przygotowanie konta przez prawdziwe repozytorium i Argon2 |

Pierwszego administratora przygotowujemy przez `create_user(role=UserRole.ADMIN)`.
Rejestrację kolejnych użytkowników sprawdzamy przez endpoint HTTP.
Nie opieramy izolacji na rollbacku: żądania HTTP zatwierdzają dane na osobnych połączeniach.
Nowe pliki dostają marker `unit` lub `integration` automatycznie na podstawie katalogu.
Każdy test przygotowuje własne dane; nie zależy od kolejności innych testów.

## Uruchamianie

Z katalogu `services/api`, z aktywnym środowiskiem Python:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest tests/unit -q
python -m pytest tests/integration -q
python -m pytest tests -q
```

Testy integracyjne wymagają działającego Docker Desktop z kontenerami Linux.
Nie trzeba uruchamiać całego stosu aplikacji ani ustawiać `.env`.
Konfiguracja pytest jest wspólna, w głównym `pyproject.toml` repozytorium.
Z głównego katalogu wybieraj `services/api/tests` albo użyj `make test-int`.
