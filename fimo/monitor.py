from fimo import importer
from typing import List, Optional, Tuple
from enum import Enum
from datetime import date

SKIP_LABEL = "SKIP"


class SortField(Enum):
    SPENDER = 0
    DATE = 1
    VALUE = 2
    RECEIVER = 3
    PURPOSE = 4


def _truncate_string(str_input: str, max_length: Optional[int]):
    str_end = "..."
    length = len(str_input)
    if max_length and length > max_length:
        return str_input[: max_length - len(str_end)] + str_end

    return str_input


def sort_records(
    data: List[importer.AccountRecord],
    field: Optional[SortField] = None,
    reverse: bool = False,
):
    def keyf(x: importer.AccountRecord):
        if field == SortField.SPENDER:
            result = x.spender
        elif field == SortField.DATE:
            result = x.date
        elif field == SortField.VALUE:
            result = x.value
        elif field == SortField.RECEIVER:
            result = x.receiver
        elif field == SortField.PURPOSE:
            result = x.purpose
        else:
            raise ValueError("Unknown Sort Field")

        return result

    if field:
        data = sorted(data, key=keyf, reverse=reverse)

    return data


def org_print(
    data: List[importer.AccountRecord],
    truncate: Optional[int] = 60,
):
    out = []
    for d in data:
        out.append(
            [
                d.account.spender.value,
                d.date.strftime("%Y-%m-%d"),
                d.value / 100,
                _truncate_string(d.receiver, truncate),
                _truncate_string(d.purpose, truncate),
            ]
        )

    return out


class Monitor:
    def __init__(self):
        self._importers = []
        for account in importer.ACCOUNTS[0:1]:
            imp = importer.AccountImporter(account)
            self._importers.append(imp)
            imp.do_import()

    def data(self):
        data = []
        for imp in self._importers:
            data.extend(imp.data())

        return data

    def catlist(
        self,
        label: Optional[str] = None,
        spender: Optional = None,
        startdate: date = date(2000, 1, 31),
        enddate: date = date(2050, 1, 31),
    ) -> List[importer.AccountRecord]:
        def check_spender(d: importer.AccountRecord):
            return spender is None or d.spender == spender

        catdata = [
            d
            for d in self.data()
            if (not label or label in d.labels)
            and not SKIP_LABEL in d.labels
            and check_spender(d)
            and d.date > startdate
            and d.date < enddate
        ]
        return catdata

    def catsumplotdata(
        self,
        label: Optional[str] = None,
        spender: Optional = None,
        startdate: date = date(2000, 1, 31),
        enddate: date = date(2050, 1, 31),
    ) -> Tuple[List[date], List[float]]:
        catdata = self.catlist(label, spender, startdate, enddate)

        catdata = sort_records(catdata, field=SortField.DATE)
        dates = []
        sums = []
        for d in catdata:
            dates.append(d.date)
            sum = 0
            if len(sums):
                sum = sums[-1]

            sums.append(sum + d.value / 100)

        return (dates, sums)
