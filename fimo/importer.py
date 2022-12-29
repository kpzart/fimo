import csv
import re
import glob
import shutil
from typing import List, Dict, Optional
import datetime

from fimo.exception import FimoException
from pydantic import BaseModel
from pathlib import Path

LABEL_HEADING = "KPZ_Label"
COMMENT_HEADING = "KPZ_Comment"
RULE_SRC = "RULE_SRC"


def _remove_stuff_before_header(lines) -> int:
    # remove stuff before header line, it's separated by a blank line
    found = False
    for i, line in enumerate(lines[15::-1]):
        if line == "\n":
            found = True
            break

    k = 0
    if found:
        k = 15 - i + 1
        del lines[:k]

    return k + 1


class Account(BaseModel):
    name: str
    srcpath: Path
    csv_delimiter: str
    csv_encoding: Optional[str]
    spender: str
    heading_date: str
    heading_value: str
    heading_receiver: str
    heading_purpose: str
    labelled: bool = False


class RecordSource(BaseModel):
    filepath: Path
    linenumber: int


class AccountRecord(BaseModel):
    """Repräsentiert einen Eintrag aus einem Kontoauszug oder einen manuellen Finanzvorgang."""

    account: Account
    date: datetime.date
    spender: str
    value: int
    receiver: str
    purpose: str
    labels: List[str]
    comment: List[str]
    src: RecordSource
    labels_src: List[RecordSource]


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

    def _create_rule_file_fieldnames(self, fieldnames: List):
        fieldnames_copy = []
        fieldnames_copy.extend(fieldnames)

        sortedfieldnames = [LABEL_HEADING, COMMENT_HEADING]
        for l in [
            LABEL_HEADING,
            COMMENT_HEADING,
            self._account.heading_date,
            self._account.heading_value,
            self._account.heading_receiver,
            self._account.heading_purpose,
        ]:
            if l in fieldnames_copy:
                sortedfieldnames.append(l)
                fieldnames_copy.remove(l)

        sortedfieldnames.extend(fieldnames_copy)

        return sortedfieldnames

    def _import(self):
        self._file_importers = []

        if not self._account.labelled:
            rulesdir = self._account.srcpath.joinpath(RULES_SUBDIR)
            if not rulesdir.is_dir():
                rulesdir.mkdir()

            previewdir = self._account.srcpath.joinpath(PREVIEW_SUBDIR)
            if previewdir.exists():
                shutil.rmtree(previewdir)

            if not previewdir.is_dir():
                previewdir.mkdir()

            # read the regex rule file
            self._regexrulesfilepath = rulesdir.joinpath(REGEX_RULE_FILENAME)
            if self._regexrulesfilepath.exists():
                regex_rule_reader = CSVReader(self._regexrulesfilepath, delimiter=";")
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


def _apply_rules(
    adict: Dict, rules: List[Dict], regex_cmp: bool, overwrite: bool, rulespath: Path
):
    """
    Beware: Empty String in pattern matches everything, even without regex_cmp
    """

    def compare_strings(rule: str, text: str):
        if regex_cmp:
            return re.search(rule, text) is not None
        else:
            return rule == text

    for i, rule in enumerate(rules):
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

            if RULE_SRC in adict and adict[RULE_SRC] and not overwrite:
                adict[RULE_SRC].append(
                    RecordSource(filepath=rulespath, linenumber=i + 2)
                )
            else:
                adict[RULE_SRC] = [RecordSource(filepath=rulespath, linenumber=i + 2)]


