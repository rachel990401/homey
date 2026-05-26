# Homey — One-Stop Family Interaction App

> *Less reminding, less guessing, more shared responsibility at home.*

![Python](https://img.shields.io/badge/Python-3.8+-blue?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-Web%20App-black?logo=flask&logoColor=white)
![Status](https://img.shields.io/badge/Status-Complete-brightgreen)
![Project](https://img.shields.io/badge/Project-Family%20Management-blue)

---

## What Is Homey?

Many family conflicts start from small repeated problems: someone forgets a bill, a chore is unclear, an outing date is not confirmed, or one person pays first and nobody knows who owes who.

**Homey** is a one-stop family interaction app for busy households. Users first set up family members and choose only the sections they need, such as Chores, Bills, Schedule, Paid Expenses, or custom add-on lists. Homey then builds a shared workspace where every member can see their responsibilities, upcoming events, pending payments, and household expense reconciliation.

---

## Core Idea

Homey is designed around one question:

> How can a household reduce repeated reminders and make shared responsibilities visible?

Instead of treating chores, bills, schedules, and expenses as separate problems, Homey connects them:

| Situation | Homey Response |
|---|---|
| A bill is unpaid | Shows a pending payment reminder for the assigned person |
| A bill is marked paid | Moves the amount into Paid Expenses automatically |
| A family event is created | Invited members accept or reject based on compulsory/optional role |
| A compulsory member rejects | Event is flagged for rescheduling |
| Shared expenses are paid | Calculates who owes who based on split proportions |

---

## Features

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Setup Flow** | Add family members, choose sections, and set expense split proportions |
| 2 | **Family Overview** | Member cards show pending chores, pending payments, upcoming events, and paid expenses |
| 3 | **Chores / Household** | Add household tasks, assign owners, switch owners, and mark tasks complete |
| 4 | **Bills / Payments** | Track bill category, name, amount, due date, paid status, and responsible member |
| 5 | **Schedule** | Create one-day or multi-day events with compulsory/optional responses |
| 6 | **Paid Expenses** | Track who paid and calculate household reconciliation |
| 7 | **Custom Add-ons** | Add extra lists for workflows outside the standard sections |
| 8 | **Export Summary** | Save a text summary of household data using file I/O |

---

## Getting Started

**Requirements:** Python 3.8 or higher.

**External library used:** Flask.

Install Flask if needed:

```bash
pip3 install flask
```

Run the web app:

```bash
python3 main.py
```

Then open:

```text
http://127.0.0.1:5001
```

## Project Structure

```text
homey/
├── main.py              # Entry point and Flask routes
├── managers.py          # Main classes and Python business logic
├── storage.py           # File I/O for JSON save/load and text export
├── homey_utils.py       # Date helpers, period filtering, and section labels
├── README.md            # Project overview for GitHub
├── README.txt           # Tutor run instructions and dependency notes
├── templates/
│   └── index.html       # Web page structure
└── static/
    ├── app.js           # Browser rendering and button interactions
    └── styles.css       # Dark mode Notion/FAANG-style interface
```

The generated `data/`, `exports/`, and `__pycache__/` folders do not need to be submitted.

---

## Demo Flow

```text
Welcome to Homey

1. Set up household members
   Example: Mum, Dad, Son, Daughter

2. Choose sections
   Chores / household
   Bills / payments
   Schedule
   Paid expenses
   Custom add-on lists

3. Add household items
   Chore: Laundry - Wash clothes - assigned to Mum
   Bill : Wifi - Jan Optus - $200 - assigned to Dad
   Event: Japan Holiday - Mum creates, Dad/R respond

4. View overview
   Mum sees assigned chores and upcoming events
   Dad sees pending payments
   Expenses show who paid and who owes who
```

---

## Python-First Design

The important rules live in Python. JavaScript mainly helps the browser display buttons, pages, cards, and refreshed state.

The web interface calls the Python manager classes for validation, calculations, and state updates:

| Manager | Responsibility |
|---------|----------------|
| `HomeManager` | Coordinates setup, sections, summaries, and shared app state |
| `ChoreManager` | Adds, completes, groups, and switches household tasks |
| `BillManager` | Validates bills, tracks paid/unpaid status, and payment owner |
| `ScheduleManager` | Handles event dates, compulsory/optional responses, and rescheduling |
| `ExpenseManager` | Tracks paid expenses and calculates who owes who |
| `CustomListManager` | Stores flexible add-on lists |
| `StorageManager` | Saves, loads, cleans, and exports data |

---

## Advanced Concepts

| Concept | File | Implementation |
|---------|------|----------------|
| **Classes & Objects** | `managers.py`, `storage.py` | Manager classes organise chores, bills, schedule, expenses, setup, and storage |
| **File I/O** | `storage.py` | Saves/loads `data/homey_state.json` and exports summaries to `exports/` |
| **Recursion** | `storage.py` | `clean_saved_value()` recursively walks nested saved JSON data |
| **Try/Except** | `managers.py`, `storage.py`, `homey_utils.py` | Handles amount parsing, date parsing, JSON loading, and file writing errors |
| **For Loops** | `main.py`, `managers.py` | Used for setup, section selection, summaries, grouping, filtering, and calendar generation |
| **While Loops** | `main.py`, `homey_utils.py` | Used for repeated validation flows and multi-day date checks |
| **Break / Continue** | `main.py`, `managers.py`, `storage.py` | Used in validation, search loops, and reconciliation matching |
| **Return Values** | All Python files | Functions return updated objects, validation results, summaries, or early exits |

---

## Tutor Notes

Homey is a **web-based application** using Flask, HTML, CSS, and JavaScript. It may need to be run outside Ed if Flask or local web hosting is not available in the Ed environment.

---

*Built as a Python-first project with a web dashboard for presentation.*
