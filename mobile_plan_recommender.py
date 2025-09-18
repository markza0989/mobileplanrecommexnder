# Mobile Plan Recommender
import json
import os
import sqlite3
from typing import Dict, Any, Tuple, Optional

PROGRAM_AUTHOR = "Nopporn Khongnongdaeng"
STUDENT_ID = "30448348"
PROGRAM_NAME = "Mobile Plan Recommender"

PLANS_JSON = "plans.json"   #Randomly assigned Mobile Plans file
DB_FILE = "usage_details.sqlite3" # SQLite database for usage details

#Utility: input helpers
def input_int(prompt: str, minimum: int = 0) -> int:
    """Prompt until the user enters a valid integer >= minimum."""
    while True:
        raw = input(prompt).strip()
        try:
            value = int(raw)
            if value < minimum:
                print(f"Please enter a number >= {minimum}.\n")
                continue
            return value
        except ValueError:
            print("Invalid number. Please try again.\n")

def input_float(prompt: str, minimum: float = 0.0) -> float:
    """Prompt until the user enters a valid float >= minimum."""
    while True:
        raw = input(prompt).strip()
        try:
            value = float(raw)
            if value < minimum:
                print(f"Please enter a number >= {minimum}.\n")
                continue
            return value
        except ValueError:
            print("Invalid number. Please try again.\n")

def input_yes_no(prompt: str) -> bool:
    """Return True for yes, False for no."""
    while True:
        raw = input(prompt + " (y/n): ").strip().lower()
        if raw in ("y", "yes"): return True
        if raw in ("n", "no"): return False
        print("Please answer y or n.\n")

