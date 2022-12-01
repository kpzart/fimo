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

class DKBImporter:

    def __init__(self, srcpath: Path):
        self._srcpath = srcpath

    def do_import(self) -> List[KontoRecord]:
        files = glob.glob(self._srcpath + "/*.csv")
        records = []
        for filepath in files:
            records.extend(self._import_file(filepath))

        return records

    def _import_file(self, filepath: Path) -> List[KontoRecord]:
        with open(filepath, "r", encoding='iso-8859-1') as f:
            lines = f.readlines()
        for i, line in enumerate(lines):
            if line.startswith(f'{self.FIRST_HEADING}'):
                break
        del lines[:i]

        reader = csv.DictReader(lines, delimiter=';', quotechar='"')
        records = []

        for row in reader:
            records.append(KontoRecord(date = datetime.strptime(row[self.HEADING_DATE], '%d.%m.%Y'),
                                       spender = self.SPENDER,
                                       client = None,
                                       value = int(row[self.HEADING_VALUE].replace(",","").replace(".", "")),
                                       receiver = row[self.HEADING_RECEIVER],
                                       purpose = row[self.HEADING_PURPOSE],
                                       labels = []))

        return records


class DKBKontoImporter(DKBImporter):

    SPENDER = User.MARTIN
    HEADING_DATE = "Buchungstag"
    HEADING_VALUE = "Betrag (EUR)"
    HEADING_RECEIVER = "Auftraggeber / Begünstigter"
    HEADING_PURPOSE = "Verwendungszweck"
    FIRST_HEADING = '"Buchungstag"'

    def __init__(self, filepath: Path):
        super().__init__(filepath)


class DKBKontoMartinImporter(DKBKontoImporter):
    def __init__(self):
        super().__init__("/home/kapuze/Shit/2007 DKB/csv/konto/")


class DKBVisaImporter(DKBImporter):

    SPENDER = User.MARTIN
    HEADING_DATE = "Belegdatum"
    HEADING_VALUE = "Betrag (EUR)"
    HEADING_RECEIVER = ""
    HEADING_PURPOSE = "Beschreibung"
    FIRST_HEADING = '"Umsatz abgerechnet und nicht im Saldo enthalten"'

    def __init__(self, filepath: Path):
        super().__init__(filepath)


class DKBVisaMartinImporter(DKBVisaImporter):
    def __init__(self):
        super().__init__("/home/kapuze/Shit/2007 DKB/csv/visa/")


class IngDiBaImporter(DKBImporter):

    SPENDER = User.LIANE
    HEADING_DATE = "Buchung"
    HEADING_VALUE = "Betrag"
    HEADING_RECEIVER = "Auftraggeber/Empfänger"
    HEADING_PURPOSE = "Verwendungszweck"
    FIRST_HEADING = "Buchung"

    def __init__(self, filepath: Path):
        super().__init__(filepath)


class IngDiBaLianeImporter(IngDiBaImporter):
    def __init__(self):
        super().__init__("/home/kapuze/Nextcloud/matlantis_ocloud/LöwiMiez/Finanzen/Miez/")


class Monitor:

    def __init__(self):
        self._records = []

    def monitor(self):
        self._records.extend(DKBKontoMartinImporter().do_import())

        print(self._records)

def test_import_martin_dkb_konto():
    assert len(DKBKontoMartinImporter().do_import())

def test_import_martin_dkb_visa():
    assert len(DKBVisaMartinImporter().do_import())

def test_import_liane_ingdiba():
    assert len(IngDiBaLianeImporter().do_import())
