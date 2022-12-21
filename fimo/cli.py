import click
import os

from fimo.exception import FimoException

from fimo import importer
from pydantic_yaml import YamlModel
from typing import List
from pathlib import Path


class FimoConfig(YamlModel):
    accounts: List[importer.Account]


@click.command()
@click.option("-c", "--config-file", "configfile", required=True, default=os.environ["HOME"] + "/.fimo.yml")
def fimo_import(configfile):
    try:
        text = Path(configfile).read_text()
        cfg = FimoConfig.parse_raw(text)

        importers = []
        for acc in cfg.accounts:
            print(f"Importing from {acc.name}")
            imp = importer.AccountImporter(acc)
            importers.append(imp)
            imp.do_import()

        for imp in importers:
            if imp.import_errors():
                print(f"Warning: {imp.import_errors()[0]}")

    except FimoException as e:
        print(f"Error: {e}")
        print(f"Exiting")
        exit(1)


if __name__ == "__main__":
    fimo_import()
