# 🏢 Nesta Home Deal Hunter | Szczecin Real Estate Sourcing Engine

> Autonomiczny kombajn poszukiwania i ewaluacji okazji mieszkaniowych na flipa w Szczecinie, w 100% zintegrowany z **Nesta Home Master Tracker API v4.04**.

---

## 🎯 1. Cel i Profil Biznesowy

Aplikacja wspiera zespół spółki inwestycyjnej **Nesta Home** ([nestahome.pl](https://nestahome.pl)) w automatycznym pozyskiwaniu i selekcjonowaniu mieszkań na rynku wtórnym w Szczecinie. 

### Kluczowe Założenia Inwestycyjne Nesta Home:
* **Sweet Spot:** Mieszkania **38 m² – 55 m²** (układ 2–3 pokoje) o najwyższej płynności rynkowej i krótkim cyklu remontu (6–8 tygodni).
* **Segment szybkich obrotów:** Mieszkania **25 m² – 35 m²** (cykl obrotu < 90–120 dni).
* **Piece kaflowe w kamienicach = Główny Atut:** Zwykli kupujący omijają je szerokim łukiem, co pozwala wynegocjować drastycznie niższą cenę zakupu (4 500 – 6 200 zł/m² w Śródmieściu). Zespół Nesta (na czele z Kierownikiem Budowy Jankiem) posiada opanowany proces wymiany instalacji grzewczej (kocioł kondensacyjny 2-f lub miejska sieć SEC).
* **Twarda Bramka 1 („DZWONIMY”):**
  * Minimalny zwrot z całego zainwestowanego kapitału: **ROI $\ge$ 16.0%**.
  * Minimalny czysty zysk spółki: **$\ge$ 30 000 – 40 000 PLN** (po uwzględnieniu prowizji koordynatora 12% min. 10 000 zł, podatku PCC 2%, taksy notarialnej ~1 850 zł, mediów budowlanych i bufora negocjacyjnego 2%).
  * Koszty remontu: **Kamienica 1 900 zł/m²**, **Blok/Płyta 1 700 zł/m²**, **Nowe budownictwo 1 500 zł/m²**.

---

## 🛠️ 2. Architektura i Stack Technologiczny

Projekt zrealizowany w identycznym, ultra-lekkim i reaktywnym ekosystemie co Nesta Master Tracker:
* **Backend:** Python 3.12 + FastAPI + SQLModel / SQLAlchemy
* **Baza Danych:** SQLite zoptymalizowane w trybie **WAL (Write-Ahead Logging)** i `PRAGMA synchronous=NORMAL`
* **Interfejs Użytkownika:** Jinja2 SSR + Alpine.js v3 + Tailwind CSS (Styl Nesta Impeccable: kamienny minimalizm, Plus Jakarta Sans, Playfair Display, FontAwesome 6)
* **Silnik AI:** Google Gemini API (Structured Outputs w formacie Pydantic) z dynamicznym wstrzykiwaniem Złotych Zasad i ostatnich decyzji (Few-Shot Active Learning)
* **Powiadomienia:** Telegram Bot API (natychmiastowe karty alertów „DZWONIMY”)
* **Harmonogram zadań:** APScheduler w tle (cykliczny scraping co 30 minut)

---

## 📂 3. Struktura Katalogów

```text
friendly-euclid/
├── app/
│   ├── core/
│   │   ├── config.py           # SSOT Wersji (v4.16.0), konfiguracja .env
│   │   ├── database.py         # Silnik SQLite WAL (busy_timeout=5000), auto-migracje
│   │   ├── scheduler.py        # Harmonogram w tle (APScheduler)
│   │   ├── templates.py        # Globalna konfiguracja Jinja2
│   │   └── calculator.py       # Silnik finansowy Nesta (ROI 16%, ARV dzielnic, taksa MS, walk-away price)
│   ├── routers/                # Modularne routery domenowe (Sekcja 1.1)
│   │   ├── system.py           # /api/version (SSOT)
│   │   ├── feed.py             # Feed okazji i wielokryterialne filtry (/)
│   │   ├── scout.py            # /quick-ingest (Smart Ingest: Link, Print Screen, Tekst)
│   │   ├── benchmarks.py       # /benchmarks (stawki i złote zasady)
│   │   ├── sources.py          # /sources (status scraperów i testy na żywo)
│   │   ├── tracker.py          # Synchronizacja z Trackerem i feedback loop
│   │   └── manual.py           # /manual (Instrukcja obsługi i dossier 11 źródeł)
│   ├── schemas/                # Ścisłe kontrakty Pydantic v2 (Sekcja 4.3)
│   │   └── listing.py          # ScrapedListing, QuickIngestRequest, WebhookRequest
│   ├── models/
│   │   ├── listing.py          # Modele Listing (z content_hash), PropertyCluster, PriceDropEvent
│   │   ├── evaluation.py       # Schematy Pydantic dla AI Evaluator
│   │   └── benchmarks.py       # Matryca cenowa Szczecina, GoldenRule, UserFeedbackHistory
│   ├── engine/
│   │   ├── filter_engine.py    # Etap 1: Twarde filtry wstępne (oszczędność tokenów)
│   │   ├── smart_extractor.py  # Autonomiczny parser linków, zrzutów ekranu i tekstu
│   │   ├── fingerprint.py      # Fingerprinting ofert (SHA-256 cache)
│   │   ├── deduplicator.py     # Rozmyte łączenie ofert (±1.5 m², piętro, cena) i detekcja obniżek
│   │   └── ai_evaluator.py     # Google Gemini Structured Output + inteligentny fallback regułowy
│   ├── ingestion/
│   │   ├── base.py             # Abstrakcyjny interfejs BaseConnector
│   │   ├── otodom.py           # Otodom.pl (bezpośredni parser JSON curl_cffi)
│   │   ├── portals.py          # OLX Szczecin
│   │   ├── infoludek.py        # infoludek.pl (ogłoszenia prywatne Szczecin)
│   │   ├── sprzedajemy.py      # sprzedajemy.pl (oferty bezpośrednie)
│   │   ├── gratka.py           # gratka.pl (kamienice, rynek wtórny)
│   │   ├── komornik.py         # E-Licytacje komornicze (Krajowa Rada Komornicza)
│   │   ├── zbilk.py            # ZBiLK Szczecin (przetargi komunalne na pustostany)
│   │   ├── spoldzielnie.py     # Spółdzielnie Mieszkaniowe (Śródmieście, Dąb, Wspólny Dom)
│   │   ├── lento.py            # Lento.pl Szczecin
│   │   ├── kurier.py           # 24Kurier.pl (ogłoszenia drobne prasy tradycyjnej)
│   │   ├── email_imap.py       # IMAP Email Alert Parser
│   │   └── pipeline.py         # Główny potok przetwarzania i scoringu
│   ├── alerts/
│   │   └── telegram_bot.py     # Natychmiastowe powiadomienia na telefon
│   ├── integrations/
│   │   └── tracker_client.py   # Most do Poczekalni Nesta Master Tracker (POST /api/staging)
│   └── web/
│       └── templates/          # Szablony HTML (styl Impeccable, sand/stone palette)
├── scripts/
│   ├── deploy_mikrus.py        # Skrypt automatycznego wdrożenia na Mikr.us (systemd, venv, SFTP)
│   └── lint_dom_balance.py     # Linter balansu DOM (Sekcja 4.6)
├── main.py                     # Czysty punkt startowy (GZip, Static, Lifespan, Routery)
└── requirements.txt
```

---

## 🚀 4. Jak Uruchomić Aplikację

### Krok 1: Aktywacja środowiska wirtualnego
```powershell
.\venv\Scripts\activate
```

### Krok 2: Konfiguracja `.env`
Skopiuj `.env.example` do `.env` i uzupełnij klucze:
```ini
# Google Gemini (opcjonalny - aplikacja posiada pełny fallback algorytmiczny)
GEMINI_API_KEY=twoj_klucz_gemini

# Telegram Bot (opcjonalny - do powiadomień w telefonie)
TELEGRAM_BOT_TOKEN=twoj_token_bota
TELEGRAM_CHAT_ID=twoj_chat_id

# Nesta Master Tracker
TRACKER_ENV=DEV # lub PROD
TRACKER_DEV_URL=http://srv75.mikr.us:30120/api/staging
TRACKER_PROD_URL=http://srv75.mikr.us:20120/api/staging
```

### Krok 3: Uruchomienie Serwera
```powershell
.\venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
```
Aplikacja jest dostępna pod adresem: **http://localhost:8000**

---

## 📡 5. Integracja z Nesta Master Tracker (`POST /api/staging`)

Każda zakwalifikowana oferta na Tablicy Okazji posiada przycisk:
> **`Wyślij do Master Trackera`**

Kliknięcie przycisku mapuje ofertę 1:1 na oficjalną specyfikację v4.04:
* Przesyła metraż, cenę, dzielnicę, typ budynku, piętro, balkon, ogrzewanie, opis i dane kontaktowe.
* Oferta natychmiast pojawia się w Poczekalni Trackera na serwerze Mikrus z nadanym `staging_id`.
* Posiada obsługę flagi `force=true` przy wykryciu duplikatów.

---

## 🧠 6. Active Learning i Feedback Loop

AI w aplikacji uczy się preferencji zespołu Nesta Home na dwa sposoby:
1. **Złote Zasady (Golden Rules):** W zakładce *Kalibracja* można w prostym języku definiować własne reguły (np. *"W kamienicach na Niebuszewie partery akceptujemy tylko poniżej 5 000 zł/m²"*). Zasady są automatycznie wstrzykiwane do promptu Gemini.
2. **Przyciski Feedbacku:** Przy każdej ofercie znajdują się przyciski `Oględziny` oraz `Odrzuć` (z możliwością wpisania powodu). Ostatnie 5 decyzji z uzasadnieniem trafia jako kontekst Few-Shot do każdej nowej oceny AI.
