# Architektura API

API stosuje Vertical Slice Architecture i lekkie CQRS, wzorowane na projekcie Tutoring.
Kod grupujemy według przypadków użycia. Każdy wycinek zawiera kompletną obsługę operacji HTTP.
Nie ma wspólnego repozytorium, Unit of Work ani osobnej warstwy Application.

## Struktura

```text
app/
  app.py                         # składanie aplikacji i cykl życia
  exception_handlers.py          # translacja błędów na odpowiedzi HTTP
  features/
    auth/
      router.py                  # wyłącznie rejestracja routerów wycinków
      common/
        authentication.py        # JWT z nagłówka i sprawdzanie ról
        dependencies.py          # współdzielone usługi bezpieczeństwa
      exceptions/                # błędy współdzielone w obszarze auth
      login/
        controller.py            # endpoint i mapowanie request -> command
        request.py               # walidacja kontraktu HTTP
        command.py               # dane przypadku użycia
        handler.py               # operacja, zapytania i zapis transakcji
        response.py              # niezależny kontrakt odpowiedzi
        dependencies.py          # lokalna fabryka handlera
      register/                  # ten sam układ
      refresh/                   # token z nagłówka, bez sztucznego request body
      logout/                    # 204, bez sztucznego modelu odpowiedzi
      me/                        # query zamiast command, bez request body
    health/ping/
      controller.py
      query.py
      handler.py
      response.py
    common/
      app_exception.py
      dependencies.py            # typ zależności sesji
  domain/                        # modele Pythona i reguły domenowe
    user.py
    user_role.py
    refresh_session.py
    detection.py
    detection_config.py
    alert.py
    network_flow.py
  infrastructure/
    config.py
    database.py                  # engine, sessionmaker, sesja na żądanie
    bootstrap_admin.py           # interaktywne narzędzie administracyjne
    persistence/
      tables.py                  # tabele, kolumny, typy PostgreSQL
      mappings.py                # mapowania ORM i relacje
    security/
      contracts.py               # protokoły hashera i wystawcy tokenów
      models.py                  # wyniki wystawiania i weryfikacji tokenów
      password_hasher.py
      token_issuer.py
      authx_config.py
```

## Zależności i przepływ

`features -> infrastructure -> domain`, a także `features -> domain`.
Domena nie importuje FastAPI, SQLAlchemy ani kodu infrastruktury.
Mapowania imperatywne SQLAlchemy są rejestrowane przy składaniu aplikacji.
Definicje kolumn i relacji pozostają w infrastrukturze.

Kontroler przyjmuje request albo zweryfikowany kontekst HTTP, tworzy komendę/zapytanie,
wywołuje handler i oddaje jego wynik. Każdy handler jest składany przez własną fabrykę
w `dependencies.py` tego samego wycinka. FastAPI `Depends` wystarcza do kompozycji;
nie ma dodatkowego kontenera ani odpowiednika MediatR.

Command oznacza operację zmieniającą stan; query oznacza odczyt.
Oddzielne modele są zwykłymi dataclasses, a request/response są modelami Pydantic.
Handler zwraca odpowiedź swojego wycinka, nie encję z hashem hasła.
Wycinki nie importują kontrolerów, handlerów ani odpowiedzi innych wycinków.
Powtórzenie kilku pól kontraktu HTTP jest celowe: zmiana odpowiedzi logowania
nie zmienia automatycznie kontraktu odświeżania tokenów.

## Baza i transakcje

Handlery korzystają bezpośrednio z `AsyncSession` SQLAlchemy 2 i sterownika psycopg.
Jedno żądanie korzysta z jednej sesji, również przy kontroli uprawnień.
Zapis kończy się jawnym `await session.commit()` w handlerze.
Zamknięcie sesji wycofuje niedokończone transakcje przy błędzie.
Odczyty używają projekcji kolumn; nie ładują śledzonych encji ani zbędnych pól.
To odpowiednik odczytów `AsNoTracking` ze wzorca C#.

Rejestracja obsługuje konflikt unikalnego loginu również przy równoległych żądaniach.
Rotacja refresh tokenu usuwa starą sesję przez `DELETE ... RETURNING` i zapisuje nową
w jednej transakcji. Blokada wiersza pozwala wygrać tylko jednemu równoległemu żądaniu.
W bazie znajduje się SHA-256 tokenu, a nie jego jawna wartość.
Haszowanie i weryfikacja haseł działają poza pętlą obsługującą asynchroniczne żądania.

Relacje ORM mają `lazy="raise"`: przyszłe wycinki muszą jawnie doładowywać potrzebne
relacje, np. przez `selectinload`, aby nie wywoływać ukrytych operacji I/O.
Mapowania odzwierciedlają istniejącą bazę, w tym nullowalne pola i `detections.trace_ids`.
API nie uruchamia `create_all` ani migracji. Skrypty inicjalizacyjne bazy pozostają poza API.
Bootstrap administratora pozostaje osobnym synchronicznym poleceniem psycopg z blokadą tabeli.

## Kolejny przypadek użycia

1. Utwórz `features/<obszar>/<przypadek_użycia>/`.
2. Dodaj lokalny kontroler, handler, command albo query i potrzebne kontrakty HTTP.
3. Dodaj lokalną fabrykę zależności, jeżeli handler wymaga usług.
4. Zarejestruj router w routerze obszaru lub w `create_app()`.
5. Pisz zapytania bezpośrednio w handlerze; transakcję zapisu zatwierdzaj przed zwróceniem odpowiedzi.
6. Reguły domenowe umieszczaj w domenie, a mapowania w `infrastructure/persistence`.

Na tym etapie nie dodawano, nie migrowano ani nie uruchamiano testów.
Istniejące testy odwołujące się do usuniętych repozytoriów i importów wymagają osobnej migracji.
