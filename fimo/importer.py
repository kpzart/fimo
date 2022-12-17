import csv
import re
import glob
import shutil
from typing import List, Dict
import datetime
from enum import Enum

from pydantic import BaseModel
from pathlib import Path

LABEL_HEADING = "KPZ_Label"
COMMENT_HEADING = "KPZ_Comment"

LABEL_ORDER = [
    LABEL_HEADING,
    COMMENT_HEADING,
    "Buchung", # Liane
    "Buchungstag", # Martin Konto
    "Betrag", # Liane
    "Betrag (EUR)", # Martin Konto
    "Auftraggeber/Empfänger", # Liane
    "Auftraggeber / Begünstigter", # Martin Konto
    "Verwendungszweck", # Martin Konto
]


def _remove_stuff_before_header(lines):
    # remove stuff before header line, it's separated by a blank line
    found = False
    for i, line in enumerate(lines[15::-1]):
        if line == "\n":
            found = True
            break

    if found:
        del lines[: 15 - i + 1]

class User(Enum):
    MARTIN = "MARTIN"
    LIANE = "LIANE"

class Account(BaseModel):
    name: str
    srcpath: Path
    csv_delimiter: str = ";"
    spender: User
    heading_date: str
    heading_value: str
    heading_receiver: str
    heading_purpose: str


ACCOUNTS = [
    Account(name = "Konto Martin",
            srcpath="/home/kapuze/Shit/2007 DKB/csv/konto/",
            spender = User.MARTIN,
            heading_date = "Buchungstag",
            heading_value = "Betrag (EUR)",
            heading_receiver = "Auftraggeber / Begünstigter",
            heading_purpose = "Verwendungszweck",
            ),
    Account(name = "Visa Martin",
            srcpath="/home/kapuze/Shit/2007 DKB/csv/visa/",
            spender = User.MARTIN,
            heading_date = "Belegdatum",
            heading_value = "Betrag (EUR)",
            heading_receiver = "",
            heading_purpose = "Beschreibung",
            ),
    Account(name = "Konto Liane",
            srcpath="/home/kapuze/Nextcloud/matlantis_ocloud/LöwiMiez/Finanzen/Miez/",
            spender = User.LIANE,
            heading_date = "Buchung",
            heading_value = "Betrag",
            heading_receiver = "Auftraggeber/Empfänger",
            heading_purpose = "Verwendungszweck",
            ),
]

class AccountRecord(BaseModel):
    """Repräsentiert einen Eintrag aus einem Kontoauszug oder einen manuellen Finanzvorgang."""
    account: Account
    date: datetime.date
    spender: User
    value: int
    receiver: str
    purpose: str
    labels: List[str]
    comment: List[str]

REGEX_RULE_FILENAME = "regexrules.csv"
RULES_SUBDIR = "rules"
PREVIEW_SUBDIR = "preview"


class AccountImporter:
    def __init__(self, account: Account):
        self._account = account

    def do_import(self):
        self._import()

    def data(self) -> List[AccountRecord]:
        data = []
        for fimp in self._file_importers:
            data.extend(fimp.data())

        return data

    def import_errors(self):
        import_errors = []
        for fimp in self._file_importers:
            import_errors.extend(fimp.import_errors)

        return import_errors

    def _import(self):
        self._file_importers = []
        rulesdir = self._account.srcpath.joinpath(RULES_SUBDIR)
        if not rulesdir.is_dir():
            rulesdir.mkdir()

        previewdir = self._account.srcpath.joinpath(PREVIEW_SUBDIR)
        if previewdir.exists():
            shutil.rmtree(previewdir)

        if not previewdir.is_dir():
            previewdir.mkdir()

        # read the regex rule file
        rulefilename = rulesdir.joinpath(REGEX_RULE_FILENAME)
        if rulefilename.exists():
            regex_rule_reader = CSVReader(rulefilename)
            self._regex_rules = [row for row in regex_rule_reader]
        else:
            self._regex_rules = []

        # import src files
        files = glob.glob(str(self._account.srcpath.joinpath("*.csv")))
        for filepath in files:
            fimp = FileImporter(Path(filepath), self)
            fimp.do_import()
            self._file_importers.append(fimp)


def _has_duplicates(alist: List):
    return len(set(alist)) != len(alist)


def _create_rule_file_fieldnames(fieldnames: List):
    fieldnames_copy = []
    fieldnames_copy.extend(fieldnames)

    sortedfieldnames = [LABEL_HEADING, COMMENT_HEADING]
    for l in LABEL_ORDER:
        if l in fieldnames_copy:
            sortedfieldnames.append(l)
            fieldnames_copy.remove(l)

    sortedfieldnames.extend(fieldnames_copy)

    return sortedfieldnames


