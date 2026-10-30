import os
from pathlib import Path
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy import event
from sqlalchemy.engine import Engine
from app.core.config import settings

# Upewnij się, że katalog na bazę danych istnieje
db_file = settings.DATABASE_URL.replace("sqlite:///", "")
db_dir = Path(db_file).parent
db_dir.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False}
)

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Włączenie trybu WAL i optymalizacja współbieżności SQLite"""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()

def init_db():
    from app.models.listing import Listing, PropertyCluster, PriceDropEvent
    from app.models.benchmarks import DistrictBenchmark, GoldenRule, UserFeedbackHistory, SystemPromptSetting
    from app.models.source import ScraperSource
    SQLModel.metadata.create_all(engine)
    
    # Migracja brakujących kolumn (Sekcja 4.5)
    with engine.connect() as conn:
        try:
            cols = [r[1] for r in conn.exec_driver_sql("PRAGMA table_info(listings)").fetchall()]
            if cols and "content_hash" not in cols:
                conn.exec_driver_sql("ALTER TABLE listings ADD COLUMN content_hash VARCHAR")
                conn.commit()
            if cols and "published_at" not in cols:
                conn.exec_driver_sql("ALTER TABLE listings ADD COLUMN published_at DATETIME")
                conn.commit()

            gr_cols = [r[1] for r in conn.exec_driver_sql("PRAGMA table_info(golden_rules)").fetchall()]
            if gr_cols and "source" not in gr_cols:
                conn.exec_driver_sql("ALTER TABLE golden_rules ADD COLUMN source VARCHAR DEFAULT 'manual'")
                conn.commit()
        except Exception as e:
            print(f"[DB Migration Warning]: {e}")

    seed_default_benchmarks()
    seed_default_sources()

def get_session():
    with Session(engine) as session:
        yield session

def seed_default_benchmarks():
    """Wypełnia domyślne benchmarki rynkowe dla Szczecina oraz dyrektywy promptu AI, jeśli tabela jest pusta"""
    from app.models.benchmarks import DistrictBenchmark, GoldenRule, SystemPromptSetting
    from app.core.calculator import DEFAULT_DISTRICT_RATES

    with Session(engine) as session:
        # 1. System Prompt Directives (bezpieczne przy wielu workerach)
        try:
            existing_setting = session.query(SystemPromptSetting).filter(SystemPromptSetting.key == "global_directives").first()
            if not existing_setting:
                setting = SystemPromptSetting(
                    key="global_directives",
                    custom_directives="""- Odrzucaj wszelkie ogłoszenia, które są reklamami skupu nieruchomości, pomocy prawnej, pożyczek lub zapytaniami 'kupię'.
