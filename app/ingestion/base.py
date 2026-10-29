from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseConnector(ABC):
    """Abstrakcyjny interfejs dla wszystkich konektorów pozyskiwania ofert"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Nazwa źródła (np. infoludek, olx, komornik)"""
        pass

    @abstractmethod
    def fetch_listings(self) -> List[Dict[str, Any]]:
        """Pobiera i zwraca listę surowych ofert w ujednoliconym słowniku"""
        pass