def _apply_rules(adict: Dict, rules: List[Dict], regex_cmp: bool, overwrite: bool):
    """
    Beware: Empty String in pattern matches everything, even without regex_cmp
    """

    def compare_strings(rule: str, text: str):
        if regex_cmp:
            return re.search(rule, text) is not None
        else:
            return rule == text

    for rule in rules:
        comparisons = [
            compare_strings(rule[field], adict[field])
            for field in rule.keys()
            if field not in [LABEL_HEADING, COMMENT_HEADING] and rule[field]
        ]
        if all(comparisons):
            if adict[LABEL_HEADING] and not overwrite:
                adict[LABEL_HEADING] += "," + rule[LABEL_HEADING]
            else:
                adict[LABEL_HEADING] = rule[LABEL_HEADING]

            if adict[COMMENT_HEADING] and not overwrite:
                adict[COMMENT_HEADING] += "," + rule[COMMENT_HEADING]
            else:
                adict[COMMENT_HEADING] = rule[COMMENT_HEADING]

class FileImporter:
    def __init__(self, filepath: Path, account_importer: AccountImporter):
        self._filepath = filepath
        self._rulefilepath = self._filepath.parent.joinpath(
            RULES_SUBDIR, self._filepath.name
        )
        self._previewfilepath = self._filepath.parent.joinpath(
            PREVIEW_SUBDIR, self._filepath.name
        )
        self._account_importer = account_importer

    def do_import(self):
        rows = self._import()
        self._data = self._normalize(rows)

        self._write_preview_file(rows)

        self._validate(rows)

    def data(self) -> List[AccountRecord]:
        return self._data

    def _normalize(self, rows: List[Dict]) -> List[AccountRecord]:
        return [ AccountRecord(
            account = self._account_importer._account,
            spender = self._account_importer._account.spender,
            date = datetime.datetime.strptime(row[self._account_importer._account.heading_date], "%d.%m.%Y").date(),
            value = int(
                        row[self._account_importer._account.heading_value].replace(",", "").replace(".", "")
                    ),
            receiver = row[self._account_importer._account.heading_receiver],
            purpose = row[self._account_importer._account.heading_purpose],
            comment = row[COMMENT_HEADING].split(","),
            labels = row[LABEL_HEADING].split(","),
        ) for row in rows ]

    def _import(self) -> List[Dict]:
        with open(self._filepath, "r", encoding="iso-8859-1") as f:
            lines = f.readlines()

        _remove_stuff_before_header(lines)
        if _has_duplicates(lines):
            raise Exception(f"Found duplicates in file {self._filepath}")

        reader = csv.DictReader(lines, delimiter=";", quotechar='"')
        self._fieldnames = reader.fieldnames

        rows = [row for row in reader]
        for r in rows:
            r[LABEL_HEADING] = ""
            r[COMMENT_HEADING] = ""
            _apply_rules(r, self._account_importer._regex_rules, True, True)

        nonregex_rules = self._create_or_update_nonregex_rule_file(
            rows, reader.fieldnames
        )

        for r in rows:
            _apply_rules(r, nonregex_rules, False, True)

        return rows

    def _validate(self, rows):
        self.import_errors = []
        if [r for r in rows if r[LABEL_HEADING] == ""]:
            self.import_errors.append(f"There are unlabeled entries in file {self._filepath}")

    def _create_or_update_nonregex_rule_file(self, rows, fieldnames):
        nonregex_rules = []
        if self._rulefilepath.exists():
            reader = CSVReader(self._rulefilepath)
            nonregex_rules = [row for row in reader]

        sortedfieldnames = _create_rule_file_fieldnames(fieldnames)

        with open(self._rulefilepath, "w") as f:
            writer = csv.DictWriter(f, fieldnames=sortedfieldnames, delimiter=";")
            writer.writeheader()

            rows_remaining = rows.copy()
            for row in nonregex_rules:
                if row[LABEL_HEADING] or row[COMMENT_HEADING]:
                    writer.writerow(row)

                    orig_row = row.copy()
                    orig_row[LABEL_HEADING] = ""
                    orig_row[COMMENT_HEADING] = ""
                    if orig_row in rows_remaining:
                        rows_remaining.remove(orig_row)

            for row in rows_remaining:
                if not row[LABEL_HEADING] and not row[COMMENT_HEADING]:
                    writer.writerow(row)

        return nonregex_rules

    def _write_preview_file(self, rows: List[Dict]):
        sortedfieldnames = _create_rule_file_fieldnames(self._fieldnames)

        with open(self._previewfilepath, "w") as f:
            writer = csv.DictWriter(f, fieldnames=sortedfieldnames, delimiter=";")
            writer.writeheader()

            for row in rows:
                if row[LABEL_HEADING]:
                    writer.writerow(row)

class CSVReader(csv.DictReader):
    def __init__(self, filepath: Path, encoding=None):
        with open(filepath, "r", encoding=encoding) as f:
            lines = f.readlines()

        _remove_stuff_before_header(lines)

        super().__init__(lines, delimiter=";", quotechar='"')


def main():
    for account in ACCOUNTS:
        acc = AccountImporter(account)
        acc.do_import()
        acc.data()


if __name__ == "__main__":
    main()
