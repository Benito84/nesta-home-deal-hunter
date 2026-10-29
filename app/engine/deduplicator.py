"""
Moduł deduplikacji i klastrowania ofert dla Szczecina.
Łączy ogłoszenia tej samej fizycznej nieruchomości wystawione w wielu biurach lub na różnych portalach.
Wykrywa także obniżki cen (Price Drop Tracker).
"""

from typing import Optional, Tuple
from sqlmodel import Session, select
from app.models.listing import Listing, PropertyCluster, PriceDropEvent

def find_or_create_cluster(
    session: Session,
    district: str,
    area_m2: float,
    price_pln: float,
    floor: Optional[int] = None,
    street: Optional[str] = None
) -> Tuple[PropertyCluster, bool]:
    """
    Szuka pasującego klastra w obrębie:
    - ta sama dzielnica
    - metraż +/- 1.5 m2
    - to samo piętro (jeśli określone)
    Zwraca (klaster, is_new: bool)
    """
    query = select(PropertyCluster).where(
        PropertyCluster.district == district,
        PropertyCluster.approximate_area_m2 >= area_m2 - 1.5,
        PropertyCluster.approximate_area_m2 <= area_m2 + 1.5
    )
    if floor is not None:
        query = query.where(PropertyCluster.floor == floor)

    candidates = session.exec(query).all()
    for cluster in candidates:
        # Sprawdzamy czy którekolwiek ogłoszenie w klastrze ma cenę w granicach +/- 12%
        for item in cluster.listings:
            if abs(item.price_pln - price_pln) / price_pln <= 0.12:
                return cluster, False

    # Jeśli nie znaleziono kandydata, tworzymy nowy klaster
    new_cluster = PropertyCluster(
        district=district,
        approximate_area_m2=area_m2,
        floor=floor,
        street=street
    )
    session.add(new_cluster)
    session.commit()
    session.refresh(new_cluster)
    return new_cluster, True


def check_price_drop(
    session: Session,
    existing_listing: Listing,
    new_price_pln: float
) -> Optional[PriceDropEvent]:
    """
    Weryfikuje czy nastąpiła zmiana ceny i rejestruje zdarzenie PriceDropEvent.
    """
    if existing_listing.price_pln > new_price_pln:
        old_price = existing_listing.price_pln
        drop_pct = round((old_price - new_price_pln) / old_price, 4)
        drop_event = PriceDropEvent(
            listing_id=existing_listing.id,
            old_price_pln=old_price,
            new_price_pln=new_price_pln,
            drop_pct=drop_pct
        )
        existing_listing.price_pln = new_price_pln
        session.add(drop_event)
        session.add(existing_listing)
        session.commit()
        return drop_event
    return None
