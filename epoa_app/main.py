from __future__ import annotations

import os
import shutil
import subprocess
import sys
from argparse import ArgumentParser, Namespace
from collections import defaultdict
from collections.abc import Callable, Iterator
from datetime import datetime
from functools import cached_property
from pathlib import Path
from zipfile import ZipFile

from colorama import Fore, Style  # type: ignore
from dateutil.parser import parse as parse_date
from pandas import Series  # type: ignore
from pandas import read_excel
from pypdf import PdfReader
from slugify import slugify

from .config import Config

config = Config()


class RoleCounter:
    def __init__(self) -> None:
        self.counts: dict[str, dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )

    def next(self, company: str, date: datetime | None = None) -> int:
        date_str = (date or datetime.now()).strftime("%Y%m%d")
        self.counts[date_str][company] += 1
        return self.counts[date_str][company]


class EPOAApp:
    @cached_property
    def args(self) -> Namespace:
        def _parse_date(x: str) -> datetime | None:
            if x.lower() in {"today", "tod"}:
                return datetime.today()
            elif x:
                return parse_date(x)
            return None

        def _parse_file_name(x: str) -> Path | None:
            if not x:
                return None
            if not (fp := Path(x).absolute()).is_file():
                raise Exception(f"{fp} is not a file")
            return fp

        ap = ArgumentParser(description="EPOA application tools")
        ap.add_argument(
            "action", choices=["apply", "zip"], help="Action to perform"
        )
        ap.add_argument(
            "-d",
            "--since-date",
            dest="since_date",
            metavar="date",
            type=_parse_date,
            help="Zip applications from this date or newer (default: all)",
        )
        ap.add_argument(
            "-r",
            "--resume",
            dest="resume",
            metavar="file",
            type=_parse_file_name,
            help='Resume file name (default: "resume" value in config file)',
        )
        return ap.parse_args()

    @cached_property
    def resume(self) -> Path:
        if isinstance(self.args.resume, Path):
            return self.args.resume
        return config.resume

    def __call__(self) -> None:
        self.print_config()
        if self.args.action == "apply":
            self.apply()
        elif self.args.action == "zip":
            self.zip()
        else:
            print(f"Unknown action {self.args.action}")

    def print_config(self) -> None:
        def _br(text: str | Path) -> str:
            return str(Style.BRIGHT + str(text) + Style.RESET_ALL)

        align = 16
        print(
            Fore.MAGENTA
            + _br(">>> ")
            + "Configuration ("
            + _br(config.conf_file)
            + "):"
        )
        print("")
        print("   ", f"{'Evidence dir:':>{align}}", _br(config.dir))
        print("   ", f"{'Resume:':>{align}}", _br(self.resume))
        print("   ", f"{'Spreadsheet:':>{align}}", _br(config.spreadsheet))
        print(
            "   ",
            f"{'Spreadsheet tab:':>{align}}",
            _br(config.spreadsheet_tab),
        )
        print(
            "   ",
            f"{'Zip file prefix:':>{align}}",
            _br(config.zip_prefix),
        )
        print(
            "   ",
            f"{'Check words:':>{align}}",
            _br(", ".join(sorted(config.compensation_words))),
        )
        print("")

    def apply(self) -> None:
        for role in self.role_gen():
            role.print_info()
            role.prep()
            input(Style.DIM + "Press [Enter] to continue " + Style.RESET_ALL)

    def zip(self) -> None:
        def _print_action(action: str, color: str = Fore.GREEN) -> None:
            print(
                Style.BRIGHT
                + color
                + ">>> "
                + Style.RESET_ALL
                + action
                + " "
                + Style.BRIGHT
                + self.trailing_path(zip_path)
                + Style.RESET_ALL
            )

        zip_path = config.dir / f"{config.zip_prefix}-{self.date_str}.zip"
        if zip_path.exists():
            _print_action("Error: Zip file already exists:", color=Fore.RED)
            sys.exit(1)
        _print_action("Creating", color=Fore.MAGENTA)
        role_count = 0
        with ZipFile(str(zip_path), mode="w") as z:
            z.write(
                config.spreadsheet,
                self.trailing_path(config.spreadsheet),
            )
            for role in self.role_gen(applied=True):
                if (
                    self.args.since_date
                    and role.date_applied < self.args.since_date
                ):
                    continue
                role_count += 1
                role.print_info(compact=True)
                for path in role.role_path.glob("**/*"):
                    z.write(str(path), self.trailing_path(path))
        _print_action(
            "Saved "
            + Style.BRIGHT
            + str(role_count)
            + Style.RESET_ALL
            + " cases to"
        )

    def trailing_path(self, path: Path) -> str:
        return str(path).removeprefix(str(config.dir) + os.sep)

    @cached_property
    def date_str(self) -> str:
        return datetime.now().strftime("%Y%m%d")

    def spreadsheet_row_gen(
        self, row_filter: Callable[[Series], bool] | None = None
    ) -> Iterator[Role]:
        role_counts = RoleCounter()
        df = read_excel(config.spreadsheet, config.spreadsheet_tab)
        for row_idx in range(0, len(df)):
            row = df.iloc[row_idx]
            if row_filter and not row_filter(row):
                continue
            if (
                not row["Company"]
                or not row["Role Posting URL"]
                or not row["Role Title"]
            ):
                continue
            yield Role.from_spreadsheet_row(
                self.resume,
                row,
                role_num=role_counts.next(
                    row["Company"],
                    (
                        row["Date Applied"].to_pydatetime()
                        if row.notna()["Date Applied"]
                        else None
                    ),
                ),
            )

    def role_gen(self, applied: bool = False) -> Iterator[Role]:
        yield from self.spreadsheet_row_gen(
            lambda r: r.notna()["Date Applied"] == applied
        )


