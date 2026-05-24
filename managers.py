"""
managers.py
-----------
Main business logic for Homey.

This file contains the manager classes that hold and update the household
state. Both the Flask web routes and the terminal menus call these classes,
so the important rules are kept in Python rather than JavaScript.

MANAGERS INCLUDED:
    ChoreManager      - household tasks and owner switching
    BillManager       - pending bills, paid/unpaid status, and bill validation
    ScheduleManager   - event dates, attendance responses, and rescheduling
    ExpenseManager    - paid expenses, split proportions, and reconciliation
    CustomListManager - optional user-created lists
    HomeManager       - coordinates the full app state

PYTHON CONCEPTS SHOWN:
    - classes and objects for each app section
    - for loops for filtering, grouping, and summary building
    - try/except for amount and date parsing
    - break/continue in settlement and search logic
    - return values to report success, failure, or updated data
"""

import calendar
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List

from homey_utils import date_in_period, dates_overlap_period, display_date, today_text, valid_date


class ChoreManager:
    """
    Create and manage household chores such as laundry, dog care, plants, and repairs.

    Chores are stored as dictionaries so they can be saved directly into JSON.
    Each chore has a category, task title, frequency, due date, owner, and done
    status.
    """
    def __init__(self) -> None:
        self.chores: List[dict] = []

    def add_chore(self, data: dict, users: List[str]) -> dict | None:
        category = data.get("category", "").strip()
        title = data.get("title", data.get("name", "")).strip()
        frequency = data.get("frequency", "").strip()
        allowed_frequencies = {"Daily", "Every 2 days", "Weekly", "Monthly"}
        if not category or not title or frequency not in allowed_frequencies:
            return None
        due_date = data.get("due_date", "")
        if not valid_date(due_date):
            return None
        assignee = data.get("assigned_to", "")
        if assignee not in users:
            return None
        next_id = max([item["id"] for item in self.chores], default=0) + 1
        chore = {
            "id": next_id,
            "category": category,
            "title": title,
            "frequency": frequency,
            "due_date": due_date,
            "assigned_to": assignee,
            "done": False,
        }
        self.chores.append(chore)
        return chore

    def complete(self, chore_id: int) -> dict | None:
        for chore in self.chores:
            if chore["id"] != chore_id:
                continue
            chore["done"] = True
            return chore
        return None

    def switch_owner(self, chore_id: int, new_owner: str, users: List[str]) -> dict | None:
        if not users or new_owner not in users:
            return None
        for chore in self.chores:
            if chore["id"] != chore_id:
                continue
            chore["assigned_to"] = new_owner
            return chore
        return None

    def by_category(self) -> List[dict]:
        categories = []
        for chore in self.chores:
            category = chore["category"]
            existing = next((item for item in categories if item["name"] == category), None)
            if existing is None:
                existing = {"name": category, "chores": []}
                categories.append(existing)
            existing["chores"].append(chore)
        return categories

    def pending_for(self, user: str, period: str) -> List[dict]:
        return [
            chore
            for chore in self.chores
            if chore["assigned_to"] == user and not chore["done"] and date_in_period(chore["due_date"], period)
        ]

    def grouped_pending_alerts(self, user: str, period: str) -> List[dict]:
        groups = []
        for chore in self.pending_for(user, period):
            existing = next(
                (
                    group
                    for group in groups
                    if group["category"] == chore.get("category", "Household") and group["due_date"] == chore["due_date"]
                ),
                None,
            )
            if existing:
                existing["tasks"].append(chore["title"])
                continue
            groups.append({"category": chore.get("category", "Household"), "due_date": chore["due_date"], "tasks": [chore["title"]]})
        return [{"title": group["category"], "detail": f"{', '.join(group['tasks'])} - Due {display_date(group['due_date'])}"} for group in groups]

    def summary_for(self, user: str, period: str) -> dict:
        user_chores = [chore for chore in self.chores if chore["assigned_to"] == user]
        done_chores = [chore for chore in user_chores if chore["done"]]
        done_counts = {
            frequency: len([chore for chore in done_chores if chore["frequency"] == frequency])
            for frequency in ["Daily", "Weekly", "Monthly"]
        }
        return {
            "done_counts": done_counts,
            "pending_alerts": self.grouped_pending_alerts(user, period),
            "all_pending_alerts": self.grouped_pending_alerts(user, "all"),
        }


