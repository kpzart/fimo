from fimo import importer
from typing import List, Optional, Tuple, Dict
from enum import Enum
from datetime import date, timedelta
from dateutil import rrule
from pydantic import BaseModel

import numpy
import matplotlib
import matplotlib.pyplot as plt

SKIP_LABEL = "SKIP"
FIGSIZE = [16, 9]

PREFIXES = {"Martin": "L", "Liane": "M"}


def other_spender(spender: str):
    return "Liane" if spender == "Martin" else "Martin"


def prefix_label(label: str, spender: str):
    return PREFIXES[spender] + "_" + label


def org_verbatim(text):
    return f"={text}="


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
    truncate: Optional[int] = 50,
    invert: bool = False,
    with_src_links: bool = True,
) -> List[List[str]]:
    out = [
        [
            "*Datum*",
            "*Betrag*",
            "*Konto*",
            "*Labels*",
            "*Kommentar*",
            "*Name*",
            "*Zweck*",
        ]
    ]

    out.append(None)

    if with_src_links:
        out[0] = [
            "*SRC*",
            "*RULE*",
            "*PRE*",
        ] + out[0]

    for d in data:
        entry = [
            d.date.strftime("%Y-%m-%d"),
            (1 - 2 * int(invert)) * d.value / 100,
            d.account.name,
            org_verbatim(d.labels[0]) if d.labels else "",
            _truncate_string(d.comment[0] if d.comment else "", truncate),
            _truncate_string(d.receiver, truncate),
            _truncate_string(d.purpose, truncate),
        ]

        if with_src_links:
            entry = [
                f"[[{d.src.filepath}::{d.src.linenumber}][src]]",
                f"[[{d.labels_src[0].filepath}::{d.labels_src[0].linenumber}][rule]]"
                if d.labels_src
                else "",
                f"[[{d.preview_src.filepath}::{d.preview_src.linenumber}][pre]]"
                if d.preview_src
                else "",
            ] + entry

        out.append(entry)

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

    def labels_in_use(self, query: RecordQuery) -> List[str]:
        labels = []
        for d in self.catlist(
            labels=query.labels,
            spender=query.spender,
            startdate=query.startdate,
            enddate=query.enddate,
        ):
            labels.extend(d.labels)

        return labels

    def org_labels(self, query: RecordQuery) -> List[List[str]]:
        labels = self.labels_in_use(query)

        labels_count = []
        for l in list(set(labels)):
            (labels_count.append((org_verbatim(l), labels.count(l))))

        return sorted(labels_count, key=lambda x: x[1])

    def org_list(
        self,
        query: RecordQuery,
        truncate: Optional[int] = 35,
        sort_field: Optional[SortField] = None,
        sort_reverse: bool = False,
        with_src_links: bool = True,
    ) -> List[List[str]]:
        data = self.catlist(
            labels=query.labels,
            spender=query.spender,
            startdate=query.startdate,
            enddate=query.enddate,
        )
        return org_print(
            sort_records(data, field=sort_field, reverse=sort_reverse),
            truncate=truncate,
            invert=query.invert,
            with_src_links=with_src_links,
        )

    def org_monthlycatsumplot(self, queries: List[RecordQuery], filename: str) -> str:
        fig, ax = plt.subplots()
        bottom_dict = {}

        for i, query in enumerate(queries):
            dates, sums = self.monthlycatsumplotdata(
                query.labels,
                query.spender,
                query.startdate,
                query.enddate,
                invert=query.invert,
            )

            bottom = []
            for d in dates:
                if d in bottom_dict:
                    bottom.append(bottom_dict[d])
                else:
                    bottom.append(0)

            ax.bar(
                dates,
                sums,
                bottom=bottom,
                label=query.plotlabel if query.plotlabel else f"{i}",
            )

            for d, s in zip(dates, sums):
                if d in bottom_dict:
                    bottom_dict[d] += s
                else:
                    bottom_dict[d] = s

            bottom += numpy.array(sums)

        ax.legend()
        fig.set_size_inches(FIGSIZE)
        fig.tight_layout()
        plt.savefig(filename)
        return filename

    def org_catsumsplot(self, queries: List[RecordQuery], filename: str):
        fig, ax = plt.subplots()
        sums = []
        sums_total = []
        labels = []
        for query in queries:
            c_sum = numpy.max(
                (
                    0,
                    self.sum(
                        labels=query.labels,
                        spender=query.spender,
                        startdate=query.startdate,
                        enddate=query.enddate,
                        invert=query.invert,
                    ),
                )
            )
            sums.append(c_sum)
            labels.append(", ".join(query.labels) if c_sum else "")

            l_labels = [prefix_label(l, "Martin") for l in query.labels]
            l_sum = numpy.max(
                (
                    0,
                    self.sum(
                        labels=l_labels,
                        spender=query.spender,
                        startdate=query.startdate,
                        enddate=query.enddate,
                        invert=query.invert,
                    ),
                )
            )
            sums.append(l_sum)
            labels.append(", ".join(l_labels) if l_sum else "")

            m_labels = [prefix_label(l, "Liane") for l in query.labels]
            m_sum = numpy.max(
                (
                    0,
                    self.sum(
                        labels=m_labels,
                        spender=query.spender,
                        startdate=query.startdate,
                        enddate=query.enddate,
                        invert=query.invert,
                    ),
                )
            )
            sums.append(m_sum)
            labels.append(", ".join(m_labels) if m_sum else "")

            sums_total.append(c_sum + l_sum + m_sum)

        inner_steps = numpy.arange(5) * 4
        outer_steps = [i for i in numpy.arange(20) if not i % 4 == 0]
        cmap1 = plt.colormaps["tab20b"]
        cmap2 = plt.colormaps["tab20c"]
        inner_colors = numpy.concatenate((cmap1(inner_steps), cmap2(inner_steps)))
        outer_colors = numpy.concatenate((cmap1(outer_steps), cmap2(outer_steps)))

        sumsum = numpy.sum(sums)

        ax.pie(
            sums,
            labels=labels,
            # autopct=lambda pct: f"{(pct / 100 * sumsum):,.2f} €",
            radius=0.8,
            wedgeprops=dict(width=0.3, edgecolor="w"),
            colors=outer_colors,
        )
        ax.pie(
            sums_total,
            autopct=lambda pct: f"{(pct / 100 * sumsum):,.2f} €",
            radius=0.5,
            wedgeprops=dict(width=0.3, edgecolor="w"),
            colors=inner_colors,
        )
        ax.axis("equal")
        # ax.set_title(f"Total {sumsum:,.2f} €")

        fig.set_size_inches(FIGSIZE)
        fig.tight_layout()
        plt.savefig(filename)
        return filename

    def org_catsumplot(self, queries: List[RecordQuery], filename: str):
        fig, ax = plt.subplots()
        for i, query in enumerate(queries):
            dates, sums = self.catsumplotdata(
                query.labels,
                query.spender,
                query.startdate,
                query.enddate,
                invert=query.invert,
            )
            ax.step(
                dates,
                sums,
                label=query.plotlabel if query.plotlabel else f"{i}",
                where="post",
            )

        ax.legend()
        fig.set_size_inches(FIGSIZE)
        fig.tight_layout()
        plt.savefig(filename)
        return filename

    def org_catplot(self, queries: List[RecordQuery], filename: str):
        fig, ax = plt.subplots()
        for i, query in enumerate(queries):
            dates, sums, labels = self.catplotdata(
                query.labels,
                query.spender,
                query.startdate,
                query.enddate,
                invert=query.invert,
            )
            if dates:
                ax.stem(
                    dates,
                    sums,
                    label=query.plotlabel if query.plotlabel else f"{i}",
                    markerfmt=["o", "P", "X", "v", "^"][i],
                )

        ax.legend()
        fig.set_size_inches(FIGSIZE)
        fig.tight_layout()
        plt.savefig(filename)
        return filename

    def catlist(
        self,
        labels: Optional[List[str]] = None,
        exclude_labels: Optional[List[str]] = None,
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
            and (not exclude_labels or not set(exclude_labels).intersection(d.labels))
            and check_spender(d)
            and d.date >= startdate
            and d.date < enddate
        ]
        return catdata

    def sum(
        self,
        labels: Optional[List[str]] = None,
        exclude_labels: Optional[List[str]] = None,
        spender: Optional = None,
        startdate: date = date(2000, 1, 31),
        enddate: date = date(2050, 1, 31),
        invert: bool = False,
    ) -> float:
        catdata = self.catlist(
            labels=labels,
            exclude_labels=exclude_labels,
            spender=spender,
            startdate=startdate,
            enddate=enddate,
        )
        return (1 - 2 * int(invert)) * sum([d.value for d in catdata]) / 100

    def privateSum(self, query: RecordQuery) -> float:
        """
        Persönliche Bilanz für query.spender. Es werden alle Kategorien in query.labels aus gemeinsamer und persönlicher Sicht betrachtet.
        """
        # Gemeinsame Ausgaben
        common_expenses = self.sum(
            labels=query.labels,
            startdate=query.startdate,
            enddate=query.enddate,
        )

        priv_labels = [prefix_label(l, query.spender) for l in query.labels]
        priv_expenses = self.sum(
            labels=priv_labels,
            startdate=query.startdate,
            enddate=query.enddate,
        )

        sum = common_expenses / 2 + priv_expenses
        return sum

    def compareLM(self, query: RecordQuery) -> float:
        """
        Vergleiche aus Sicht von query.spender. Ausgaben der Kategorien in query.labels werden aufgeteilt.

        Einkommen wird nicht explizit angerechnet. Transfer Leistungen dagegen schon.
        """
        # Ausgaben von spender
        expenses_spender = self.sum(
            labels=query.labels,
            spender=query.spender,
            startdate=query.startdate,
            enddate=query.enddate,
            invert=True,
        )

        # Ausgaben des anderen
        expenses_other = self.sum(
            labels=query.labels,
            spender=other_spender(query.spender),
            startdate=query.startdate,
            enddate=query.enddate,
            invert=True,
        )

        # Transfer Ausgaben
        transfer_spender = self.sum(
            labels=prefix_label("TRANSFER", query.spender),
            spender=query.spender,
            startdate=query.startdate,
            enddate=query.enddate,
            invert=True,
        )

        # Transfer Einnahmen
        transfer_other = self.sum(
            labels=prefix_label("TRANSFER", other_spender(query.spender)),
            spender=query.spender,
            startdate=query.startdate,
            enddate=query.enddate,
            invert=True,
        )

        sum = (
            expenses_spender
            - (expenses_spender + expenses_other) / 2
            + transfer_spender
            - transfer_other
        )
        return sum

    def monthlycatsumplotdata(
        self,
        labels: Optional[List[str]] = None,
        spender: Optional = None,
        startdate: date = date(2000, 1, 31),
        enddate: date = date(2050, 1, 31),
        invert: bool = False,
    ) -> Tuple[List[date], List[float]]:
        stepdays = list(rrule.rrule(rrule.MONTHLY, dtstart=startdate, until=enddate))

        if len(stepdays) < 1:
            raise Exception("Date range must be at least one month")

        catsums = []
        plotdays = []
        for i in range(len(stepdays) - 1):
            catdata = self.catlist(
                labels=labels,
                spender=spender,
                startdate=stepdays[i].date(),
                enddate=stepdays[i + 1].date(),
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
        catdata = self.catlist(
            labels=labels, spender=spender, startdate=startdate, enddate=enddate
        )

        dates = []
        sums = []
        for d in catdata:
            dates.append(d.date)
            sum = 0
            if len(sums):
                sum = sums[-1]

            sums.append(sum + (1 - 2 * int(invert)) * d.value / 100)

    def catplotdata(
        self,
        labels: Optional[List[str]] = None,
        spender: Optional = None,
        startdate: date = date(2000, 1, 31),
        enddate: date = date(2050, 1, 31),
        invert: bool = False,
    ) -> Tuple[List[date], List[float], List[str]]:
        catdata = self.catlist(
            labels=labels, spender=spender, startdate=startdate, enddate=enddate
        )

        dates = []
        values = []
        labels = []
        for d in catdata:
            dates.append(d.date)
            values.append((1 - 2 * int(invert)) * d.value / 100)
            labels.append(d.comment if d.comment else d.purpose)

        return (dates, values, labels)
