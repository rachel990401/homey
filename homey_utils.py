"""
homey_utils.py
--------------
Shared helper functions for Homey.

This file keeps date formatting, date validation, period filtering, and section
labels in one place so the terminal version and web version use the same rules.
"""

from datetime import datetime, timedelta


def today_text() -> str:
    """Return today's date in the YYYY-MM-DD format used by forms and saved data."""
    return datetime.now().strftime("%Y-%m-%d")


def date_in_period(date_text: str, period: str) -> bool:
    """
    Check whether a date belongs to the selected overview period.

    Args:
        date_text (str): Date in YYYY-MM-DD format.
        period (str): all, day, tomorrow, week, next_week, month, or next_month.

    Returns:
        bool: True when the item should appear in that overview period.
    """
    try:
        item_date = datetime.strptime(date_text, "%Y-%m-%d").date()
    except ValueError:
        return True

    today = datetime.now().date()
    if period == "all":
        return True
    if period == "day":
        return item_date == today
    if period == "tomorrow":
        return item_date == today + timedelta(days=1)
    if period == "week":
        return today <= item_date <= today + timedelta(days=7)
    if period == "next_week":
        return today + timedelta(days=8) <= item_date <= today + timedelta(days=14)
    if period == "month":
        return today <= item_date <= today + timedelta(days=31)
    if period == "next_month":
        first_this_month = today.replace(day=1)
        next_month = (first_this_month + timedelta(days=32)).replace(day=1)
        following_month = (next_month + timedelta(days=32)).replace(day=1)
        return next_month <= item_date < following_month
    return True


def valid_date(date_text: str) -> bool:
    """Return True when a value is a valid YYYY-MM-DD date."""
    try:
        datetime.strptime(date_text, "%Y-%m-%d")
    except (TypeError, ValueError):
        return False
    return True


def display_date(date_text: str) -> str:
    """Convert a saved YYYY-MM-DD date into a friendlier display label."""
    try:
        return datetime.strptime(date_text, "%Y-%m-%d").strftime("%b %d, %Y")
    except (TypeError, ValueError):
        return date_text or "No date"


def dates_overlap_period(start_text: str, end_text: str, period: str) -> bool:
    """Return True when any date in a multi-day event overlaps the selected period."""
    try:
        start_date = datetime.strptime(start_text, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_text, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return False

    current_date = start_date
    while current_date <= end_date:
        if date_in_period(current_date.strftime("%Y-%m-%d"), period):
            return True
        current_date += timedelta(days=1)
    return False


def section_choices() -> dict[str, str]:
    """Return the section keys and labels used in setup, terminal, and web views."""
    return {
        "chores": "Chores / household",
        "bills": "Bills / payments",
        "schedule": "Schedule",
        "expenses": "Paid expenses",
        "custom": "Custom add-on lists",
    }
