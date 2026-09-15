from pathlib import Path
import re

import pandas as pd

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from flaxes.models import Flax


class Command(BaseCommand):
    help = "Import Flax numbers and sizes from Flask_Sequence.xlsx"

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            default="Flask_Sequence.xlsx",
            help="Excel file name/path",
        )

        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete existing Flax records before importing",
        )

    def handle(self, *args, **options):

        file_path = Path(options["file"])

        # If a relative path is provided, look relative to BASE_DIR.
        if not file_path.is_absolute():
            file_path = Path(settings.BASE_DIR) / file_path

        if not file_path.exists():
            raise CommandError(
                f"Excel file not found: {file_path}"
            )

        self.stdout.write(
            self.style.NOTICE(
                f"Reading Excel file: {file_path}"
            )
        )

        try:
            df = pd.read_excel(file_path)
        except Exception as exc:
            raise CommandError(
                f"Could not read Excel file: {exc}"
            )

        # --------------------------------------------------
        # Normalize column names
        # --------------------------------------------------

        df.columns = [
            str(column).strip().lower()
            for column in df.columns
        ]

        size_column = self.find_column(
            df.columns,
            ["sizes", "size", "flax_size"],
        )

        flax_column = self.find_column(
            df.columns,
            ["flax no.", "flax no", "flax_no", "flax id", "flax_id"],
        )

        assignment_column = self.find_column(
            df.columns,
            [
                "assignment_status",
                "assignment_status",
                "status",
            ],
        )

        if not size_column:
            raise CommandError(
                "Could not find the size column. "
                "Expected something like 'Sizes'."
            )

        if not flax_column:
            raise CommandError(
                "Could not find the Flax number column. "
                "Expected something like 'Flax no.'."
            )
        if not assignment_column:
            raise CommandError(
                "Could not find the assignment_status column. "
                "Expected 'assignment_status' or 'Assignment Status'."
            )

        # --------------------------------------------------
        # Keep only the required columns
        # --------------------------------------------------

        df = df[
            [size_column, flax_column, assignment_column]
        ].copy()


        df = df.rename(
            columns={
                size_column: "flax_size",
                flax_column: "flax_no",
                assignment_column: "assignment_status",
            }
        )


        # Remove completely empty rows.
        df = df.dropna(
            subset=["flax_size", "flax_no"]
        )

        # --------------------------------------------------
        # Clean values
        # --------------------------------------------------

        df["flax_size"] = (
            df["flax_size"]
            .astype(str)
            .str.strip()
        )

        df["flax_no"] = (
            df["flax_no"]
            .astype(str)
            .str.strip()
            .str.upper()
        )


        df["assignment_status"] = (
            df["assignment_status"]
            .astype(str)
            .str.strip()
            .str.title()
        )

        # --------------------------------------------------
        # Validate Flax numbers
        # --------------------------------------------------

        valid_rows = []

        for _, row in df.iterrows():

            flax_no = row["flax_no"]
            flax_size = row["flax_size"]

            # Excel sometimes converts values unexpectedly.
            # Normalize FLX-1 -> FLX-001.
            match = re.fullmatch(
                r"FLX[- ]?(\d+)",
                flax_no,
            )

            if not match:
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipping invalid Flax number: {flax_no}"
                    )
                )
                continue

            number = int(match.group(1))

            # We only want FLX-001 through FLX-200.
            if number < 1 or number > 200:
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipping {flax_no}: outside FLX-001 to FLX-200"
                    )
                )
                continue

            normalized_flax_no = f"FLX-{number:03d}"

            valid_rows.append(
                {
                    "flax_no": normalized_flax_no,
                    "flax_size": flax_size,
                    "assignment_status": row["assignment_status"],
                }
            )


            valid_statuses = {
                "Assigned",
                "Available",
            }

            invalid_statuses = set(
                df["assignment_status"]
            ) - valid_statuses

            if invalid_statuses:
                raise CommandError(
                    "Invalid assignment_status values found: "
                    + ", ".join(sorted(invalid_statuses))
                    + ". Only 'Assigned' and 'Available' are allowed."
                )


        if not valid_rows:
            raise CommandError(
                "No valid Flax records were found in the Excel file."
            )

        # --------------------------------------------------
        # Convert to DataFrame again for validation
        # --------------------------------------------------

        imported_df = pd.DataFrame(valid_rows)

        # Remove duplicate Flax numbers.
        duplicates = (
            imported_df[
                imported_df.duplicated(
                    subset=["flax_no"],
                    keep=False,
                )
            ]
            ["flax_no"]
            .unique()
            .tolist()
        )

        if duplicates:
            raise CommandError(
                "Duplicate Flax numbers found: "
                + ", ".join(duplicates)
            )

        # --------------------------------------------------
        # Validate 10 Flax records per size
        # --------------------------------------------------

        size_counts = (
            imported_df
            .groupby("flax_size")
            .size()
            .sort_index()
        )

        self.stdout.write(
            self.style.NOTICE(
                "\nFlax count by size:"
            )
        )

        for size, count in size_counts.items():
            self.stdout.write(
                f"  {size}: {count}"
            )

        invalid_sizes = size_counts[
            size_counts != 10
        ]

        if not invalid_sizes.empty:
            details = ", ".join(
                f"{size}={count}"
                for size, count in invalid_sizes.items()
            )

            raise CommandError(
                "Each size must contain exactly 10 Flax "
                f"records. Invalid counts: {details}"
            )

        # --------------------------------------------------
        # Validate FLX-001 through FLX-200
        # --------------------------------------------------

        expected_numbers = {
            f"FLX-{number:03d}"
            for number in range(1, 201)
        }

        actual_numbers = set(
            imported_df["flax_no"]
        )

        missing_numbers = sorted(
            expected_numbers - actual_numbers
        )

        if missing_numbers:
            raise CommandError(
                "Missing Flax numbers: "
                + ", ".join(missing_numbers)
            )

        # --------------------------------------------------
        # Clear existing records if requested
        # --------------------------------------------------

        if options["clear"]:
            deleted_count, _ = Flax.objects.all().delete()

            self.stdout.write(
                self.style.WARNING(
                    f"Deleted {deleted_count} existing records."
                )
            )

        # --------------------------------------------------
        # Import records
        # --------------------------------------------------

        created_count = 0
        updated_count = 0

        for row in valid_rows:

            flax, created = Flax.objects.update_or_create(
                flax_no=row["flax_no"],
                defaults={
                    "flax_size": row["flax_size"],
                    "assignment_status": row["assignment_status"],
                },
            )


            if created:
                created_count += 1
            else:
                updated_count += 1


        # --------------------------------------------------
        # Final result
        # --------------------------------------------------

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "Excel import completed successfully."
            )
        )

        self.stdout.write(
            f"Created: {created_count}"
        )

        self.stdout.write(
            f"Updated: {updated_count}"
        )

        self.stdout.write(
            f"Total Flax records: {Flax.objects.count()}"
        )


        

    @staticmethod
    def find_column(columns, possible_names):

        for name in possible_names:
            if name.lower() in columns:
                return name.lower()

        return None