class BillManager:
    """
    Create and manage household bills.

    A bill begins as unpaid and assigned to one family member. When it is marked
    paid, HomeManager syncs it into ExpenseManager so the payer's paid expenses
    and the household reconciliation are updated.
    """
    def __init__(self) -> None:
        self.bills: List[dict] = []

    def parse_amount(self, value) -> float:
        """
        Convert user input into a positive money amount.

        Args:
            value: Raw amount from terminal input or web form.

        Returns:
            float: Rounded amount with two decimal places.

        Raises:
            ValueError: If the input is not numeric or is not above zero.
        """
        # try/except lets users type freely while Python gives a friendly validation error.
        try:
            amount = float(value)
        except (TypeError, ValueError) as error:
            raise ValueError("Bill amount must be a number.") from error
        if amount <= 0:
            raise ValueError("Bill amount must be more than 0.")
        return round(amount, 2)

    def add_bill(self, data: dict, users: List[str]) -> dict | None:
        category = data.get("category", "").strip()
        title = data.get("title", data.get("name", "")).strip()
        if not category or not title:
            return None
        amount = self.parse_amount(data.get("amount", ""))
        due_date = data.get("due_date", "")
        if not valid_date(due_date):
            return None
        pending_who = data.get("pending_who", "")
        if pending_who not in users:
            return None
        next_id = max([item["id"] for item in self.bills], default=0) + 1
        bill = {
            "id": next_id,
            "category": category,
            "title": title,
            "amount": amount,
            "due_date": due_date,
            "pending_who": pending_who,
            "paid": False,
        }
        self.bills.append(bill)
        return bill

    def pay(self, bill_id: int) -> dict | None:
        for bill in self.bills:
            if bill["id"] != bill_id:
                continue
            if bill["paid"]:
                return None
            bill["paid"] = True
            return bill
        return None

    def mark_unpaid(self, bill_id: int) -> dict | None:
        for bill in self.bills:
            if bill["id"] != bill_id:
                continue
            if not bill["paid"]:
                return None
            bill["paid"] = False
            return bill
        return None

    def switch_owner(self, bill_id: int, new_owner: str, users: List[str]) -> dict | None:
        if not users or new_owner not in users:
            return None
        for bill in self.bills:
            if bill["id"] != bill_id:
                continue
            if bill["paid"]:
                return None
            bill["pending_who"] = new_owner
            return bill
        return None

    def summary(self) -> dict:
        unpaid = [bill for bill in self.bills if not bill["paid"]]
        return {
            "unpaid_total": round(sum(bill["amount"] for bill in unpaid), 2),
            "unpaid_count": len(unpaid),
        }

    def pending_for(self, user: str, period: str) -> List[dict]:
        return [
            bill
            for bill in self.bills
            if bill["pending_who"] == user and not bill["paid"] and date_in_period(bill["due_date"], period)
        ]

    def summary_for(self, user: str, period: str) -> dict:
        user_bills = [bill for bill in self.bills if bill["pending_who"] == user]
        unpaid_bills = [bill for bill in user_bills if not bill["paid"]]
        pending_bills = self.pending_for(user, period)
        pending_alerts = [
            {
                "title": f"Payment: {bill.get('category', 'Bill')} - {bill['title']}",
                "detail": f"Due {display_date(bill['due_date'])} - ${bill['amount']:.2f}",
            }
            for bill in (unpaid_bills if period == "all" else pending_bills)
        ]
        return {
            "paid": len([bill for bill in user_bills if bill["paid"]]),
            "pending": len(pending_bills),
            "total": len(user_bills),
            "pending_alerts": pending_alerts,
        }


