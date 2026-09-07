from dataclasses import dataclass
from datetime import date

import nepali_datetime


@dataclass(frozen=True, slots=True)
class BsMonthMetadata:
    year: int
    month: int
    month_name: str
    days: int
    first_ad_date: date
    last_ad_date: date


class BsDateService:
    """Convert AD/BS dates through one tested calendar implementation."""

    @staticmethod
    def ad_to_bs(value: date) -> str:
        try:
            converted = nepali_datetime.date.from_datetime_date(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("AD date is outside the supported Bikram Sambat range") from exc
        return converted.strftime("%Y-%m-%d")

    @staticmethod
    def bs_to_ad(value: str) -> date:
        try:
            year_text, month_text, day_text = value.split("-", 2)
            converted = nepali_datetime.date(
                int(year_text),
                int(month_text),
                int(day_text),
            )
            return converted.to_datetime_date()
        except (AttributeError, TypeError, ValueError, OverflowError) as exc:
            raise ValueError("invalid or unsupported Bikram Sambat date") from exc

    @classmethod
    def month_metadata(cls, year: int, month: int) -> BsMonthMetadata:
        if month < 1 or month > 12:
            raise ValueError("BS month must be between 1 and 12")
        try:
            first = nepali_datetime.date(year, month, 1)
            next_year = year + 1 if month == 12 else year
            next_month = 1 if month == 12 else month + 1
            following = nepali_datetime.date(next_year, next_month, 1)
            first_ad = first.to_datetime_date()
            following_ad = following.to_datetime_date()
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("BS month is outside the supported range") from exc
        days = (following_ad - first_ad).days
        return BsMonthMetadata(
            year=year,
            month=month,
            month_name=first.strftime("%B"),
            days=days,
            first_ad_date=first_ad,
            last_ad_date=following_ad.fromordinal(following_ad.toordinal() - 1),
        )
