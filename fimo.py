from pydantic import BaseModel
from datetime import datetime
from enum import Enum
from typing import List, Optional
from pathlib import Path
import csv
import glob

class User(Enum):
    MARTIN = "MARTIN"
    LIANE = "LIANE"

class Label(Enum):
    DAILY = "DAILY"
    COMMON_PERIODIC = "COMMON_PERIODIC"
    COMMON_ONETIME = "COMMON_ONETIME"

class KontoRecord(BaseModel):
    """Repräsentiert einen Eintrag aus einem Kontoauszug oder einen manuellen Finanzvorgang."""

    date: datetime
    spender: User
    client: Optional[User]
    value: int
    # Referenz auf Ursprungsdatensatz
    receiver: str
    purpose: str
    labels: List[Label]

class DKBKontoImporter:

    def __init__(self, srcpath: Path):
        self._srcpath = srcpath

    def do_import(self) -> List[KontoRecord]:
        files = glob.glob(self._srcpath + "/*.csv")
        records = []
        for filepath in files:
            records.extend(self._import_file(filepath))

        return records

    @staticmethod
    def _import_file(filepath: Path) -> List[KontoRecord]:
        with open(filepath, "r", encoding='iso-8859-1') as f:
            lines = f.readlines()
        for i, line in enumerate(lines):
            if line.startswith('"Buchungstag"'):
                break
        del lines[:i]

        reader = csv.DictReader(lines, delimiter=';', quotechar='"')
        records = []

        for row in reader:
            records.append(KontoRecord(date = datetime.strptime(row["Buchungstag"], '%d.%m.%Y'),
                                       spender = User.MARTIN,
                                       client = None,
                                       value = int(row["Betrag (EUR)"].replace(",","").replace(".", "")),
                                       receiver = row["Auftraggeber / Begünstigter"],
                                       purpose = row["Verwendungszweck"],
                                       labels = []))

        return records

class DKBKontoMartinImporter(DKBKontoImporter):
    def __init__(self):
        super().__init__("/home/kapuze/Shit/2007 DKB/csv/konto/")

class Monitor:

    def __init__(self):
        self._records = []

    def monitor(self):
        self._records.extend(DKBKontoMartinImporter().do_import())

        print(self._records)