class ScheduleManager:
    """
    Manage family events and attendance responses.

    The schedule logic supports one-day and multi-day events. The creator does
    not need to accept their own event. Compulsory members must accept before
    the event is confirmed; if a compulsory member declines, the event needs a
    new date.
    """
    def __init__(self) -> None:
        self.events: List[dict] = []

    def parse_date_range(self, data: dict) -> tuple[str, str, int] | None:
        # Multi-day event rules stay in Python so terminal and web behave the same way.
        try:
            duration_days = int(data.get("duration_days", ""))
        except (TypeError, ValueError):
            return None
        if duration_days < 1:
            return None
        if duration_days == 1:
            start_text = data.get("date") or data.get("start_date", "")
            end_text = start_text
        else:
            start_text = data.get("start_date", "")
            end_text = data.get("end_date", "")
        if not valid_date(start_text) or not valid_date(end_text):
            return None
        start_date = datetime.strptime(start_text, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_text, "%Y-%m-%d").date()
        if end_date < start_date:
            return None
        actual_duration = (end_date - start_date).days + 1
        if duration_days > 1 and actual_duration != duration_days:
            return None
        return start_text, end_text, actual_duration

    def date_label(self, event: dict) -> str:
        start_text = event.get("start_date", event.get("date", ""))
        end_text = event.get("end_date", start_text)
        if start_text == end_text:
            return display_date(start_text)
        return f"{display_date(start_text)} - {display_date(end_text)}"

    def event_overlaps_period(self, event: dict, period: str) -> bool:
        start_text = event.get("start_date", event.get("date", ""))
        end_text = event.get("end_date", start_text)
        return dates_overlap_period(start_text, end_text, period)

    def event_on_day(self, event: dict, day: datetime.date) -> bool:
        try:
            start_date = datetime.strptime(event.get("start_date", event.get("date", "")), "%Y-%m-%d").date()
            end_date = datetime.strptime(event.get("end_date", event.get("date", "")), "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return False
        return start_date <= day <= end_date

    def attendance_for(self, event: dict, user: str) -> str:
        if user == event["owner"]:
            return "Creator"
        attendance = event.get("attendance", {}).get(user, "Compulsory")
        return attendance if attendance in ["Compulsory", "Optional"] else "Compulsory"

    def people_with_status(self, event: dict, attendance_type: str, response: str) -> List[str]:
        people = []
        for user, user_response in event["responses"].items():
            if self.attendance_for(event, user) == attendance_type and user_response == response:
                people.append(user)
        return people

    def compulsory_pending(self, event: dict) -> List[str]:
        return self.people_with_status(event, "Compulsory", "Pending")

    def optional_pending(self, event: dict) -> List[str]:
        return self.people_with_status(event, "Optional", "Pending")

    def compulsory_declined(self, event: dict) -> List[str]:
        return self.people_with_status(event, "Compulsory", "Declined")

    def optional_declined(self, event: dict) -> List[str]:
        return self.people_with_status(event, "Optional", "Declined")

    def confirmed(self, event: dict) -> bool:
        return not self.compulsory_pending(event) and not self.compulsory_declined(event)

    def confirmed_for_user(self, event: dict, user: str) -> bool:
        if not self.confirmed(event):
            return False
        if user == event["owner"]:
            return True
        return event["responses"].get(user) == "Accepted"

    def status_text(self, event: dict) -> str:
        declined = self.compulsory_declined(event)
        if declined:
            return f"Reschedule required: {', '.join(declined)} cannot make it."
        pending = self.compulsory_pending(event)
        if pending:
            return f"Waiting for: {', '.join(pending)}."
        optional = self.optional_pending(event)
        if optional:
            return f"Confirmed. Optional response pending from: {', '.join(optional)}."
        return "Confirmed and added to calendar."

    def enriched_event(self, event: dict) -> dict:
        copy = dict(event)
        copy["attendance"] = {user: self.attendance_for(event, user) for user in event["responses"]}
        copy["confirmed"] = self.confirmed(event)
        copy["compulsory_pending"] = self.compulsory_pending(event)
        copy["optional_pending"] = self.optional_pending(event)
        copy["compulsory_declined"] = self.compulsory_declined(event)
        copy["optional_declined"] = self.optional_declined(event)
        copy["status_text"] = self.status_text(event)
        copy["date_label"] = self.date_label(event)
        return copy

    def enriched_events(self) -> List[dict]:
        return [self.enriched_event(event) for event in self.events]

    def calendar_reference_date(self) -> datetime.date:
        dated_events = []
        for event in self.events:
            try:
                dated_events.append((datetime.strptime(event["date"], "%Y-%m-%d").date(), event))
            except (TypeError, ValueError):
                continue
        confirmed_dates = [event_date for event_date, event in dated_events if self.confirmed(event)]
        if confirmed_dates:
            return min(confirmed_dates)
        if dated_events:
            return min(event_date for event_date, _ in dated_events)
        return datetime.now().date()

    def month_calendar(self) -> dict:
        reference = self.calendar_reference_date()
        month = calendar.Calendar(firstweekday=0)
        confirmed_events = [self.enriched_event(event) for event in self.events if self.confirmed(event)]
        weeks = []
        for week in month.monthdatescalendar(reference.year, reference.month):
            week_days = []
            for day in week:
                day_text = day.strftime("%Y-%m-%d")
                day_events = [event for event in confirmed_events if self.event_on_day(event, day)]
                week_days.append(
                    {
                        "date": day_text,
                        "day": day.day,
                        "in_month": day.month == reference.month,
                        "today": day == datetime.now().date(),
                        "events": day_events,
                    }
                )
            weeks.append(week_days)
        return {
            "month_label": reference.strftime("%B %Y"),
            "weekdays": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            "weeks": weeks,
        }

    def summary_for(self, user: str, period: str = "all") -> dict:
        user_events = [event for event in self.events if user in event["responses"]]
        pending_compulsory = [
            {
                "title": f"Pending response: {event['title']}",
                "detail": f"Scheduled by {event['owner']}: {self.date_label(event)}",
            }
            for event in user_events
            if event["owner"] != user and self.attendance_for(event, user) == "Compulsory" and event["responses"][user] == "Pending"
        ]
        pending_optional = [
            {
                "title": f"Optional response: {event['title']}",
                "detail": f"Scheduled by {event['owner']}: {self.date_label(event)}",
            }
            for event in user_events
            if event["owner"] != user and self.attendance_for(event, user) == "Optional" and event["responses"][user] == "Pending"
        ]
        upcoming_items = [
            {
                "title": event["title"],
                "detail": f"Scheduled by {event['owner']}: {self.date_label(event)}",
            }
            for event in user_events
            if self.confirmed_for_user(event, user) and self.event_overlaps_period(event, period)
        ]
        return {
            "pending_compulsory": pending_compulsory,
            "pending_optional": pending_optional,
            "upcoming": len(upcoming_items),
            "upcoming_items": upcoming_items,
            "upcoming_week": len([event for event in user_events if self.confirmed_for_user(event, user) and self.event_overlaps_period(event, "week")]),
            "upcoming_month": len([event for event in user_events if self.confirmed_for_user(event, user) and self.event_overlaps_period(event, "month")]),
        }

    def add_event(self, data: dict, users: List[str]) -> dict | None:
        """
        Add a schedule item after validating dates, owner, and invite roles.

        Args:
            data (dict): Event form data from terminal or web.
            users (List[str]): Current family members.

        Returns:
            dict | None: The created event, or None when validation fails.
        """
        title = data.get("title", "").strip()
        if not title:
            return None
        date_range = self.parse_date_range(data)
        if not date_range:
            return None
        start_date, end_date, duration_days = date_range
        owner = data.get("owner", "")
        if owner not in users:
            return None
        requested_attendance = data.get("attendance", {})
        attendance = {}
        for user in users:
            if user == owner:
                attendance[user] = "Creator"
            else:
                attendance[user] = requested_attendance.get(user, "")
                if attendance[user] not in ["Compulsory", "Optional"]:
                    return None
        next_id = max([item["id"] for item in self.events], default=0) + 1
        event = {
            "id": next_id,
            "title": title,
            "date": start_date,
            "start_date": start_date,
            "end_date": end_date,
            "duration_days": duration_days,
            "owner": owner,
            "note": data.get("note", "").strip() or "No note added.",
            "attendance": attendance,
            "responses": {user: ("Accepted" if user == owner else "Pending") for user in users},
        }
        self.events.append(event)
        self.events.sort(key=lambda item: item["date"])
        return event

    def set_response(self, event_id: int, user: str, response: str) -> None:
        if response not in ["Accepted", "Declined", "Pending"]:
            return
        for event in self.events:
            if event["id"] == event_id and user in event["responses"]:
                if user == event["owner"]:
                    return
                event["responses"][user] = response
                return

    def reschedule(self, event_id: int, date_data, users: List[str]) -> dict | None:
        """
        Reschedule an event declined by a compulsory member.

        Args:
            event_id (int): Event to update.
            date_data: A date string or a dict with date/start_date/end_date.
            users (List[str]): Current family members.

        Returns:
            dict | None: Updated event, or None if the new dates are invalid.
        """
        for event in self.events:
            if event["id"] != event_id:
                continue
            if isinstance(date_data, dict):
                duration_days = int(event.get("duration_days", 1))
                if duration_days > 1:
                    date_range = self.parse_date_range(
                        {
                            "duration_days": duration_days,
                            "start_date": date_data.get("start_date", ""),
                            "end_date": date_data.get("end_date", ""),
                        }
                    )
                else:
                    date_range = self.parse_date_range(
                        {
                            "duration_days": 1,
                            "date": date_data.get("date", ""),
                        }
                    )
            else:
                date_range = self.parse_date_range({"duration_days": 1, "date": date_data})
            if not date_range:
                return None
            start_date, end_date, duration_days = date_range
            event["date"] = start_date
            event["start_date"] = start_date
            event["end_date"] = end_date
            event["duration_days"] = duration_days
            # After rescheduling, invited members must respond again for the new date.
            event["responses"] = {user: ("Accepted" if user == event["owner"] else "Pending") for user in users}
            self.events.sort(key=lambda item: item["date"])
            return event
        return None

    def for_user(self, user: str, period: str) -> List[dict]:
        return [
            self.enriched_event(event)
            for event in self.events
            if user in event["responses"] and self.event_overlaps_period(event, period)
        ]


class ExpenseManager:
    """
    Track paid household expenses and calculate who owes who.

    Bills that are marked paid are copied here as paid expenses. The summary
    method compares each person's paid amount against their agreed split.
    """
    def __init__(self) -> None:
        self.expenses: List[dict] = []

    def parse_amount(self, value) -> float:
        try:
            amount = float(value)
        except (TypeError, ValueError) as error:
            raise ValueError("Expense amount must be a number.") from error
        if amount <= 0:
            raise ValueError("Expense amount must be more than 0.")
        return round(amount, 2)

    def add_expense(self, data: dict, users: List[str]) -> dict | None:
        category = data.get("category", "").strip()
        title = data.get("title", "").strip()
        if not category or not title:
            return None
        amount = self.parse_amount(data.get("amount", ""))
        expense_date = data.get("date", "")
        if not valid_date(expense_date):
            return None
        paid_by = data.get("paid_by", "")
        if paid_by not in users:
            return None
        for_member = data.get("for_member") or "Household"
        if for_member != "Household" and for_member not in users:
            return None
        next_id = max([item["id"] for item in self.expenses], default=0) + 1
        expense = {
            "id": next_id,
            "title": title,
            "category": category,
            "amount": amount,
            "date": expense_date,
            "paid_by": paid_by,
            "for_member": for_member,
        }
        if data.get("source_bill_id") is not None:
            expense["source_bill_id"] = data["source_bill_id"]
        self.expenses.append(expense)
        return expense

    def add_bill_payment(self, bill: dict, users: List[str]) -> dict | None:
        if any(expense.get("source_bill_id") == bill["id"] for expense in self.expenses):
            return None
        return self.add_expense(
            {
                "title": f"Bill paid: {bill['title']}",
                "category": bill.get("category", "Bill"),
                "amount": bill["amount"],
                "date": today_text(),
                "paid_by": bill["pending_who"],
                "for_member": "Household",
                "source_bill_id": bill["id"],
            },
            users,
        )

    def remove_bill_payment(self, bill_id: int) -> bool:
        original_count = len(self.expenses)
        self.expenses = [expense for expense in self.expenses if expense.get("source_bill_id") != bill_id]
        return len(self.expenses) != original_count

    def total_for(self, user: str, period: str) -> float:
        return round(
            sum(expense["amount"] for expense in self.expenses if expense["paid_by"] == user and date_in_period(expense["date"], period)),
            2,
        )

    def summary(self, users: List[str], split_proportions: Dict[str, float] | None = None) -> dict:
        """
        Calculate total paid, member paid amounts, fair shares, and settlements.

        Args:
            users (List[str]): Current family members.
            split_proportions (Dict[str, float] | None): Percentage share per member.

        Returns:
            dict: Total, per-member balances, and settlement instructions.
        """
        total = round(sum(expense["amount"] for expense in self.expenses), 2)
        if not split_proportions:
            split_proportions = {user: round(100 / len(users), 2) for user in users} if users else {}
        balances = []
        for user in users:
            paid = round(sum(expense["amount"] for expense in self.expenses if expense["paid_by"] == user), 2)
            proportion = float(split_proportions.get(user, 0))
            share = round(total * proportion / 100, 2)
            balances.append({"user": user, "paid": paid, "split_percent": proportion, "fair_share": share, "balance": round(paid - share, 2)})
        settlements = self.calculate_settlements(balances)
        for balance in balances:
            user = balance["user"]
            owes_to = [settlement for settlement in settlements if settlement["from"] == user]
            owed_from = [settlement for settlement in settlements if settlement["to"] == user]
            balance["owes_to"] = owes_to
            balance["owed_from"] = owed_from
            balance["owes_total"] = round(sum(settlement["amount"] for settlement in owes_to), 2)
            balance["owed_total"] = round(sum(settlement["amount"] for settlement in owed_from), 2)
        return {"total": total, "balances": balances, "settlements": settlements}

    def calculate_settlements(self, balances: List[dict]) -> List[dict]:
        """
        Match debtors to creditors until the shared expenses are balanced.

        Args:
            balances (List[dict]): Per-member paid amount minus fair share.

        Returns:
            List[dict]: Items such as {"from": "Mum", "to": "Dad", "amount": 60}.
        """
        # Nested loops match debtors with creditors until every shared expense is settled.
        debtors = [{"user": item["user"], "amount": round(-item["balance"], 2)} for item in balances if item["balance"] < 0]
        creditors = [{"user": item["user"], "amount": round(item["balance"], 2)} for item in balances if item["balance"] > 0]
        settlements = []
        for debtor in debtors:
            amount_left = debtor["amount"]
            for creditor in creditors:
                if amount_left <= 0:
                    break
                if creditor["amount"] <= 0:
                    continue
                payment = round(min(amount_left, creditor["amount"]), 2)
                settlements.append({"from": debtor["user"], "to": creditor["user"], "amount": payment})
                amount_left = round(amount_left - payment, 2)
                creditor["amount"] = round(creditor["amount"] - payment, 2)
        return settlements


class CustomListManager:
    def __init__(self) -> None:
        self.lists: List[dict] = []

    def add_list(self, data: dict, users: List[str]) -> dict | None:
        title = data.get("title", "").strip()
        if not title:
            return None
        owner = data.get("owner", "")
        if owner not in users:
            return None
        next_id = max([item["id"] for item in self.lists], default=0) + 1
        custom_list = {
            "id": next_id,
            "title": title,
            "owner": owner,
            "label": data.get("label", "Custom"),
            "detail": data.get("detail", "").strip() or "No details yet.",
        }
        self.lists.append(custom_list)
        return custom_list


@dataclass
class HomeManager:
    """
    Coordinate the whole Homey app.

    HomeManager owns the section managers and acts as the shared controller for
    both interfaces. Flask routes and terminal menus call this class so the
    business rules stay in Python.
    """
    users: List[str] = field(default_factory=list)
    setup_complete: bool = False
    enabled_sections: List[str] = field(default_factory=list)
    chores: ChoreManager = field(default_factory=ChoreManager)
    bills: BillManager = field(default_factory=BillManager)
    schedule: ScheduleManager = field(default_factory=ScheduleManager)
    expenses: ExpenseManager = field(default_factory=ExpenseManager)
    custom_lists: CustomListManager = field(default_factory=CustomListManager)
    expense_split: Dict[str, float] = field(default_factory=dict)
    event_log: List[str] = field(default_factory=list)
    form_errors: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        pass

    def reset_workspace(self) -> None:
        self.users = []
        self.setup_complete = False
        self.enabled_sections = []
        self.chores = ChoreManager()
        self.bills = BillManager()
        self.schedule = ScheduleManager()
        self.expenses = ExpenseManager()
        self.custom_lists = CustomListManager()
        self.expense_split = {}
        self.event_log = []
        self.form_errors = {}

    def log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.event_log.insert(0, f"{timestamp} - {message}")
        self.event_log = self.event_log[:10]

    def set_form_error(self, form_name: str, message: str) -> None:
        self.form_errors[form_name] = message

    def clear_form_error(self, form_name: str) -> None:
        if form_name in self.form_errors:
            del self.form_errors[form_name]

    def setup_home(self, names: List[str], sections: List[str]) -> None:
        """
        Validate and save the initial household setup.

        Args:
            names (List[str]): Family member names entered by the user.
            sections (List[str]): Section keys chosen during setup.
        """
        cleaned_names = []
        seen_names = set()
        for name in names:
            cleaned_name = name.strip()
            normalized_name = cleaned_name.lower()
            if not cleaned_name or normalized_name in seen_names:
                self.log("Setup blocked because member names were invalid")
                return
            seen_names.add(normalized_name)
            cleaned_names.append(cleaned_name)
        if len(cleaned_names) < 2:
            self.log("Setup blocked because no family members were provided")
            return
        allowed_sections = ["chores", "bills", "schedule", "expenses", "custom"]
        chosen_sections = [section for section in sections if section in allowed_sections]
        self.users = cleaned_names
        if "expenses" not in chosen_sections:
            self.expense_split = self.default_split(cleaned_names, self.expense_split)
        self.enabled_sections = chosen_sections
        self.setup_complete = True
        self.log(f"Setup complete for {', '.join(self.users)}")

    def setup_home_with_split(self, names: List[str], sections: List[str], split: Dict[str, float] | None = None) -> None:
        """
        Run setup and validate split proportions when Paid Expenses is selected.

        Args:
            names (List[str]): Family member names.
            sections (List[str]): Selected app sections.
            split (Dict[str, float] | None): Optional percentage share per member.
        """
        allowed_sections = ["chores", "bills", "schedule", "expenses", "custom"]
        chosen_sections = [section for section in sections if section in allowed_sections]
        if "expenses" not in chosen_sections:
            self.setup_home(names, sections)
            return
        current_users = self.users
        current_sections = self.enabled_sections
        current_split = self.expense_split
        self.setup_home(names, sections)
        if not self.setup_complete or not self.update_expense_split(split or {}):
            self.users = current_users
            self.enabled_sections = current_sections
            self.expense_split = current_split
            self.setup_complete = bool(current_users)
            self.log("Setup blocked because expense split was invalid")

    def add_member(self, name: str) -> bool:
        cleaned_name = name.strip()
        if not cleaned_name:
            self.set_form_error("setup", "Enter the new member name.")
            return False
        if any(user.lower() == cleaned_name.lower() for user in self.users):
            self.set_form_error("setup", "Family member names must be unique.")
            return False
        self.users.append(cleaned_name)
        self.expense_split = self.default_split(self.users, self.expense_split)
        self.clear_form_error("setup")
        self.log(f"Member added: {cleaned_name}")
        return True

    def delete_member(self, name: str, confirmed: bool = False) -> bool:
        if name not in self.users:
            self.set_form_error("setup", "Choose an existing member to delete.")
            return False
        if len(self.users) <= 2:
            self.set_form_error("setup", "Homey needs at least 2 members.")
            return False
        if not confirmed:
            self.set_form_error("setup", f"Deleting {name} will reassign their pending items. Confirm to continue.")
            return False
        remaining_users = [user for user in self.users if user != name]
        fallback_user = remaining_users[0]
        self.users = remaining_users
        self.expense_split.pop(name, None)
        self.expense_split = self.default_split(self.users, self.expense_split)
        for chore in self.chores.chores:
            if chore["assigned_to"] == name:
                chore["assigned_to"] = fallback_user
        for bill in self.bills.bills:
            if bill["pending_who"] == name:
                bill["pending_who"] = fallback_user
        for event in self.schedule.events:
            if event["owner"] == name:
                event["owner"] = fallback_user
            event["responses"].pop(name, None)
            event.get("attendance", {}).pop(name, None)
            if fallback_user in event["responses"]:
                event["responses"][fallback_user] = "Accepted" if event["owner"] == fallback_user else event["responses"][fallback_user]
                event["attendance"][fallback_user] = "Creator" if event["owner"] == fallback_user else event["attendance"].get(fallback_user, "Compulsory")
        self.clear_form_error("setup")
        self.log(f"Member deleted: {name}")
        return True

    def amend_section(self, section: str, action: str) -> bool:
        allowed_sections = ["chores", "bills", "schedule", "expenses", "custom"]
        if section not in allowed_sections:
            self.set_form_error("setup", "Choose a valid section.")
            return False
        if action == "add":
            if section not in self.enabled_sections:
                self.enabled_sections.append(section)
            if section == "expenses":
                self.expense_split = self.default_split(self.users, self.expense_split)
            self.clear_form_error("setup")
            self.log(f"Section added: {section}")
            return True
        if action == "remove":
            if section in self.enabled_sections:
                self.enabled_sections.remove(section)
            self.clear_form_error("setup")
            self.log(f"Section removed: {section}")
            return True
        self.set_form_error("setup", "Choose whether to add or remove the section.")
        return False

    def has_section(self, section: str) -> bool:
        return self.setup_complete and section in self.enabled_sections

    def default_split(self, users: List[str], existing_split: Dict[str, float] | None = None) -> Dict[str, float]:
        existing_split = existing_split or {}
        if not users:
            return {}
        if all(user in existing_split for user in users):
            selected = {user: float(existing_split[user]) for user in users}
            if round(sum(selected.values()), 2) == 100:
                return selected
        equal_share = round(100 / len(users), 2)
        split = {user: equal_share for user in users}
        split[users[-1]] = round(100 - sum(split[user] for user in users[:-1]), 2)
        return split

    def update_expense_split(self, split: Dict[str, float]) -> bool:
        """
        Save member split proportions after confirming they add up to 100%.

        Args:
            split (Dict[str, float]): Member name mapped to percentage share.

        Returns:
            bool: True if the split was valid and saved, otherwise False.
        """
        if set(split.keys()) != set(self.users):
            return False
        try:
            cleaned_split = {user: round(float(split[user]), 2) for user in self.users}
        except (TypeError, ValueError):
            return False
        if any(value < 0 or value > 100 for value in cleaned_split.values()):
            return False
        if round(sum(cleaned_split.values()), 2) != 100:
            return False
        self.expense_split = cleaned_split
        self.log("Expense split updated")
        return True

    def complete_chore(self, chore_id: int) -> dict | None:
        chore = self.chores.complete(chore_id)
        if chore:
            self.log(f"Completed: {chore['title']}")
        return chore

    def switch_chore_owner(self, chore_id: int, new_owner: str) -> dict | None:
        chore = self.chores.switch_owner(chore_id, new_owner, self.users)
        if chore:
            self.log(f"Chore reassigned: {chore['title']} to {chore['assigned_to']}")
        return chore

    def mark_bill_paid(self, bill_id: int) -> dict | None:
        bill = self.bills.pay(bill_id)
        if bill:
            expense = self.expenses.add_bill_payment(bill, self.users)
            self.log(f"Paid: {bill['title']}")
            if expense:
                self.log(f"Expense synced from bill: {expense['title']}")
        return bill

    def mark_bill_unpaid(self, bill_id: int) -> dict | None:
        bill = self.bills.mark_unpaid(bill_id)
        if bill:
            removed = self.expenses.remove_bill_payment(bill_id)
            self.log(f"Marked unpaid: {bill['title']}")
            if removed:
                self.log(f"Removed synced expense for bill: {bill['title']}")
        return bill

    def switch_bill_owner(self, bill_id: int, new_owner: str) -> dict | None:
        bill = self.bills.switch_owner(bill_id, new_owner, self.users)
        if bill:
            self.log(f"Bill reassigned: {bill['title']} to {bill['pending_who']}")
        return bill

    def respond_to_schedule(self, event_id: int, user: str, response: str) -> None:
        self.schedule.set_response(event_id, user, response)
        self.log("Schedule response updated")

    def reschedule_event(self, event_id: int, date_data) -> dict | None:
        event = self.schedule.reschedule(event_id, date_data, self.users)
        if event:
            self.log(f"Schedule date changed: {event['title']}")
        return event

    def member_summaries(self, period: str) -> List[dict]:
        summaries = []
        for user in self.users:
            pending_chores = self.chores.pending_for(user, period)
            pending_bills = self.bills.pending_for(user, period)
            events = self.schedule.for_user(user, period)
            expenses_paid = self.expenses.total_for(user, period)
            summaries.append(
                {
                    "user": user,
                    "pending_chores": pending_chores,
                    "pending_bills": pending_bills,
                    "chore_summary": self.chores.summary_for(user, period),
                    "bill_member_summary": self.bills.summary_for(user, period),
                    "events": events,
                    "schedule_summary": self.schedule.summary_for(user, period),
                    "expenses_paid": expenses_paid,
                }
            )
        return summaries

    def household_snapshot(self, period: str) -> dict:
        chores = [chore for chore in self.chores.chores if not chore["done"] and date_in_period(chore["due_date"], period)]
        bills = [bill for bill in self.bills.bills if not bill["paid"] and date_in_period(bill["due_date"], period)]
        schedule_items = [event for event in self.schedule.enriched_events() if self.schedule.event_overlaps_period(event, period)]
        confirmed_events = [event for event in schedule_items if event["confirmed"]]
        pending_response_events = [
            event
            for event in schedule_items
            if event["compulsory_pending"] or event["optional_pending"]
        ]
        expenses = [expense for expense in self.expenses.expenses if date_in_period(expense["date"], period)]
        return {
            "chores": {"pending": len(chores), "due": self.closest_due(chores, "due_date")},
            "bills": {"pending": len(bills), "due": self.closest_due(bills, "due_date")},
            "schedule": {
                "pending": len(pending_response_events),
                "scheduled": len(confirmed_events),
                "due": self.closest_due(pending_response_events or confirmed_events, "date"),
            },
            "expenses": {"paid": f"${sum(expense['amount'] for expense in expenses):.2f}", "count": len(expenses)},
            "custom": {"pending": len(self.custom_lists.lists), "due": "Custom lists"},
        }

    def closest_due(self, items: List[dict], date_key: str) -> str:
        dated_items = []
        for item in items:
            try:
                dated_items.append((datetime.strptime(item[date_key], "%Y-%m-%d").date(), item))
            except (KeyError, TypeError, ValueError):
                continue
        if not dated_items:
            return "None"
        dated_items.sort(key=lambda item: item[0])
        return display_date(dated_items[0][0].strftime("%Y-%m-%d"))

    def as_dict(self) -> dict:
        return {
            "users": self.users,
            "setup_complete": self.setup_complete,
            "enabled_sections": self.enabled_sections,
            "chores_by_category": self.chores.by_category(),
            "chores_by_user": [{"name": user, "pending": len(self.chores.pending_for(user, "month"))} for user in self.users],
            "bills": self.bills.bills,
            "bill_summary": self.bills.summary(),
            "scheduled_items": self.schedule.enriched_events(),
            "schedule_calendar": self.schedule.month_calendar(),
            "expenses": self.expenses.expenses,
            "expense_split": self.expense_split,
            "expense_summary": self.expenses.summary(self.users, self.expense_split),
            "custom_lists": self.custom_lists.lists,
            "member_summaries": {
                "all": self.member_summaries("all"),
                "day": self.member_summaries("day"),
                "tomorrow": self.member_summaries("tomorrow"),
                "week": self.member_summaries("week"),
                "next_week": self.member_summaries("next_week"),
                "month": self.member_summaries("month"),
                "next_month": self.member_summaries("next_month"),
            },
            "household_snapshots": {
                "all": self.household_snapshot("all"),
                "day": self.household_snapshot("day"),
                "tomorrow": self.household_snapshot("tomorrow"),
                "week": self.household_snapshot("week"),
                "next_week": self.household_snapshot("next_week"),
                "month": self.household_snapshot("month"),
                "next_month": self.household_snapshot("next_month"),
            },
            "event_log": self.event_log,
            "form_errors": self.form_errors,
        }

    def storage_dict(self) -> dict:
        return {
            "users": self.users,
            "setup_complete": self.setup_complete,
            "enabled_sections": self.enabled_sections,
            "chores": self.chores.chores,
            "bills": self.bills.bills,
            "events": self.schedule.events,
            "expenses": self.expenses.expenses,
            "custom_lists": self.custom_lists.lists,
            "expense_split": self.expense_split,
            "event_log": self.event_log,
        }
