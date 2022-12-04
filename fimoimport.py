from pathlib import Path
import glob

LABEL_HEADING = "KPZ_Label"
COLUMN_SEP = ";"
LABEL_RULES = {"VERBRAUCHERGEM": "DAILY"}


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


def _add_label_by_occurence(lines, label, word):
    output = []
    output.append(lines[0])

    for line in lines[1:]:
        if word in line:
            if line[-3] == ";":
                insertion = label
            else:
                insertion = "," + label

            line = line[:-2] + insertion + line[-2:]

        output.append(line)

    return output


class FimoImporter:
    def __init__(self, srcpath: Path):
        self._srcpath = Path(srcpath)

    def do_import(self):
        files = glob.glob(str(self._srcpath) + "/*.csv")
        for filepath in files:
            self._import_file(Path(filepath))

    def _import_file(self, filepath: Path):
        with open(filepath, encoding="iso-8859-1") as f:
            lines = f.readlines()

        _remove_stuff_before_header(lines)
        lines = _add_label_column(lines)
        for word, label in LABEL_RULES.items():
            lines = _add_label_by_occurence(lines, label, word)

        outfilepath = self._srcpath.joinpath("labeled", filepath.name)
        print(outfilepath)
        with open(outfilepath, "w") as f:
            f.writelines(lines)
