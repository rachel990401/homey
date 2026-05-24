"""
main.py
-------
Homey: One-Stop Family Interaction App
======================================

Entry point for the Homey application. Run this file to start the web app:

    python3 main.py

Homey helps families and shared households coordinate chores, bills, schedules,
paid expenses, and custom lists from one shared workspace.

PROGRAM FLOW:
    1. Load saved household data from disk (storage.py)
    2. Display setup if the household has not been configured
    3. User chooses sections such as Chores, Bills, Schedule, or Paid Expenses
    4. User actions are passed into manager classes (managers.py)
    5. Data is saved after changes and returned to the web view

ADVANCED CONCEPTS USED:
    - File I/O      : storage.py saves, loads, and exports household data
    - Recursion     : StorageManager.clean_saved_value walks nested JSON data
    - Classes       : managers.py contains HomeManager and section managers
    - Try/except    : amount parsing, date validation, JSON loading, file saving
    - Loops         : setup flow, filtering, summaries, calendar generation
    - Break/continue: validation flow, search loops, and settlement matching

EXTERNAL LIBRARY:
    Flask is used for the web version. The browser UI also uses HTML, CSS, and
    JavaScript, but the main validation and calculations are in Python.

Author : [Your Name]
SID    : [Your SID]
Course : [Your Course]
"""

import sys
from typing import Dict, List

from flask import Flask, jsonify, render_template, request

from homey_utils import display_date, section_choices, valid_date
from managers import HomeManager
from storage import StorageManager


app = Flask(__name__)
home = HomeManager()
storage = StorageManager()
storage.load(home)


# ---------- FLASK WEB HELPERS ----------

def save_and_return():
    """
    Save the current Homey state and return it to the web page as JSON.

    Returns:
        flask.Response: Updated application state for JavaScript rendering.
    """
    storage.save(home)
    return jsonify(home.as_dict())


def blocked_section_response(section: str):
    """
    Return the current state when a disabled page receives an action.

    Args:
        section (str): Section name that was blocked.

    Returns:
        flask.Response: Unchanged application state.
    """
    home.log(f"Ignored {section} action because that page is not enabled")
    return jsonify(home.as_dict())


# ---------- FLASK WEB ROUTES ----------

@app.route("/")
def dashboard():
    """Render the main Homey dashboard page."""
    return render_template("index.html")


@app.get("/api/state")
def state():
    """Send the latest Python state to the JavaScript dashboard."""
    return jsonify(home.as_dict())


@app.post("/api/setup")
def setup():
    """
    Complete the first-time setup using names, sections, and expense split.

    The browser collects form values, but Python validates the household
    members, selected sections, and split proportions before the app is built.
    """
    payload = request.get_json(force=True)
    home.setup_home_with_split(payload.get("names", []), payload.get("sections", []), payload.get("split", {}))
    return save_and_return()


@app.post("/api/setup/amend")
def amend_setup():
    payload = request.get_json(force=True)
    part = payload.get("part", "")
    action = payload.get("action", "")
    if part == "members" and action == "add":
        home.add_member(payload.get("name", ""))
    elif part == "members" and action == "delete":
        home.delete_member(payload.get("name", ""), bool(payload.get("confirmed")))
    elif part == "sections":
        home.amend_section(payload.get("section", ""), action)
    else:
        home.set_form_error("setup", "Choose what you want to amend.")
    return save_and_return()


@app.post("/api/expense-split")
def update_expense_split():
    if not home.has_section("expenses"):
        return blocked_section_response("expenses")
    payload = request.get_json(force=True)
    home.update_expense_split(payload.get("split", {}))
    return save_and_return()


@app.post("/api/chores")
def add_chore():
    if not home.has_section("chores"):
        return blocked_section_response("chores")
    chore = home.chores.add_chore(request.get_json(force=True), home.users)
    if chore:
        home.clear_form_error("chore")
        home.log(f"Chore added: {chore['title']}")
    else:
        home.set_form_error("chore", "Please complete the category, task, frequency, date, and person responsible.")
    return save_and_return()


