from pathlib import Path

LABEL_HEADING = "KPZ_Label"
COLUMN_SEP = ";"


def _remove_stuff_before_header(lines):
    # remove stuff before header line, it's separated by a blank line
    for i, line in enumerate(lines[15::-1]):
        if line == "\n":
            break

    del lines[: 15 - i + 1]


def _add_label_column(lines):
    output = []
    output.append(lines[0][:-1] + LABEL_HEADING + COLUMN_SEP + lines[0][-1])

    for line in lines[1:]:
        output.append(line[:-1] + COLUMN_SEP + line[-1])

    return output


class FimoImporter:
    def __init__(self, srcpath: Path):
        self._srcpath = srcpath

    def do_import(self):
        with open(self._srcpath, encoding="iso-8859-1") as f:
            lines = f.readlines()

            _remove_stuff_before_header(lines)
            lines = _add_label_column(lines)

            self._lines = lines
