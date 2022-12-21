from fimo import importer
from typing import List, Optional, Tuple
from enum import Enum
from datetime import date, timedelta
from dateutil import rrule
from pydantic import BaseModel

import matplotlib
import matplotlib.pyplot as plt

SKIP_LABEL = "SKIP"


class SortField(Enum):
    SPENDER = 0
    DATE = 1
    VALUE = 2
    RECEIVER = 3
    PURPOSE = 4
    COMMENT = 5


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
        elif field == SortField.COMMENT:
            result = x.comment
        else:
            raise ValueError("Unknown Sort Field")

        return result

    if field:
        data = sorted(data, key=keyf, reverse=reverse)

    return data


def org_print(
    data: List[importer.AccountRecord],
    truncate: Optional[int] = 60,
    invert: bool = False,
) -> List[List[str]]:
    out = []
    for d in data:
        out.append(
            [
                d.account.spender,
                d.date.strftime("%Y-%m-%d"),
                (1 - 2 * int(invert)) * d.value / 100,
                _truncate_string(d.receiver, truncate),
                _truncate_string(d.purpose, truncate),
                _truncate_string(d.comment, truncate),
            ]
        )

    return out


class RecordQuery(BaseModel):
    labels: Optional[List[str]]
    spender: Optional[str]
    startdate: date = date(2000, 1, 31)
    enddate: date = date(2050, 1, 31)
    invert: bool = False
    plotlabel: Optional[str]


class Monitor:
    def __init__(self, accounts: List[importer.Account]):
        self._importers = []
        for account in accounts:
            imp = importer.AccountImporter(account)
            self._importers.append(imp)
            imp.do_import()
            if imp.import_errors():
                print(f"Warning: {imp.import_errors()[0]}")

    def data(self):
        data = []
        for imp in self._importers:
            data.extend(imp.data())

        return data

    def org_list(
        self,
        query: RecordQuery,
        truncate: Optional[int] = 60,
        sort_field: Optional[SortField] = None,
        sort_reverse: bool = False,
    ) -> List[List[str]]:
        data = self.catlist(query.labels, query.spender, query.startdate, query.enddate)
        return org_print(
            sort_records(data, field=sort_field, reverse=sort_reverse),
            truncate=truncate,
            invert=invert,
        )

    def org_monthlycatsumplot(self, queries: List[RecordQuery], filename: str):
        fig, ax = plt.subplots()
        for query in queries:
            dates, sums = self.monthlycatsumplotdata(
                query.labels, query.spender, query.startdate, query.enddate, invert=query.invert
            )
            ax.bar(dates, sums, label=query.plotlabel if query.plotlabel else None)

        ax.legend()
        fig.tight_layout()
        plt.savefig(filename)
        return filename

    def org_catsumplot(self, queries: List[RecordQuery], filename: str):
        fig, ax = plt.subplots()
        for query in queries:
            dates, sums = self.catsumplotdata(
                query.labels, query.spender, query.startdate, query.enddate, invert=query.invert
            )
            ax.plot(dates, sums, label=query.plotlabel if query.plotlabel else None)

        ax.legend()
        fig.tight_layout()
        plt.savefig(filename)
        return filename

    def catlist(
        self,
        labels: Optional[List[str]] = None,
        spender: Optional[str] = None,
        startdate: date = date(2000, 1, 31),
        enddate: date = date(2050, 1, 31),
    ) -> List[importer.AccountRecord]:
        def check_spender(d: importer.AccountRecord):
            return spender is None or d.spender == spender

        catdata = [
            d
            for d in self.data()
            if (not labels or set(labels).intersection(d.labels))
            and not SKIP_LABEL in d.labels
            and check_spender(d)
            and d.date > startdate
            and d.date < enddate
        ]
        return catdata

    def sum(
        self,
        labels: Optional[List[str]] = None,
        spender: Optional = None,
        startdate: date = date(2000, 1, 31),
        enddate: date = date(2050, 1, 31),
        invert: bool = False,
    ) -> float:
        catdata = self.catlist(labels, spender, startdate, enddate)
        return (1 - 2 * int(invert)) * sum([d.value for d in catdata]) / 100

    def monthlycatsumplotdata(
        self,
        labels: Optional[List[str]] = None,
        spender: Optional = None,
        startdate: date = date(2000, 1, 31),
        enddate: date = date(2050, 1, 31),
        invert: bool = False,
    ) -> Tuple[List[date], List[float]]:
        allcatdata = sort_records(self.catlist(labels, spender), field=SortField.DATE)
        startdate = startdate if startdate > allcatdata[0].date else allcatdata[0].date
        enddate = enddate if enddate < allcatdata[-1].date else allcatdata[-1].date

        stepdays = list(rrule.rrule(rrule.MONTHLY, dtstart=startdate, until=enddate))

        if len(stepdays) < 1:
            raise Exception("Date range must be at least one month")

        catsums = []
        plotdays = []
        for i in range(len(stepdays) - 1):
            catdata = self.catlist(
                labels, spender, stepdays[i].date(), stepdays[i + 1].date()
            )
            catsums.append(
                (1 - 2 * int(invert)) * sum([d.value for d in catdata]) / 100
            )
            plotdays.append((stepdays[i + 1] - timedelta(days=1)).strftime("%Y-%m"))

        return plotdays, catsums

    def catsumplotdata(
        self,
        labels: Optional[List[str]] = None,
        spender: Optional = None,
        startdate: date = date(2000, 1, 31),
        enddate: date = date(2050, 1, 31),
        invert: bool = False,
    ) -> Tuple[List[date], List[float]]:
        catdata = self.catlist(labels, spender, startdate, enddate)

        catdata = sort_records(catdata, field=SortField.DATE)
        dates = []
        sums = []
        for d in catdata:
            dates.append(d.date)
            sum = 0
            if len(sums):
                sum = sums[-1]

            sums.append(sum + (1 - 2 * int(invert)) * d.value / 100)

        return (dates, sums)
