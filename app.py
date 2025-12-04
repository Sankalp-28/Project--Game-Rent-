"""
Simple Game Rental Platform (Beginner-friendly)
Technologies: Flask + HTML + CSS + CSV
Author: Your Team
"""

from flask import Flask, render_template, request, redirect, session, url_for
import csv
import os
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "replace_with_some_random_string"  # change for security

# CSV file names
USERS_FILE = "users.csv"
GAMES_FILE = "games.csv"
RENTALS_FILE = "rentals.csv"

# Fine settings (you can change these)
ALLOWED_DAYS_DEFAULT = 7
FINE_PER_DAY = 10  # rupees per extra day


# -----------------------
# Setup CSV files (if missing)
# -----------------------
def ensure_files():
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["email", "name", "password"])  # simple auth
    if not os.path.exists(GAMES_FILE):
        with open(GAMES_FILE, "w", newline="") as f:
            writer = csv.writer(f)
            # columns: game_id, name, price, rent_price, genre, platform, status
            writer.writerow(["game_id", "name", "price", "rent_price", "genre", "platform", "status"])
            # Optional: add sample games (uncomment if you want sample data)
            # writer.writerow(["G1","Cyber Adventure","3999","150","Action","PC","Available"])
            # writer.writerow(["G2","Racing Fury","3499","120","Racing","PS5","Available"])
    if not os.path.exists(RENTALS_FILE):
        with open(RENTALS_FILE, "w", newline="") as f:
            writer = csv.writer(f)
            # columns: rental_id, game_id, user_email, issue_date, due_date, return_date, fine
            writer.writerow(["rental_id", "game_id", "user_email", "issue_date", "due_date", "return_date", "fine"])