class Role:
    def __init__(
        self,
        resume: Path,
        company: str,
        role_title: str,
        role_url: str,
        date_applied: datetime | None = None,
        role_num: int = 0,
    ) -> None:
        self.resume = resume
        self.company = company
        self.role_title = role_title
        self.role_url = role_url
        self.role_num = role_num
        self.date_applied = date_applied

    @staticmethod
    def from_spreadsheet_row(
        resume: Path, row: Series, role_num: int = 0
    ) -> Role:
        return Role(
            resume=resume,
            company=row["Company"],
            role_title=row["Role Title"],
            role_url=row["Role Posting URL"],
            date_applied=(
                row["Date Applied"].to_pydatetime()
                if row.notna()["Date Applied"]
                else None
            ),
            role_num=role_num,
        )

    def prep(self) -> None:
        self.role_path.mkdir(parents=True, exist_ok=True)
        role_resume_path = self.role_path / self.resume.name
        if not role_resume_path.exists():
            shutil.copy(self.resume, role_resume_path)
        if not self.posting_pdf_path.exists():
            print(
                Fore.GREEN
                + "Saving posting to PDF: "
                + str(self.posting_pdf_path).removeprefix(
                    str(config.dir) + os.sep
                )
                + Style.RESET_ALL
            )
            self.url_to_pdf(self.role_url, self.posting_pdf_path)
            print(Fore.GREEN + "Posting saved" + Style.RESET_ALL)
            print("")
        self.check_posting_pdf()

    def print_info(self, compact: bool = False) -> None:
        print(
            Fore.MAGENTA
            + Style.BRIGHT
            + ">>> "
            + Style.RESET_ALL
            + Style.BRIGHT
            + self.role_title
            + Style.RESET_ALL
            + " at "
            + Style.BRIGHT
            + self.company
            + Style.RESET_ALL
            + " -> "
            + Style.BRIGHT
            + Fore.BLUE
            + str(self.role_path).removeprefix(str(config.dir) + os.sep)
            + Style.RESET_ALL
            + ((" " + self.role_url) if compact else "")
            + (
                (Style.BRIGHT + Fore.YELLOW + " (applied)" + Style.RESET_ALL)
                if self.date_applied
                else ""
            )
        )
        if not compact:
            print("")
            print("    " + Style.BRIGHT + self.role_url + Style.RESET_ALL)
            print("")

    def text_search(self, page_num: int, text: str) -> None:
        matches = 0
        for word in config.compensation_words:
            for line in text.splitlines():
                if word.lower() in line.lower():
                    matches += 1
                    print(
                        Style.BRIGHT
                        + f"[Posting page {page_num}] "
                        + Style.RESET_ALL
                        + 'Found "'
                        + Fore.YELLOW
                        + Style.BRIGHT
                        + word
                        + Style.RESET_ALL
                        + " in [ "
                        + Style.DIM
                        + text
                        + Style.RESET_ALL
                        + " ]"
                    )
        if matches:
            print("")

    def check_posting_pdf(self) -> None:
        # Check if compensation-related words are in the PDF
        reader = PdfReader(self.posting_pdf_path)
        for i, page in enumerate(reader.pages):
            self.text_search(i + 1, page.extract_text())

    @cached_property
    def posting_pdf_path(self) -> Path:
        return self.role_path / f"posting-{self.date_str}.pdf"

    def url_to_pdf(self, url: str, file_name: Path) -> None:
        cmd_exe = (
            ["cmd.exe", "/c", "start", "/wait", "chrome"]
            if os.name == "nt"
            else ["google-chrome"]
        )
        cmd = cmd_exe + [
            "--headless",
            url,
            "--run-all-compositor-stages-before-draw",
            f"--print-to-pdf={str(file_name)}",
            "--virtual-time-budget=5000",
        ]
        subprocess.run(cmd, check=True)

    @cached_property
    def company_slug(self) -> str:
        return slugify(self.company)

    @cached_property
    def title_slug(self) -> str:
        return slugify(self.role_title)

    @cached_property
    def date_str(self) -> str:
        return (self.date_applied or datetime.now()).strftime("%Y%m%d")

    @cached_property
    def role_dir_name(self) -> str:
        return f"{self.date_str}-{self.role_num}-{self.title_slug}"

    @cached_property
    def role_path(self) -> Path:
        return config.dir / self.company_slug / self.role_dir_name