- Zwracaj szczególną uwagę na oficyny i kondygnacje parterowe w kamienicach (ryzyko zawilgocenia, ciemnych podwórek i braku nasłonecznienia).
- W przypadku ogrzewania piecami kaflowymi, traktuj to jako dźwignię do twardych negocjacji cenowych, o ile w budynku jest pion gazowy lub sieć SEC.
- Nie akceptujemy ofert, w których przedmiotem transakcji jest tylko ułamek/udział (np. 1/2 lub 1/4 lokalu bez czystej KW).
- Mieszkania na 4. piętrze w kamienicy lub bloku bez windy wymagają dyskonta cenowego min. 8% z uwagi na dłuższą odsprzedaż."""
                )
                session.add(setting)
                session.commit()
        except Exception:
            session.rollback()

        # 2. Benchmarks
        try:
            existing = session.query(DistrictBenchmark).first()
            if not existing:
                for district_name, rates in DEFAULT_DISTRICT_RATES.items():
                    bm = DistrictBenchmark(
                        district=district_name,
                        avg_renovation_m2=rates["avg_renovation_m2"],
                        ready_min_m2=rates["ready_min_m2"],
                        ready_avg_m2=rates["ready_avg_m2"],
                        ready_max_m2=rates["ready_max_m2"],
                        active=True
                    )
                    session.add(bm)
                
                # Wstępne Złote Zasady Nesta Home
                default_rules = [
                    GoldenRule(rule_text="Piece kaflowe w kamienicy w Śródmieściu to nasz atut i pole do negocjacji, a nie powód do odrzucenia. Janek ma opanowaną instalację gazową/SEC.", category="heating", weight=1.2),
                    GoldenRule(rule_text="Mieszkania 38-55 m2 o układzie 2-3 pokoje mają najwyższy priorytet i najszybszą płynność (sweet spot).", category="layout", weight=1.5),
                    GoldenRule(rule_text="Mieszkania powyżej 70 m2 akceptujemy tylko przy drastycznym dyskoncie cenowym (min. 25% poniżej rynku) w topowych lokalizacjach (Pogodno, Centrum).", category="area", weight=1.0),
                    GoldenRule(rule_text="Ostatnie piętro (4. p) w kamienicy lub bloku bez windy wymaga dodatkowego dyskonta min. 8% z uwagi na dłuższą sprzedaż.", category="floor", weight=1.1)
                ]
                for r in default_rules:
                    session.add(r)

                session.commit()
        except Exception:
            session.rollback()

def seed_default_sources():
    """Inicjalizuje rejestr źródeł, aktywne scrapery oraz kolejkę backlogu"""
    from app.models.source import ScraperSource
    from sqlmodel import select

    with Session(engine) as session:
        existing = session.query(ScraperSource).first()
        if not existing:
            default_sources = [
                # Aktywne scrapery (Live)
                ScraperSource(
                    code="infoludek",
                    name="infoludek.pl",
                    url="https://ogloszenia.infoludek.pl/ogloszenia/kategorie/short/nieruchomosci-sprzedam-mieszkania.xhtml",
                    tier="Tier 1: Poza radarem",
                    is_active=True,
                    status="PENDING",
                    notes="Lokalny portal Szczecina, ogłoszenia bezpośrednie od osób starszych i właścicieli"
                ),
                ScraperSource(
                    code="sprzedajemy",
                    name="Sprzedajemy.pl",
                    url="https://sprzedajemy.pl/szczecin/nieruchomosci/mieszkania",
                    tier="Tier 1: Poza radarem",
                    is_active=True,
                    status="PENDING",
                    notes="Ogłoszenia drobne, wysoki udział ofert prywatnych bez pośrednika"
                ),
                ScraperSource(
                    code="elicytacje",
                    name="E-Licytacje Komornicze Szczecin",
                    url="https://licytacje.komornik.pl/wyszukiwarka/obwieszczenia-o-licytacji",
                    tier="Tier 1: Poza radarem",
                    is_active=True,
                    status="PENDING",
                    notes="Krajowa Rada Komornicza: Sąd Rejonowy Szczecin-Centrum i Szczecin-Prawobrzeże (dyskont 25-34%)"
                ),
                ScraperSource(
                    code="zbilk",
                    name="ZBiLK Szczecin (Mieszkania komunalne i przetargi)",
                    url="https://zbilk.szczecin.pl/?type=wykazy&action=view&id=32",
                    tier="Tier 1: Poza radarem",
                    is_active=True,
                    status="PENDING",
                    notes="Zarząd Budynków i Lokali Komunalnych - pustostany do remontu i lokale w kamienicach Szczecina"
                ),
                ScraperSource(
                    code="gratka",
                    name="Gratka.pl Szczecin",
                    url="https://gratka.pl/nieruchomosci/mieszkania/szczecin/sprzedaz?sort=created_at:desc",
                    tier="Tier 2: Portale i IMAP",
                    is_active=True,
                    status="PENDING",
                    notes="Kamienice i rynek wtórny, pełne parametry techniczne"
                ),
                ScraperSource(
                    code="olx",
                    name="OLX Szczecin",
                    url="https://www.olx.pl/nieruchomosci/mieszkania/sprzedaz/szczecin/?search%5Border%5D=created_at%3Adesc",
                    tier="Tier 2: Portale i IMAP",
                    is_active=True,
                    status="PENDING",
                    notes="Największy wolumen bieżących ogłoszeń ze Szczecina"
                ),
                ScraperSource(
                    code="otodom",
                    name="Otodom.pl Szczecin",
                    url="https://www.otodom.pl/pl/wyniki/sprzedaz/mieszkanie/zachodniopomorskie/szczecin/szczecin/szczecin?limit=36&ownerTypeSingleSelect=ALL&by=LATEST&direction=DESC",
                    tier="Tier 2: Portale i IMAP",
                    is_active=True,
                    status="PENDING",
                    notes="Wiodący portal nieruchomości w Polsce, bezpośredni parser JSON bez ryzyka blokad"
                ),
                ScraperSource(
                    code="email_imap",
                    name="Skrzynka IMAP (Otodom/OLX)",
                    url="imap://settings",
                    tier="Tier 2: Portale i IMAP",
                    is_active=True,
                    status="PENDING",
                    notes="Architektura Zero-Ban: natywny odbiór powiadomień e-mail bez ryzyka blokady IP"
                ),
                ScraperSource(
                    code="spoldzielnie",
                    name="Przetargi Spółdzielni Szczecińskich",
                    url="https://smsrodmiescie.szczecin.pl/przetargi",
                    tier="Tier 1: Poza radarem",
                    is_active=True,
                    status="PENDING",
                    notes="SM Śródmieście, SM Dąb, SM Wspólny Dom, SM Kolejarz - lokale z odzysku i przetargi"
                ),
                ScraperSource(
                    code="lento",
                    name="Lento.pl Szczecin",
                    url="https://szczecin.lento.pl/nieruchomosci/mieszkania/sprzedaz.html",
                    tier="Tier 1: Poza radarem",
                    is_active=True,
                    status="PENDING",
                    notes="Ogłoszenia drobne, duży odsetek ofert bezpośrednich od osób starszych i spadkobierców"
                ),
                ScraperSource(
                    code="kurier",
                    name="24Kurier.pl Szczecin (Drobne)",
                    url="https://24kurier.pl/ogloszenia/nieruchomosci/",
                    tier="Tier 1: Poza radarem",
                    is_active=True,
                    status="PENDING",
                    notes="Ogłoszenia prasowe i drobne z regionu Szczecina - wydanie Kuriera Szczecińskiego"
                ),
                # Kolejka do oprogramowania (Backlog)
                ScraperSource(
                    code="fb_groups",
                    name="Grupy Mieszkaniowe Facebook",
                    url="https://www.facebook.com/groups/nieruchomosciszczecin",
                    tier="Kolejka: Do analizy",
                    is_active=False,
                    status="QUEUED",
                    notes="Grupy 'Mieszkania Szczecin bez pośredników' (wymaga sesji przeglądarki Playwright)"
                )
            ]
            for s in default_sources:
                session.add(s)
            session.commit()
        else:
            # Aktywacja elicytacje i zbilk w istniejącej bazie (Priorytet 1 i 2)
            elicytacje = session.exec(select(ScraperSource).where(ScraperSource.code == "elicytacje")).first()
            if elicytacje and not elicytacje.is_active:
                elicytacje.is_active = True
                elicytacje.tier = "Tier 1: Poza radarem"
                elicytacje.name = "E-Licytacje Komornicze Szczecin"
                elicytacje.url = "https://licytacje.komornik.pl/wyszukiwarka/obwieszczenia-o-licytacji"
                elicytacje.status = "PENDING"
                elicytacje.notes = "Krajowa Rada Komornicza: Sąd Rejonowy Szczecin-Centrum i Szczecin-Prawobrzeże (dyskont 25-34%)"
                session.add(elicytacje)

            zbilk = session.exec(select(ScraperSource).where(ScraperSource.code == "zbilk")).first()
            if zbilk and not zbilk.is_active:
                zbilk.is_active = True
                zbilk.tier = "Tier 1: Poza radarem"
                zbilk.name = "ZBiLK Szczecin (Mieszkania komunalne i przetargi)"
                zbilk.url = "https://zbilk.szczecin.pl/?type=wykazy&action=view&id=32"
                zbilk.status = "PENDING"
                zbilk.notes = "Zarząd Budynków i Lokali Komunalnych - pustostany do remontu i lokale w kamienicach Szczecina"
                session.add(zbilk)

            otodom = session.exec(select(ScraperSource).where(ScraperSource.code == "otodom")).first()
            if not otodom:
                otodom_src = ScraperSource(
                    code="otodom",
                    name="Otodom.pl Szczecin",
                    url="https://www.otodom.pl/pl/wyniki/sprzedaz/mieszkanie/zachodniopomorskie/szczecin/szczecin/szczecin?limit=36&ownerTypeSingleSelect=ALL&by=LATEST&direction=DESC",
                    tier="Tier 2: Portale i IMAP",
                    is_active=True,
                    status="PENDING",
                    notes="Wiodący portal nieruchomości w Polsce, bezpośredni parser JSON bez ryzyka blokad"
                )
                session.add(otodom_src)
            elif not otodom.is_active:
                otodom.is_active = True
                session.add(otodom)

            # Priorytet 3: Przetargi spółdzielni mieszkaniowych
            sm_src = session.exec(select(ScraperSource).where(ScraperSource.code.in_(["spoldzielnie", "sm_srodmiescie"]))).first()
            if not sm_src:
                sm_new = ScraperSource(
                    code="spoldzielnie",
                    name="Przetargi Spółdzielni Szczecińskich",
                    url="https://smsrodmiescie.szczecin.pl/przetargi",
                    tier="Tier 1: Poza radarem",
                    is_active=True,
                    status="PENDING",
                    notes="SM Śródmieście, SM Dąb, SM Wspólny Dom, SM Kolejarz - lokale z odzysku i przetargi"
                )
                session.add(sm_new)
            else:
                sm_src.code = "spoldzielnie"
                sm_src.is_active = True
                sm_src.tier = "Tier 1: Poza radarem"
                sm_src.name = "Przetargi Spółdzielni Szczecińskich"
                sm_src.url = "https://smsrodmiescie.szczecin.pl/przetargi"
                sm_src.notes = "SM Śródmieście, SM Dąb, SM Wspólny Dom, SM Kolejarz - lokale z odzysku i przetargi"
                session.add(sm_src)

            # Priorytet 5: Portale uzupełniające (Lento i 24kurier)
            lento_src = session.exec(select(ScraperSource).where(ScraperSource.code == "lento")).first()
            if not lento_src:
                lento_new = ScraperSource(
                    code="lento",
                    name="Lento.pl Szczecin",
                    url="https://szczecin.lento.pl/nieruchomosci/mieszkania/sprzedaz.html",
                    tier="Tier 1: Poza radarem",
                    is_active=True,
                    status="PENDING",
                    notes="Ogłoszenia drobne, duży odsetek ofert bezpośrednich od osób starszych i spadkobierców"
                )
                session.add(lento_new)
            elif not lento_src.is_active:
                lento_src.is_active = True
                session.add(lento_src)

            kurier_src = session.exec(select(ScraperSource).where(ScraperSource.code == "kurier")).first()
            if not kurier_src:
                kurier_new = ScraperSource(
                    code="kurier",
                    name="24Kurier.pl Szczecin (Drobne)",
                    url="https://24kurier.pl/ogloszenia/nieruchomosci/",
                    tier="Tier 1: Poza radarem",
                    is_active=True,
                    status="PENDING",
                    notes="Ogłoszenia prasowe i drobne z regionu Szczecina - wydanie Kuriera Szczecińskiego"
                )
                session.add(kurier_new)
            elif not kurier_src.is_active:
                kurier_src.is_active = True
                session.add(kurier_src)

            session.commit()