@app.post("/api/chores/<int:chore_id>/complete")
def complete_chore(chore_id: int):
    if not home.has_section("chores"):
        return blocked_section_response("chores")
    home.complete_chore(chore_id)
    return save_and_return()


@app.post("/api/chores/<int:chore_id>/switch-owner")
def switch_chore_owner(chore_id: int):
    if not home.has_section("chores"):
        return blocked_section_response("chores")
    payload = request.get_json(force=True)
    home.switch_chore_owner(chore_id, payload.get("assigned_to", ""))
    return save_and_return()


@app.post("/api/bills")
def add_bill():
    """
    Add a bill after Python validates category, name, amount, date, and owner.

    The amount is parsed in BillManager.parse_amount() using try/except, so
    invalid text input is handled by Python rather than only by the browser.
    """
    if not home.has_section("bills"):
        return blocked_section_response("bills")
    try:
        bill = home.bills.add_bill(request.get_json(force=True), home.users)
    except ValueError as error:
        home.set_form_error("bill", str(error))
        home.log(str(error))
        return jsonify(home.as_dict())
    if bill:
        home.clear_form_error("bill")
        home.log(f"Bill added: {bill['title']}")
    else:
        home.set_form_error("bill", "Please complete the bill category, name, amount, date, and person responsible.")
    return save_and_return()


@app.post("/api/bills/<int:bill_id>/pay")
def pay_bill(bill_id: int):
    if not home.has_section("bills"):
        return blocked_section_response("bills")
    home.mark_bill_paid(bill_id)
    return save_and_return()


@app.post("/api/bills/<int:bill_id>/unpay")
def unpay_bill(bill_id: int):
    if not home.has_section("bills"):
        return blocked_section_response("bills")
    home.mark_bill_unpaid(bill_id)
    return save_and_return()


@app.post("/api/bills/<int:bill_id>/switch-owner")
def switch_bill_owner(bill_id: int):
    if not home.has_section("bills"):
        return blocked_section_response("bills")
    payload = request.get_json(force=True)
    home.switch_bill_owner(bill_id, payload.get("pending_who", ""))
    return save_and_return()


@app.post("/api/schedule")
def add_schedule():
    if not home.has_section("schedule"):
        return blocked_section_response("schedule")
    event = home.schedule.add_event(request.get_json(force=True), home.users)
    if event:
        home.clear_form_error("schedule")
        home.log(f"Schedule added: {event['title']}")
    else:
        home.set_form_error("schedule", "Please complete the event name, number of days, date, owner, and member roles.")
    return save_and_return()


@app.post("/api/schedule/<int:event_id>/response")
def schedule_response(event_id: int):
    if not home.has_section("schedule"):
        return blocked_section_response("schedule")
    payload = request.get_json(force=True)
    home.respond_to_schedule(event_id, payload.get("user", ""), payload.get("response", "Pending"))
    return save_and_return()


@app.post("/api/schedule/<int:event_id>/reschedule")
def reschedule_event(event_id: int):
    if not home.has_section("schedule"):
        return blocked_section_response("schedule")
    payload = request.get_json(force=True)
    home.reschedule_event(event_id, payload)
    return save_and_return()


@app.post("/api/expenses")
def add_expense():
    if not home.has_section("expenses"):
        return blocked_section_response("expenses")
    try:
        expense = home.expenses.add_expense(request.get_json(force=True), home.users)
    except ValueError as error:
        home.set_form_error("expense", str(error))
        home.log(str(error))
        return jsonify(home.as_dict())
    if expense:
        home.clear_form_error("expense")
        home.log(f"Expense added: {expense['title']}")
    else:
        home.set_form_error("expense", "Please complete the expense title, category, amount, date, and who paid.")
    return save_and_return()


