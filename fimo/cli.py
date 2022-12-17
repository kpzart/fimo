import click

from fimo.exception import FimoException


@click.command()
def fimo_import():
    try:
        from fimo import importer

        importers = []
        for acc in importer.ACCOUNTS:
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
