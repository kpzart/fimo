from pathlib import Path
import csv
import glob

from enum import Enum

LABEL_HEADING = "KPZ_Label"
COLUMN_SEP = ";"


class Label(Enum):
    DAILY = "DAILY"
    WOHNEN = "WOHNEN"


LABEL_RULES = {
    "VERBRAUCHERGEM": Label.DAILY,
    "Verbrauchergem": Label.DAILY,
    "REWE": Label.DAILY,
    "LIDL": Label.DAILY,
    "NETTO": Label.DAILY,
    "ROSSMANN": Label.DAILY,
    "DREWAG": Label.WOHNEN,
    "POPIMOB": Label.WOHNEN,
    "Telefonica": Label.WOHNEN,
    "Rundfunk": Label.WOHNEN,
}

LABEL_ORDER = [
    LABEL_HEADING,
    "Buchungstag",
    "Auftraggeber / Begünstigter",
    "Verwendungszweck",
    "Betrag (EUR)",
]


def _remove_stuff_before_header(lines):
    # remove stuff before header line, it's separated by a blank line
    for i, line in enumerate(lines[15::-1]):
        if line == "\n":
            break

    del lines[: 15 - i + 1]


class FimoImporter:
    def __init__(self, srcpath: Path):
        self._srcpath = Path(srcpath)

    def do_import(self):
        files = glob.glob(str(self._srcpath) + "/*.csv")
        for filepath in files:
            self._import_file(Path(filepath))

    def _import_file(self, filepath: Path):
        with open(filepath, "r", encoding="iso-8859-1") as f:
            lines = f.readlines()

        _remove_stuff_before_header(lines)

        reader = csv.DictReader(lines, delimiter=";", quotechar='"')

        fieldnames_copy = []
        fieldnames_copy.extend(reader.fieldnames)

        sortedfieldnames = [LABEL_HEADING]
        for l in LABEL_ORDER:
            if l in fieldnames_copy:
                sortedfieldnames.append(l)
                del l
        sortedfieldnames.extend(fieldnames_copy)

        outfilepath = self._srcpath.joinpath("labeled", filepath.name)
        with open(outfilepath, "w") as f:
            writer = csv.DictWriter(f, fieldnames=sortedfieldnames, delimiter=";")
            writer.writeheader()
            for row in reader:
                labels = [
                    label.value
                    for word, label in LABEL_RULES.items()
                    if word in ";".join(row.values())
                ]
                row[LABEL_HEADING] = ",".join(labels)
                writer.writerow(row)