class FileImporter:
    def __init__(self, filepath: Path, account_importer: AccountImporter):
        self._filepath = filepath
        self._account_importer = account_importer
        if not self._account_importer._account.labelled:
            self._rulefilepath = self._filepath.parent.joinpath(
                RULES_SUBDIR, self._filepath.name
            )
            self._previewfilepath = self._filepath.parent.joinpath(
                PREVIEW_SUBDIR, self._filepath.name
            )

    def do_import(self):
        rows = self._import()
        self._data = self._normalize(rows)

        if not self._account_importer._account.labelled:
            self._write_preview_file(rows)

        self._validate(rows)

    def data(self) -> List[AccountRecord]:
        return self._data

    def _normalize(self, rows: List[Dict]) -> List[AccountRecord]:
        result = [
            AccountRecord(
                account=self._account_importer._account,
                spender=self._account_importer._account.spender,
                date=datetime.datetime.strptime(
                    row[self._account_importer._account.heading_date], "%d.%m.%Y"
                ).date(),
                value=int(
                    row[self._account_importer._account.heading_value]
                    .replace(",", "")
                    .replace(".", "")
                ),
                receiver=row.get(self._account_importer._account.heading_receiver, ""),
                purpose=row.get(self._account_importer._account.heading_purpose, ""),
                comment=row[COMMENT_HEADING].split(","),
                labels=row[LABEL_HEADING].split(","),
                src=RecordSource(
                    filepath=self._filepath, linenumber=i + self._n_skipped_lines + 1
                ),
                labels_src=row[RULE_SRC] if RULE_SRC in row else [],
            )
            for i, row in enumerate(rows)
        ]

        for row in rows:
            if RULE_SRC in row:
                del row[RULE_SRC]

        return result

    def _import(self) -> List[Dict]:
        with open(
            self._filepath, "r", encoding=self._account_importer._account.csv_encoding
        ) as f:
            lines = f.readlines()

        self._n_skipped_lines = _remove_stuff_before_header(lines)
        if _has_duplicates(lines):
            raise FimoException(f"Found duplicates in file {self._filepath}")

        reader = csv.DictReader(
            lines,
            delimiter=self._account_importer._account.csv_delimiter,
            quotechar='"',
        )
        self._fieldnames = reader.fieldnames

        rows = [row for row in reader]

        if not self._account_importer._account.labelled:
            for r in rows:
                r[LABEL_HEADING] = ""
                r[COMMENT_HEADING] = ""
                _apply_rules(
                    r,
                    self._account_importer._regex_rules,
                    True,
                    True,
                    self._account_importer._regexrulesfilepath,
                )

            nonregex_rules = self._create_or_update_nonregex_rule_file(
                rows, reader.fieldnames
            )

            for r in rows:
                _apply_rules(r, nonregex_rules, False, True, self._rulefilepath)

        return rows

    def _validate(self, rows):
        self.import_errors = []
        if [r for r in rows if r[LABEL_HEADING] == ""]:
            self.import_errors.append(
                f"There are unlabeled entries in file {self._rulefilepath}"
            )

    def _create_or_update_nonregex_rule_file(self, rows, fieldnames):
        nonregex_rules = []
        if self._rulefilepath.exists():
            reader = CSVReader(self._rulefilepath, delimiter=";")
            nonregex_rules = [row for row in reader]

        sortedfieldnames = self._account_importer._create_rule_file_fieldnames(
            fieldnames
        )

        with open(self._rulefilepath, "w") as f:
            writer = csv.DictWriter(
                f, fieldnames=sortedfieldnames, delimiter=";", quoting=csv.QUOTE_ALL
            )
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
        sortedfieldnames = self._account_importer._create_rule_file_fieldnames(
            self._fieldnames
        )

        with open(self._previewfilepath, "w") as f:
            writer = csv.DictWriter(
                f, fieldnames=sortedfieldnames, delimiter=";", quoting=csv.QUOTE_ALL
            )
            writer.writeheader()

            for row in rows:
                if row[LABEL_HEADING]:
                    writer.writerow(row)


class CSVReader(csv.DictReader):
    def __init__(self, filepath: Path, delimiter: str, encoding=None):
        with open(filepath, "r", encoding=encoding) as f:
            lines = f.readlines()

        _remove_stuff_before_header(lines)

        super().__init__(lines, delimiter=delimiter, quotechar='"')