@app.post("/api/custom-lists")
def add_custom_list():
    if not home.has_section("custom"):
        return blocked_section_response("custom")
    custom_list = home.custom_lists.add_list(request.get_json(force=True), home.users)
    if custom_list:
        home.clear_form_error("custom")
        home.log(f"Custom list added: {custom_list['title']}")
    else:
        home.set_form_error("custom", "Please enter a list title and owner.")
    return save_and_return()


@app.post("/api/export-summary")
def export_summary():
    export_path = storage.export_summary(home)
    storage.save(home)
    data = home.as_dict()
    data["export_file"] = str(export_path) if export_path else ""
    return jsonify(data)


def prompt_text(question: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    answer = input(f"{question}{suffix}: ").strip()
    return answer or default


def prompt_required(question: str) -> str:
    while True:
        answer = prompt_text(question)
        if answer:
            return answer
        print("Please type something before continuing.")


def prompt_member_count() -> int:
    while True:
        answer = prompt_text("How many family members?")
        try:
            count = int(answer)
        except ValueError:
            print("Use a whole number, for example 4.")
            continue
        if count < 2:
            print("Must be at least 2 members.")
            continue
        if count > 8:
            print("Keep it to 8 family members or fewer for this demo.")
            continue
        return count


def prompt_date(question: str) -> str:
    while True:
        answer = prompt_required(question)
        if valid_date(answer):
            return answer
        print("Use the date format YYYY-MM-DD.")


def prompt_amount(question: str) -> str:
    while True:
        answer = prompt_required(question)
        try:
            if float(answer) > 0:
                return answer
        except ValueError:
            pass
        print("Enter an amount above 0.")


def prompt_positive_int(question: str) -> int:
    while True:
        answer = prompt_required(question)
        try:
            value = int(answer)
        except ValueError:
            print("Use a whole number.")
            continue
        if value >= 1:
            return value
        print("Must be at least 1.")


def prompt_percentage(question: str) -> float:
    while True:
        answer = prompt_required(question)
        try:
            value = float(answer)
        except ValueError:
            print("Enter a percentage from 0 to 100.")
            continue
        if 0 <= value <= 100:
            return value
        print("Enter a percentage from 0 to 100.")


def prompt_yes_no(question: str) -> bool:
    while True:
        answer = prompt_text(f"{question} yes/no").lower()
        if answer in ["yes", "y"]:
            return True
        if answer in ["no", "n"]:
            return False
        print("Please answer yes or no.")


def prompt_choice(question: str, choices: List[str], default: str) -> str:
    """
    Ask the terminal user to choose one option from a numbered list.

    Args:
        question (str): Prompt shown above the choices.
        choices (List[str]): Valid options.
        default (str): Value returned if the user enters an invalid choice.

    Returns:
        str: The chosen option text.
    """
    print(question)
    for index, choice in enumerate(choices, start=1):
        marker = " default" if choice == default else ""
        print(f"  {index}. {choice}{marker}")
    answer = input("Choose number: ").strip()
    if answer.isdigit():
        choice_index = int(answer) - 1
        if 0 <= choice_index < len(choices):
            return choices[choice_index]
    return default


def prompt_from_items(question: str, items: List[dict], label_key: str = "title") -> dict | None:
    if not items:
        print("Nothing here yet.")
        return None
    print(question)
    for index, item in enumerate(items, start=1):
        print(f"  {index}. {item.get(label_key, 'Untitled')}")
    print("  0. Back")
    answer = input("Choose number: ").strip()
    if answer == "0":
        return None
    if answer.isdigit():
        item_index = int(answer) - 1
        if 0 <= item_index < len(items):
            return items[item_index]
    print("That choice was not available.")
    return None


def terminal_setup() -> None:
    """
    Run the setup flow for the command-line mode.

    This mirrors the web setup screen: number of members, member names,
    sections to include, and expense split if Paid Expenses is selected.
    """
    home.reset_workspace()
    print("Welcome to Homey, a family interaction app for household responsibilities, events, payments, and shared expenses.")
    family_count = prompt_member_count()
    names = []
    for index in range(family_count):
        while True:
            name = prompt_required(f"Family member {index + 1} name")
            if name.lower() not in [existing.lower() for existing in names]:
                names.append(name)
                break
            print("Family member names must be unique.")

    section_map = section_choices()
    print("\nChoose which sections to add to this Homey workspace.")
    sections = []
    for key, label in section_map.items():
        if prompt_yes_no(f"Add {label}?"):
            sections.append(key)
    split = {}
    if "expenses" in sections:
        while True:
            split = {name: prompt_percentage(f"{name} expense split %") for name in names}
            if round(sum(split.values()), 2) == 100:
                break
            print("Split must add up to 100%.")
    home.setup_home_with_split(names, sections, split)
    storage.save(home)


def terminal_update_expense_split() -> None:
    if "expenses" not in home.enabled_sections:
        print("Paid expenses is not selected.")
        return
    while True:
        split = {name: prompt_percentage(f"{name} expense split %") for name in home.users}
        if home.update_expense_split(split):
            storage.save(home)
            print("Expense split updated.")
            return
        print("Split must add up to 100%.")


def prompt_attendance(owner: str, users: List[str]) -> Dict[str, str]:
    attendance = {}
    for user in users:
        if user == owner:
            continue
        attendance[user] = prompt_choice(f"{user} attendance", ["Compulsory", "Optional"], "Compulsory")
    return attendance


def print_terminal_summary(period: str) -> None:
    """
    Print the overview summary for the selected terminal period.

    Args:
        period (str): One of all, day, tomorrow, week, next_week, month, next_month.
    """
    summary = home.as_dict()
    print(f"\nFamily overview ({period})")
    for item in summary["member_summaries"][period]:
        print(f"\n{item['user']}")
        if "chores" in home.enabled_sections:
            alerts = item["chore_summary"]["pending_alerts"]
            print("  Chores:")
            if alerts:
                for alert in alerts:
                    print(f"    Pending: {alert['title']} - {alert['detail']}")
            else:
                print("    None pending")
        if "bills" in home.enabled_sections:
            alerts = item["bill_member_summary"]["pending_alerts"]
            print("  Bills:")
            if alerts:
                for alert in alerts:
                    print(f"    Pending Payment: {alert['title'].replace('Payment: ', '')} - {alert['detail']}")
            else:
                print("    None pending")
        if "schedule" in home.enabled_sections:
            schedule = item["schedule_summary"]
            print("  Schedule:")
            for alert in schedule["pending_compulsory"]:
                print(f"    Pending response: {alert['title']} - {alert['detail']}")
            for alert in schedule["pending_optional"]:
                print(f"    Optional response: {alert['title']} - {alert['detail']}")
            if not schedule["pending_compulsory"] and not schedule["pending_optional"]:
                if schedule["upcoming_items"]:
                    for event in schedule["upcoming_items"]:
                        print(f"    Upcoming: {event['title']} - {event['detail']}")
                else:
                    print("    None pending")
        if "expenses" in home.enabled_sections:
            print(f"  Paid expenses: ${item['expenses_paid']:.2f}")


def add_terminal_chore() -> None:
    chore = home.chores.add_chore(
        {
            "category": prompt_required("Chore category"),
            "title": prompt_required("Chore title"),
            "frequency": prompt_choice("Frequency", ["Daily", "Every 2 days", "Weekly", "Monthly"], "Weekly"),
            "due_date": prompt_date("Due date"),
            "assigned_to": prompt_choice("Assign to", home.users, home.users[0]),
        },
        home.users,
    )
    print(f"Added chore: {chore['title']}" if chore else "Chore was not added.")
    storage.save(home)


def add_terminal_bill() -> None:
    try:
        bill = home.bills.add_bill(
            {
                "category": prompt_required("Bill category"),
                "title": prompt_required("Bill title"),
                "amount": prompt_amount("Amount"),
                "due_date": prompt_date("Payment date"),
                "pending_who": prompt_choice("Pending who", home.users, home.users[0]),
            },
            home.users,
        )
    except ValueError as error:
        print(error)
        return
    print(f"Added bill: {bill['title']}" if bill else "Bill was not added.")
    storage.save(home)


def add_terminal_schedule() -> None:
    owner = prompt_choice("Owner", home.users, home.users[0])
    duration_days = prompt_positive_int("Number of days")
    schedule_payload = {
        "title": prompt_required("Schedule title"),
        "duration_days": duration_days,
        "owner": owner,
        "attendance": prompt_attendance(owner, home.users),
        "note": prompt_text("Note", ""),
    }
    if duration_days == 1:
        schedule_payload["date"] = prompt_date("Date")
    else:
        schedule_payload["start_date"] = prompt_date("Start date")
        schedule_payload["end_date"] = prompt_date("End date")
    event = home.schedule.add_event(schedule_payload, home.users)
    print(f"Added schedule item: {event['title']}" if event else "Schedule item was not added.")
    storage.save(home)


def add_terminal_expense() -> None:
    try:
        expense = home.expenses.add_expense(
            {
                "title": prompt_required("Expense title"),
                "category": prompt_required("Expense category"),
                "amount": prompt_amount("Amount"),
                "date": prompt_date("Expense date"),
                "paid_by": prompt_choice("Paid by", home.users, home.users[0]),
                "for_member": prompt_choice("For", ["Household"] + home.users, "Household"),
            },
            home.users,
        )
    except ValueError as error:
        print(error)
        return
    print(f"Added expense: {expense['title']}" if expense else "Expense was not added.")
    storage.save(home)


def add_terminal_custom_list() -> None:
    custom_list = home.custom_lists.add_list(
        {
            "title": prompt_required("List title"),
            "owner": prompt_choice("Owner", home.users, home.users[0]),
            "label": prompt_text("Label", "Custom"),
            "detail": prompt_text("Details", ""),
        },
        home.users,
    )
    print(f"Added list: {custom_list['title']}" if custom_list else "List was not added.")
    storage.save(home)


def print_chores() -> None:
    print("\nChores / household")
    if not home.chores.chores:
        print("No chores added yet.")
        return
    for chore in home.chores.chores:
        status = "Done" if chore["done"] else "Pending"
        print(f"{chore['id']}. {chore['category']}: {chore['title']} | {status} | {chore['assigned_to']} | due {display_date(chore['due_date'])}")


def terminal_chores_page() -> None:
    while True:
        print_chores()
        action = prompt_choice("Chores action", ["Add chore", "Complete chore", "Switch owner", "Back"], "Back")
        if action == "Add chore":
            add_terminal_chore()
            continue
        if action == "Complete chore":
            chore = prompt_from_items("Choose chore to complete", [item for item in home.chores.chores if not item["done"]])
            if chore:
                home.complete_chore(chore["id"])
                storage.save(home)
            continue
        if action == "Switch owner":
            chore = prompt_from_items("Choose chore to switch", [item for item in home.chores.chores if not item["done"]])
            if chore:
                owner = prompt_choice("New owner", home.users, chore["assigned_to"])
                home.switch_chore_owner(chore["id"], owner)
                storage.save(home)
            continue
        break


def print_bills() -> None:
    print("\nBills")
    if not home.bills.bills:
        print("No bills added yet.")
        return
    for bill in home.bills.bills:
        status = "Paid" if bill["paid"] else "Unpaid"
        print(f"{bill['id']}. {bill['category']} - {bill['title']} | ${bill['amount']:.2f} | {status} | {bill['pending_who']} | due {display_date(bill['due_date'])}")


def terminal_bills_page() -> None:
    while True:
        print_bills()
        action = prompt_choice("Bills action", ["Add bill", "Mark paid", "Mark unpaid", "Switch payer", "Back"], "Back")
        if action == "Add bill":
            add_terminal_bill()
            continue
        if action == "Mark paid":
            bill = prompt_from_items("Choose unpaid bill", [item for item in home.bills.bills if not item["paid"]])
            if bill:
                home.mark_bill_paid(bill["id"])
                storage.save(home)
            continue
        if action == "Mark unpaid":
            bill = prompt_from_items("Choose paid bill", [item for item in home.bills.bills if item["paid"]])
            if bill:
                home.mark_bill_unpaid(bill["id"])
                storage.save(home)
            continue
        if action == "Switch payer":
            bill = prompt_from_items("Choose unpaid bill to switch", [item for item in home.bills.bills if not item["paid"]])
            if bill:
                owner = prompt_choice("New pending person", home.users, bill["pending_who"])
                home.switch_bill_owner(bill["id"], owner)
                storage.save(home)
            continue
        break


def print_schedule() -> None:
    print("\nSchedule")
    events = home.schedule.enriched_events()
    if not events:
        print("No schedule items yet.")
        return
    for event in events:
        print(f"{event['id']}. {event['title']} | {event['owner']} | {event['date_label']} | {event['status_text']}")
        for user, response in event["responses"].items():
            print(f"   - {user}: {response} / {event['attendance'].get(user, 'Compulsory')}")


def terminal_schedule_page() -> None:
    while True:
        print_schedule()
        action = prompt_choice("Schedule action", ["Add schedule", "Accept or reject", "Reschedule", "Back"], "Back")
        if action == "Add schedule":
            add_terminal_schedule()
            continue
        if action == "Accept or reject":
            event = prompt_from_items("Choose schedule item", home.schedule.enriched_events())
            if event:
                possible_users = [user for user in event["responses"] if user != event["owner"]]
                user = prompt_choice("Who is responding?", possible_users, possible_users[0]) if possible_users else ""
                response = prompt_choice("Response", ["Accepted", "Declined", "Pending"], "Accepted")
                home.respond_to_schedule(event["id"], user, response)
                storage.save(home)
            continue
        if action == "Reschedule":
            event = prompt_from_items("Choose schedule item", home.schedule.enriched_events())
            if event:
                if event.get("duration_days", 1) > 1:
                    home.reschedule_event(
                        event["id"],
                        {
                            "start_date": prompt_date("New start date"),
                            "end_date": prompt_date("New end date"),
                        },
                    )
                else:
                    home.reschedule_event(event["id"], {"date": prompt_date("New date")})
                storage.save(home)
            continue
        break


def print_expenses() -> None:
    print("\nPaid expenses")
    if not home.expenses.expenses:
        print("No expenses added yet.")
    for expense in home.expenses.expenses:
        print(f"{expense['id']}. {expense['category']} - {expense['title']} | ${expense['amount']:.2f} | paid by {expense['paid_by']} | {display_date(expense['date'])}")
    summary = home.expenses.summary(home.users, home.expense_split)
    print(f"Total paid: ${summary['total']:.2f}")
    print("\nPaid by member")
    for balance in summary["balances"]:
        paid_out = f"-${balance['paid']:.2f}" if balance["paid"] > 0 else "$0.00"
        print(f"- {balance['user']}: {paid_out} paid out | share ${balance['fair_share']:.2f}")
    print("\nReconciliation")
    if summary["settlements"]:
        for settlement in summary["settlements"]:
            print(f"- {settlement['from']} owes {settlement['to']} ${settlement['amount']:.2f}")
    else:
        print("- Everyone is settled.")


def terminal_expenses_page() -> None:
    while True:
        print_expenses()
        action = prompt_choice("Expenses action", ["Add expense", "Change split", "Back"], "Back")
        if action == "Add expense":
            add_terminal_expense()
            continue
        if action == "Change split":
            terminal_update_expense_split()
            continue
        break


def terminal_custom_page() -> None:
    while True:
        print("\nAdd-on lists")
        if home.custom_lists.lists:
            for item in home.custom_lists.lists:
                print(f"{item['id']}. {item['title']} | {item['owner']} | {item['label']} | {item['detail']}")
        else:
            print("No custom lists yet.")
        action = prompt_choice("Add-ons action", ["Add custom list", "Back"], "Back")
        if action == "Add custom list":
            add_terminal_custom_list()
            continue
        break


def terminal_amend_setup() -> None:
    while True:
        action = prompt_choice("What do you want to amend?", ["Members", "Sections", "Expense split", "Back"], "Back")
        if action == "Members":
            member_action = prompt_choice("Action", ["Add member", "Delete member", "Back"], "Back")
            if member_action == "Add member":
                home.add_member(prompt_required("New member name"))
                print(home.form_errors.get("setup", "Member added."))
                storage.save(home)
            elif member_action == "Delete member":
                member = prompt_choice("Delete which member?", home.users, home.users[0])
                if prompt_yes_no(f"Delete {member}? Their pending items will be reassigned."):
                    home.delete_member(member, confirmed=True)
                    print(home.form_errors.get("setup", "Member deleted."))
                    storage.save(home)
            continue
        if action == "Sections":
            section_map = section_choices()
            section_action = prompt_choice("Action", ["Add section", "Remove section", "Back"], "Back")
            if section_action == "Back":
                continue
            section_label = prompt_choice("Section", list(section_map.values()), list(section_map.values())[0])
            section = next(key for key, label in section_map.items() if label == section_label)
            home.amend_section(section, "add" if section_action == "Add section" else "remove")
            print(home.form_errors.get("setup", "Sections updated."))
            if section == "expenses" and section in home.enabled_sections and prompt_yes_no("Set expense split now?"):
                terminal_update_expense_split()
            storage.save(home)
            continue
        if action == "Expense split":
            terminal_update_expense_split()
            continue
        break


def terminal_app() -> None:
    print("\nHomey command-line mode")
    terminal_setup()
    current_period = "week"
    while True:
        print_terminal_summary(current_period)
        actions = []
        if "chores" in home.enabled_sections:
            actions.append("Chores")
        if "bills" in home.enabled_sections:
            actions.append("Bills")
        if "schedule" in home.enabled_sections:
            actions.append("Schedule")
        if "expenses" in home.enabled_sections:
            actions.append("Paid expenses")
        if "custom" in home.enabled_sections:
            actions.append("Add-ons")
        actions.extend(["View summary", "Amend setup", "Export summary", "Open web app", "Exit"])
        action = prompt_choice("Next action", actions, "View summary")
        if action == "Chores":
            terminal_chores_page()
        elif action == "Bills":
            terminal_bills_page()
        elif action == "Schedule":
            terminal_schedule_page()
        elif action == "Paid expenses":
            terminal_expenses_page()
        elif action == "Add-ons":
            terminal_custom_page()
        elif action == "Amend setup":
            terminal_amend_setup()
        elif action == "View summary":
            current_period = prompt_choice("View summary period", ["all", "day", "tomorrow", "week", "next_week", "month", "next_month"], current_period)
            print_terminal_summary(current_period)
        elif action == "Export summary":
            export_path = storage.export_summary(home)
            storage.save(home)
            print(f"Exported to {export_path}" if export_path else "Export failed.")
        elif action == "Open web app":
            print("Open http://127.0.0.1:5001/")
            app.run(host="0.0.0.0", port=5001, debug=False)
            break
        elif action == "Exit":
            break


if __name__ == "__main__":
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "web"
    if mode in ["terminal", "term", "cli"]:
        terminal_app()
    else:
        print("Open http://127.0.0.1:5001/")
        app.run(host="0.0.0.0", port=5001, debug=False)