# -----------------------
# Helper functions
# -----------------------
def read_csv_dict(filename):
    """Return list of dicts from CSV (preserving header names)."""
    with open(filename, "r", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def write_csv_dict(filename, fieldnames, rows):
    """Write list of dicts to CSV using provided fieldnames."""
    with open(filename, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def append_csv_row(filename, row):
    with open(filename, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(row)


def next_id(prefix, filename):
    """Create a simple next id like G1, G2 or R1, R2 based on rows count."""
    rows = read_csv_dict(filename)
    num = len(rows)  # header excluded by read_csv_dict
    return f"{prefix}{num+1}"


def find_user(email):
    users = read_csv_dict(USERS_FILE)
    for u in users:
        if u["email"].lower() == email.lower():
            return u
    return None


def is_logged_in():
    return "user" in session


# -----------------------
# Routes: Signup / Login / Logout
# -----------------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    ensure_files()
    if request.method == "POST":
        name = request.form.get("name").strip()
        email = request.form.get("email").strip().lower()
        password = request.form.get("password").strip()

        if find_user(email):
            return render_template("signup.html", error="Email already registered")

        append_csv_row(USERS_FILE, [email, name, password])
        return render_template("message.html", title="Signup successful",
                               message="Signup complete. Please login.", link=url_for("login"))

    return render_template("signup.html")


@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    ensure_files()
    if request.method == "POST":
        email = request.form.get("email").strip().lower()
        password = request.form.get("password").strip()

        user = find_user(email)
        if user and user["password"] == password:
            session["user"] = {"email": user["email"], "name": user["name"]}
            return redirect(url_for("home"))
        else:
            return render_template("login.html", error="Invalid email or password")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# -----------------------
# Home / Store (list games)
# -----------------------
@app.route("/home")
def home():
    if not is_logged_in():
        return redirect(url_for("login"))

    ensure_files()
    games = read_csv_dict(GAMES_FILE)
    return render_template("home.html", games=games, user=session.get("user"))


# -----------------------
# Rent page (choose days and confirm)
# -----------------------
@app.route("/rent/<game_id>", methods=["GET", "POST"])
def rent(game_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    games = read_csv_dict(GAMES_FILE)
    game = None
    for g in games:
        if g["game_id"] == game_id:
            game = g
            break
    if not game:
        return render_template("message.html", title="Not found", message="Game not found", link=url_for("home"))

    if request.method == "POST":
        # days user wants to rent
        days = int(request.form.get("days", ALLOWED_DAYS_DEFAULT))
        issue_date = datetime.now()
        due_date = issue_date + timedelta(days=days)

        # create rental record
        rental_id = next_id("R", RENTALS_FILE)
        append_csv_row(RENTALS_FILE, [rental_id, game_id, session["user"]["email"],
                                      issue_date.strftime("%Y-%m-%d"),
                                      due_date.strftime("%Y-%m-%d"),
                                      "-", "0"])

        # mark game as Rented in games.csv
        for g in games:
            if g["game_id"] == game_id:
                g["status"] = "Rented"
        # write back games
        write_csv_dict(GAMES_FILE, ["game_id", "name", "price", "rent_price", "genre", "platform", "status"], games)

        return render_template("message.html", title="Rented",
                               message=f"Game rented successfully until {due_date.strftime('%Y-%m-%d')}",
                               link=url_for("library"))

    # GET -> show rent page
    return render_template("rent.html", game=game, default_days=ALLOWED_DAYS_DEFAULT)


# -----------------------
# User Library (list user's rentals)
# -----------------------
@app.route("/library")
def library():
    if not is_logged_in():
        return redirect(url_for("login"))

    rentals = read_csv_dict(RENTALS_FILE)
    games = read_csv_dict(GAMES_FILE)
    user_email = session["user"]["email"]

    # filter rentals for this user and include game info
    my_rentals = []
    for r in rentals:
        if r["user_email"].lower() == user_email.lower():
            # find game details
            game_info = next((g for g in games if g["game_id"] == r["game_id"]), None)
            # calculate status (active/overdue/returned)
            status = "Active"
            if r["return_date"] and r["return_date"] != "-":
                status = "Returned"
            else:
                due = datetime.strptime(r["due_date"], "%Y-%m-%d")
                if datetime.now() > due:
                    status = "Overdue"
            my_rentals.append({"rental": r, "game": game_info, "status": status})

    return render_template("library.html", rentals=my_rentals)


# -----------------------
# Return a game (calculates fine if late)
# -----------------------
@app.route("/return/<rental_id>", methods=["POST"])
def return_rental(rental_id):
    if not is_logged_in():
        return redirect(url_for("login"))

    rentals = read_csv_dict(RENTALS_FILE)
    updated = []
    fine_amount = 0
    returned_game_id = None

    for r in rentals:
        if r["rental_id"] == rental_id:
            # process this return
            returned_game_id = r["game_id"]
            if r["return_date"] and r["return_date"] != "-":
                # already returned
                pass
            else:
                due = datetime.strptime(r["due_date"], "%Y-%m-%d")
                now = datetime.now()
                days_late = (now - due).days
                if days_late > 0:
                    fine_amount = days_late * FINE_PER_DAY
                r["return_date"] = now.strftime("%Y-%m-%d")
                r["fine"] = str(fine_amount)
        updated.append(r)

    # write back rentals
    write_csv_dict(RENTALS_FILE, ["rental_id", "game_id", "user_email", "issue_date", "due_date", "return_date", "fine"], updated)

    # mark the game available again in games.csv
    if returned_game_id:
        games = read_csv_dict(GAMES_FILE)
        for g in games:
            if g["game_id"] == returned_game_id:
                g["status"] = "Available"
        write_csv_dict(GAMES_FILE, ["game_id", "name", "price", "rent_price", "genre", "platform", "status"], games)

    if fine_amount > 0:
        msg = f"Returned. Fine: Rs {fine_amount}"
    else:
        msg = "Returned successfully. No fine."

    return render_template("message.html", title="Return processed", message=msg, link=url_for("library"))


# -----------------------
# Admin helper (optional): add sample games quickly
# -----------------------
@app.route("/admin/add_sample")
def add_sample():
    # only for development convenience
    ensure_files = None  # placeholder to avoid lint error
    games = read_csv_dict(GAMES_FILE)
    # if empty (only header), add samples
    if len(games) == 0:
        append_csv_row(GAMES_FILE, ["G1", "Cyber Adventure", "3999", "150", "Action", "PC", "Available"])
        append_csv_row(GAMES_FILE, ["G2", "Racing Fury", "3499", "120", "Racing", "PS5", "Available"])
        append_csv_row(GAMES_FILE, ["G3", "Puzzle Land", "999", "50", "Puzzle", "PC", "Available"])
        return "Sample games added. Go to /home"
    return "Games already exist."

# -----------------------
# Run the app
# -----------------------
if __name__ == "__main__":
    ensure_files()
    app.run(debug=True)
