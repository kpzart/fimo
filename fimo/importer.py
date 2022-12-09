import csv
import re
import glob
from typing import List, Dict

from pydantic import BaseModel
from pathlib import Path

LABEL_HEADING = "KPZ_Label"

LABEL_ORDER = [
    LABEL_HEADING,
    "Buchungstag",
    "Auftraggeber / Begünstigter",
    "Verwendungszweck",
    "Betrag (EUR)",
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


class Account(BaseModel):
    srcpath: Path
    csv_delimiter: str = ";"


ACCOUNTS = [
    Account(srcpath="/home/kapuze/Shit/2007 DKB/csv/konto/"),
    Account(srcpath="/home/kapuze/Shit/2007 DKB/csv/visa/"),
    Account(srcpath="/home/kapuze/Nextcloud/matlantis_ocloud/LöwiMiez/Finanzen/Miez/"),
]

REGEX_RULE_FILENAME = "regexrules.csv"
RULES_SUBDIR = "rules"


class AccountImporter:
    def __init__(self, account: Account):
        self._account = account

    def do_import(self):
        rulesdir = self._account.srcpath.joinpath(RULES_SUBDIR)
        if not rulesdir.is_dir():
            rulesdir.mkdir()

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
            FileImporter(Path(filepath), self).do_import()


def _has_duplicates(alist: List):
    return len(set(alist)) != len(alist)


def _create_rule_file_fieldnames(fieldnames: List):
    fieldnames_copy = []
    fieldnames_copy.extend(fieldnames)

    sortedfieldnames = [LABEL_HEADING]
    for l in LABEL_ORDER:
        if l in fieldnames_copy:
            sortedfieldnames.append(l)
            fieldnames_copy.remove(l)

    sortedfieldnames.extend(fieldnames_copy)

    return sortedfieldnames


def apply_rules(adict: Dict, rules: List[Dict], regex_cmp: bool):
    """
    Beware: Empty String in pattern matches everything, even without regex_cmp
    """

    def compare_strings(rule: str, text: str):
        if regex_cmp:
            return re.fullmatch(rule, text) is not None
        else:
            return rule == text

    for rule in rules:
        comparisons = [
            compare_strings(rule[field], adict[field])
            for field in rule.keys()
            if field not in [LABEL_HEADING] and rule[field]
        ]
        if all(comparisons):
            if adict[LABEL_HEADING]:
                adict[LABEL_HEADING] += "," + rule[LABEL_HEADING]
            else:
                adict[LABEL_HEADING] = rule[LABEL_HEADING]


class FileImporter:
    def __init__(self, filepath: Path, account_importer: AccountImporter):
        self._filepath = filepath
        self._rulefilepath = self._filepath.parent.joinpath(
            RULES_SUBDIR, self._filepath.name
        )
        self._account_importer = account_importer

    def do_import(self):
        with open(self._filepath, "r", encoding="iso-8859-1") as f:
            lines = f.readlines()

        _remove_stuff_before_header(lines)
        if _has_duplicates(lines):
            raise Exception(f"Found duplicates in file {self._filepath}")

        reader = csv.DictReader(lines, delimiter=";", quotechar='"')
        rows = [row for row in reader]
        for r in rows:
            r[LABEL_HEADING] = ""
            apply_rules(r, self._account_importer._regex_rules, True)

        nonregex_rules = self._create_or_read_nonregex_rule_file(
            rows, reader.fieldnames
        )

        for r in rows:
            apply_rules(r, nonregex_rules, False)

        if [r for r in rows if r[LABEL_HEADING] == ""]:
            raise Exception(f"There are unlabeled entries in file {self._filepath}")

    def _create_or_read_nonregex_rule_file(self, rows, fieldnames):
        if self._rulefilepath.exists():
            reader = CSVReader(self._rulefilepath)
            nonregex_rules = [row for row in reader]
        else:
            sortedfieldnames = _create_rule_file_fieldnames(fieldnames)

            with open(self._rulefilepath, "w") as f:
                writer = csv.DictWriter(f, fieldnames=sortedfieldnames, delimiter=";")
                writer.writeheader()
                for row in rows:
                    if not row[LABEL_HEADING]:
                        writer.writerow(row)

            nonregex_rules = []

        return nonregex_rules


class CSVReader(csv.DictReader):
    def __init__(self, filepath: Path, encoding=None):
        with open(filepath, "r", encoding=encoding) as f:
            lines = f.readlines()

        _remove_stuff_before_header(lines)

        super().__init__(lines, delimiter=";", quotechar='"')


def main():
    for account in ACCOUNTS:
        AccountImporter(account).do_import()


if __name__ == "__main__":
    main()
