from . import importer
from typing import List, Optional


def org_print(data: List[importer.AccountRecord]):
    out = []
    for d in data:
        out.append(
            [
                d.account.spender.value,
                d.date.strftime("%Y-%m-%d"),
                d.value / 100,
                d.receiver,
                d.purpose,
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
        self, label: str, spender: Optional = None
    ) -> List[importer.AccountRecord]:
        data = self.data()

        catdata = [d for d in data if label in d.labels]
        return catdata
