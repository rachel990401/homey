"""
storage.py
----------
File input/output layer for Homey.

This file saves and loads the household state as JSON and can export a readable
text summary. It also contains a small recursive cleaner that walks nested saved
data before the app trusts it.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from managers import HomeManager


class StorageManager:
    """Save, load, and export Homey data using local files."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or Path(__file__).resolve().parent
        self.data_dir = self.base_dir / "data"
        self.export_dir = self.base_dir / "exports"
        self.state_path = self.data_dir / "homey_state.json"

    def load(self, manager: HomeManager) -> bool:
        """
        Load saved household data from data/homey_state.json.

        Args:
            manager (HomeManager): App manager to populate with loaded data.

        Returns:
            bool: True when a saved file was loaded, otherwise False.
        """
        try:
            with self.state_path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except FileNotFoundError:
            return False
        except (json.JSONDecodeError, OSError):
            manager.log("Saved file could not be loaded")
            return False

        data = self.clean_saved_value(data)
        allowed_sections = ["chores", "bills", "schedule", "expenses", "custom"]
        loaded_sections = []
        for section in data.get("enabled_sections", []):
            if section not in allowed_sections:
                continue
            loaded_sections.append(section)
            if len(loaded_sections) == len(allowed_sections):
                break

        manager.users = self.safe_list(data.get("users"))
        manager.setup_complete = bool(data.get("setup_complete")) and len(manager.users) >= 2
        manager.enabled_sections = loaded_sections
        manager.chores.chores = self.safe_list(data.get("chores"))
        manager.bills.bills = self.safe_list(data.get("bills"))
        manager.schedule.events = self.safe_list(data.get("events"))
        manager.expenses.expenses = self.safe_list(data.get("expenses"))
        manager.custom_lists.lists = self.safe_list(data.get("custom_lists"))
        manager.expense_split = self.safe_dict(data.get("expense_split"))
        manager.event_log = self.safe_list(data.get("event_log"))[:10]
        manager.log("Loaded saved household file")
        return True

    def save(self, manager: HomeManager) -> bool:
        """
        Save the current Homey state into a JSON file.

        Args:
            manager (HomeManager): App manager containing the latest data.

        Returns:
            bool: True when saving succeeds, otherwise False.
        """
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            with self.state_path.open("w", encoding="utf-8") as file:
                json.dump(manager.storage_dict(), file, indent=2)
        except OSError:
            manager.log("Could not save household file")
            return False
        return True

    def export_summary(self, manager: HomeManager) -> Path | None:
        """Create a readable text file summary for the household."""
        try:
            self.export_dir.mkdir(parents=True, exist_ok=True)
            export_path = self.export_dir / f"homey_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with export_path.open("w", encoding="utf-8") as file:
                file.write("Homey Household Summary\n")
                file.write("=======================\n\n")
                file.write(f"Members: {', '.join(manager.users) or 'Not set'}\n")
                file.write(f"Enabled sections: {', '.join(manager.enabled_sections) or 'Overview only'}\n\n")
                for member in manager.member_summaries("month"):
                    file.write(f"{member['user']}\n")
                    file.write(f"- Chores pending this month: {len(member['pending_chores'])}\n")
                    file.write(f"- Bills pending this month: {len(member['pending_bills'])}\n")
                    file.write(f"- Expenses paid this month: ${member['expenses_paid']:.2f}\n")
                    file.write(f"- Upcoming schedule this month: {member['schedule_summary']['upcoming_month']}\n\n")
        except OSError:
            manager.log("Could not export summary file")
            return None
        manager.log(f"Summary exported: {export_path.name}")
        return export_path

    def clean_saved_value(self, value):
        """
        Recursively clean nested saved JSON values.

        Saved data can contain dictionaries inside lists inside dictionaries.
        Recursion lets the function walk the whole structure using the same
        logic at every level.
        """
        if isinstance(value, dict):
            return {key: self.clean_saved_value(child) for key, child in value.items()}
        if isinstance(value, list):
            return [self.clean_saved_value(item) for item in value]
        return value

    def safe_list(self, value) -> List:
        return value if isinstance(value, list) else []

    def safe_dict(self, value) -> Dict:
        return value if isinstance(value, dict) else {}