#Plans: load & validate
def load_plans(path: str) -> Dict[str, Dict[str, Any]]:
    """Load plans from JSON. Returns a dict keyed by plan_code.

    Schema per plan:
    {
      "plan_code": "ABC",
      "provider": "TelcoX",
      "plan_name": "Saver 30",
      "base_cost": 30.0,
      "included_minutes": 300,
      "included_data_gb": 10.0,
      "cost_per_minute": 0.3,
      "cost_per_gb": 8.0,
      "roaming_included": false
    }
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"WARNING: '{path}' not found. Please create it with the five plans from Moodle.\n")
        return {}
    except json.JSONDecodeError as ex:
        print(f"ERROR: Could not parse '{path}': {ex}\n")
        return {}

    plans: Dict[str, Dict[str, Any]] = {}
    for item in data.get("plans", []):
        # Basic validation and coercion
        try:
            code = str(item["plan_code"]).strip()
            plans[code] = {
                "provider": str(item["provider"]).strip(),
                "plan_name": str(item["plan_name"]).strip(),
                "base_cost": float(item["base_cost"]),
                "included_minutes": int(item["included_minutes"]),
                "included_data_gb": float(item["included_data_gb"]),
                "cost_per_minute": float(item["cost_per_minute"]),
                "cost_per_gb": float(item["cost_per_gb"]),
                "roaming_included": bool(item["roaming_included"]),
                # Any unknown fields are ignored.
            }
        except (KeyError, ValueError, TypeError) as ex:
            print(f"WARNING: Skipping invalid plan entry: {item} (reason: {ex})")
    if len(plans) < 5:
        print("NOTE: Fewer than five valid plans were loaded. Make sure you copied all five from Moodle.\n")
    return plans

#Cost calculation
def cost_for_usage(plan: Dict[str, Any], minutes: int, data_gb: float) -> float:
    extra_minutes = max(0, minutes - int(plan["included_minutes"]))
    extra_data_gb = max(0.0, data_gb - float(plan["included_data_gb"]))
    return float(plan["base_cost"]) + extra_minutes * float(plan["cost_per_minute"]) + extra_data_gb * float(plan["cost_per_gb"])

#SQLite helpers (extension)
def init_db(db_path: str = DB_FILE) -> None:
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute(
        """CREATE TABLE IF NOT EXISTS usage_details (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               person_name TEXT NOT NULL,
               minutes INTEGER NOT NULL,
               data_gb REAL NOT NULL,
               roaming_required INTEGER NOT NULL CHECK(roaming_required IN (0,1)),
               created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
           )"""
    )
    con.commit()
    con.close()

def save_usage(person_name: str, minutes: int, data_gb: float, roaming: bool, db_path: str = DB_FILE) -> None:
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute(
        "INSERT INTO usage_details (person_name, minutes, data_gb, roaming_required) VALUES (?,?,?,?)",
        (person_name, minutes, data_gb, 1 if roaming else 0),
    )
    con.commit()
    con.close()

def load_usage(person_name: str, db_path: str = DB_FILE) -> Optional[Tuple[int, float, bool]]:
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute(
        "SELECT minutes, data_gb, roaming_required FROM usage_details WHERE person_name = ? ORDER BY created_at DESC LIMIT 1",
        (person_name,),
    )
    row = cur.fetchone()
    con.close()
    if row:
        minutes, data_gb, roaming_int = row
        return int(minutes), float(data_gb), bool(roaming_int)
    return None

def show_stats(db_path: str = DB_FILE) -> None:
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    # Basic descriptive stats
    cur.execute("SELECT COUNT(*), AVG(minutes), AVG(data_gb) FROM usage_details")
    count, avg_min, avg_gb = cur.fetchone()
    cur.execute("SELECT MIN(minutes), MAX(minutes), MIN(data_gb), MAX(data_gb) FROM usage_details")
    min_min, max_min, min_gb, max_gb = cur.fetchone()
    cur.execute("SELECT SUM(roaming_required), COUNT(*) FROM usage_details")
    roam_count, total = cur.fetchone()
    con.close()
    if not count:
        print("No saved usage yet.\n")
        return
    roaming_pct = (roam_count or 0) * 100.0 / max(1, total or 1)
    print("\n== Saved Usage Statistics ==")
    print(f"Total records: {count}")
    print(f"Average minutes: {avg_min:.1f}, average data: {avg_gb:.2f} GB")
    print(f"Minutes range: {min_min} - {max_min}; Data range: {min_gb:.2f} - {max_gb:.2f} GB")
    print(f"Roaming required: {roaming_pct:.1f}% of saved profiles\n")

#Menu handlers
def display_current_usage(current: Dict[str, Any]) -> None:
    if not current:
        print("Current usage: (not set yet)\n")
        return
    print("Current usage:")
    print(f"  Person: {current.get('person_name','(Anonymous)')}")
    print(f"  Minutes per month: {current['minutes']}")
    print(f"  Data per month: {current['data_gb']} GB")
    print(f"  International roaming required: {'Yes' if current['roaming_required'] else 'No'}\n")

def display_plan_costs(plans: Dict[str, Dict[str, Any]], current: Dict[str, Any]) -> None:
    if not current:
        print("Please enter usage details first.\n")
        return
    if not plans:
        print("No plans loaded. Create 'plans.json' with the five plans from Moodle.\n")
        return
    print("\n== Plan Costs for Current Usage ==")
    for code, plan in plans.items():
        monthly = cost_for_usage(plan, current['minutes'], current['data_gb'])
        eligible = True
        if current['roaming_required'] and not plan['roaming_included']:
            eligible = False
        tag = "(eligible)" if eligible else "(NOT eligible for required roaming)"
        full_name = f"{plan['provider']} - {plan['plan_name']}"
        print(f"{code}: {full_name} -> ${monthly:.2f} {tag}")
    print()

def recommend_best_plan(plans: Dict[str, Dict[str, Any]], current: Dict[str, Any]) -> None:
    if not current:
        print("Please enter usage details first.\n")
        return
    if not plans:
        print("No plans loaded. Create 'plans.json' with the five plans from Moodle.\n")
        return
    best_code = None
    best_cost = None
    for code, plan in plans.items():
        if current['roaming_required'] and not plan['roaming_included']:
            continue  # skip plans that don't meet roaming requirement
        monthly = cost_for_usage(plan, current['minutes'], current['data_gb'])
        if best_cost is None or monthly < best_cost:
            best_cost = monthly
            best_code = code
    if best_code is None:
        print("No plan meets the requirement for international roaming.\n")
        return
    plan = plans[best_code]
    print("\n== Recommended Plan ==")
    print(f"{plan['provider']} - {plan['plan_name']} (code: {best_code})")
    print(f"Estimated monthly cost: ${best_cost:.2f}")
    print(f"Includes roaming: {'Yes' if plan['roaming_included'] else 'No'}\n")

#Main loop 
def main() -> None:
    print("="*60)
    print(f"Welcome to {PROGRAM_NAME}!\nBy {PROGRAM_AUTHOR} (Student ID: {STUDENT_ID})")
    print("="*60 + "\n")

    # Load plans and init DB (extension)
    plans = load_plans(PLANS_JSON)
    init_db(DB_FILE)

    current_usage: Dict[str, Any] = {}  # will hold person_name, minutes, data_gb, roaming_required

    while True:
        # Always show current usage at the top (also has its own menu item)
        display_current_usage(current_usage)
        print("Menu:")
        print("  1) Enter usage details")
        print("  2) Display current usage details")
        print("  3) Display plan costs")
        print("  4) Recommend best plan")
        print("  5) Save current usage (extension)")
        print("  6) Load usage for a person (extension)")
        print("  7) Show usage statistics (extension)")
        print("  8) Exit")

        choice = input("Choose an option (1-8): ").strip()
        print()  # visual spacing

        if choice == "1":
            person_name = input("Enter person's name (for saving later; can be blank): ").strip() or "(Anonymous)"
            minutes = input_int("Typical monthly call minutes: ", minimum=0)
            data_gb = input_float("Typical monthly data usage (GB): ", minimum=0.0)
            roaming = input_yes_no("Require international roaming?")
            current_usage = {
                "person_name": person_name,
                "minutes": minutes,
                "data_gb": data_gb,
                "roaming_required": roaming,
            }
            print("Saved current usage details.\n")

        elif choice == "2":
            display_current_usage(current_usage)

        elif choice == "3":
            display_plan_costs(plans, current_usage)

        elif choice == "4":
            recommend_best_plan(plans, current_usage)

        elif choice == "5":
            if not current_usage:
                print("Please enter usage details first.\n")
            else:
                save_usage(current_usage['person_name'], current_usage['minutes'], current_usage['data_gb'], current_usage['roaming_required'])
                print("Usage details saved to SQLite.\n")

        elif choice == "6":
            name = input("Load usage for which person name? ").strip()
            loaded = load_usage(name)
            if loaded is None:
                print("No saved usage found for that name.\n")
            else:
                minutes, data_gb, roaming = loaded
                current_usage = {
                    "person_name": name,
                    "minutes": minutes,
                    "data_gb": data_gb,
                    "roaming_required": roaming,
                }
                print("Loaded usage details into current profile.\n")

        elif choice == "7":
            show_stats()

        elif choice == "8":
            print("Thank you for using the Mobile Plan Recommender. Goodbye!\n")
            break

        else:
            print("Invalid choice. Please pick 1-8.\n")

if __name__ == "__main__":
    main()
