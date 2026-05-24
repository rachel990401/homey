HOMEY - ONE-STOP FAMILY INTERACTION APP
=======================================

Main script to run:
    main.py

How to run:
    1. Run:
       python3 main.py
    2. Open this link in a browser:
       http://127.0.0.1:5001

External library used:
    Flask

Important note for tutor:
    Homey is a web-based application using Flask, HTML, CSS, and JavaScript.
    The main business logic is written in Python inside managers.py.

Python files submitted:
    main.py          - main entry point and Flask routes
    managers.py     - main classes and business logic
    storage.py      - file input/output for saving, loading, and exporting data
    homey_utils.py  - date helpers, period filtering, and section choices

Other supporting files for the web version:
    templates/index.html
    static/app.js
    static/styles.css

Advanced Python concepts included:
    Classes and objects:
        HomeManager, ChoreManager, BillManager, ScheduleManager,
        ExpenseManager, CustomListManager, StorageManager

    File I/O:
        storage.py saves and loads JSON data from data/homey_state.json.
        It can also export a text summary into the exports folder.

    Try/except:
        Used for amount parsing, date validation, JSON loading, and file saving.

    For loops:
        Used for setup, member summaries, grouping chores, bills, schedules,
        calendar generation, and expense reconciliation.

    While loops:
        Used for repeated validation flows and date range checks.

    Break and continue:
        Used in validation flow, search loops, and settlement calculations.

    Recursion:
        StorageManager.clean_saved_value() recursively checks nested saved JSON
        data before loading it into the application.

    Return:
        Used throughout manager functions to stop invalid actions early or send
        updated objects back to the caller.

Files/folders automatically created when running:
    data/
    exports/

These generated folders do not need to be submitted unless the tutor asks for
sample saved data.
