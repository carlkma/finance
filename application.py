import os
import json
from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    info = db.execute("SELECT * FROM stocks WHERE user_id=:ID",ID=session["user_id"])
    symbolinfo = []
    sharesinfo = []
    price = []
    value_of_holding = []
    grand_total = 0
    count = []
    for i in range(len(info)):
        count.append(i)
        symbolinfo.append(info[i]["symbol"])
        price.append(usd(lookup(info[i]["symbol"])["price"]))
        sharesinfo.append(info[i]["shares"])
        value_of_holding.append(usd(lookup(info[i]["symbol"])["price"]*info[i]["shares"]))
        grand_total += lookup(info[i]["symbol"])["price"]*info[i]["shares"]
    
    balance = db.execute("SELECT cash FROM users WHERE id = :ID", ID=session["user_id"])
    balance = balance[0].get("cash")
    username = db.execute("SELECT username FROM users WHERE id = :ID", ID=session["user_id"])
    username = username[0].get("username")
    grand_total += balance
    balance = usd(balance)
    grand_total = usd(grand_total)
    return render_template("index.html",symbolinfo=symbolinfo,price=price, sharesinfo=sharesinfo,value_of_holding=value_of_holding,count=count, balance=balance,grand_total=grand_total,username=username)


@app.route("/buy", methods=["GET"])
@login_required
def load_buy():
    return render_template("buy.html")


@app.route("/buy", methods=["POST"])
@login_required
def buy():
    balance = db.execute("SELECT cash FROM users WHERE id = :ID", ID=session["user_id"])
    balance = balance[0].get("cash")
    if not request.form.get("symbol") or not request.form.get("shares"):
        return apology("Please complete all fields")
    try:
        num = int(request.form.get("shares"))
    except ValueError:
        return apology("Please enter a valid number of shares")
    if num <= 0:
        return apology("Please enter a valid number of shares")
    if not lookup(request.form.get("symbol").upper()):
        return apology("Please enter a valid symbol")
    
    total = num * lookup(request.form.get("symbol").upper())["price"]
    if balance < total:
        return apology("Not enough balance")
    id_of_stocks = db.execute("SELECT id FROM stocks WHERE user_id=:a AND symbol=:b",a=session["user_id"],b=request.form.get("symbol").upper())
    if not id_of_stocks:
        db.execute("INSERT INTO stocks(user_id,symbol,shares) VALUES(:a,:b,:c)",a=session["user_id"],b=request.form.get("symbol").upper(), c=num)
        balance = float(balance) - float(total)
        db.execute("UPDATE users SET cash=:balance WHERE id=:ID", balance=balance,ID=session["user_id"])
        return redirect("/")
    previous_shares = db.execute("SELECT shares FROM stocks WHERE user_id=:a AND symbol=:b",a=session["user_id"],b=request.form.get("symbol").upper())
    previous_shares = previous_shares[0].get("shares")
    db.execute("UPDATE stocks SET shares=:n WHERE user_id=:ID and symbol=:symbol", n=int(previous_shares)+int(num), ID=session["user_id"], symbol=request.form.get("symbol").upper())
    balance = float(balance) - float(total)
    db.execute("UPDATE users SET cash=:balance WHERE id=:ID", balance=balance,ID=session["user_id"])
    return redirect("/")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET"])
@login_required
def load_quote():
    return render_template("quote.html")


@app.route("/quote", methods=["POST"])
@login_required
def quote():
    if not request.form.get("symbol") or not lookup(request.form.get("symbol").upper()):
        return apology("Please enter a valid symbol")
    data = lookup(request.form.get("symbol").upper())
    d1 = data["name"]
    d2 = usd(data["price"])
    d3 = data["symbol"]
    return render_template("quoted.html",d1=d1,d2=d2,d3=d3)

@app.route("/register", methods=["GET"])
def load_register():
    return render_template("register.html")

@app.route("/register", methods=["POST"])
def register():
    if not request.form.get("username") or not request.form.get("password") or not request.form.get("confirmation"):
        return apology("Please complete all fields")
    if request.form.get("password") != request.form.get("confirmation"):
        return apology("Please reenter your password")
    rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))
    if len(rows) == 1:
        return apology("Username already exists")
    db.execute("INSERT INTO users (username,hash) VALUES (:username,:password)", username=request.form.get("username"), password=generate_password_hash(request.form.get("password")))
    return redirect("/")
    
@app.route("/sell", methods=["GET"])
@login_required
def load_sell():
    info = db.execute("SELECT * FROM stocks WHERE user_id=:ID",ID=session["user_id"])
    symbolinfo = ""
    counter = len(info)
    for i in range(len(info)):
        symbolinfo += info[i]["symbol"] + " "
    symbolinfo = symbolinfo.rstrip()
    return render_template("sell.html",symbolinfo=symbolinfo,counter=counter)


@app.route("/sell", methods=["POST"])
@login_required
def sell():
    if not request.form.get("symbol") or not request.form.get("shares"):
        return apology("Please complete all fields")
    try:
        num = int(request.form.get("shares"))
    except ValueError:
        return apology("Please enter a valid number of shares")
    if num <= 0:
        return apology("Please enter a valid number of shares")
    
    info = db.execute("SELECT * FROM stocks WHERE user_id=:ID and symbol=:symbol",ID=session["user_id"],symbol=request.form.get("symbol"))
    if not info:
        return apology("Something went wrong, please try again")
    sharesinfo = info[0]["shares"]
    if num>sharesinfo:
        return apology("You do not have enough shares")
    balance = db.execute("SELECT cash FROM users WHERE id = :ID", ID=session["user_id"])
    balance = balance[0].get("cash")
    total = num * lookup(request.form.get("symbol").upper())["price"]
    db.execute("UPDATE stocks SET shares=:n WHERE user_id=:ID and symbol=:symbol", n=int(sharesinfo)-int(num), ID=session["user_id"], symbol=request.form.get("symbol"))
    if num == sharesinfo:
        db.execute("DELETE FROM stocks WHERE user_id=:ID and symbol=:symbol", ID=session["user_id"], symbol=request.form.get("symbol"))
    balance = float(balance) + float(total)
    db.execute("UPDATE users SET cash=:balance WHERE id=:ID", balance=balance,ID=session["user_id"])
    return redirect("/")
def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


@app.route("/change", methods=["GET"])
@login_required
def load_change():
    return render_template("change.html")

@app.route("/change", methods=["POST"])
@login_required
def change():
    if not request.form.get("password") or not request.form.get("confirmation"):
        return apology("Please complete all fields")
    if request.form.get("password") != request.form.get("confirmation"):
        return apology("Please reenter your password")

    db.execute("UPDATE users SET hash=:h WHERE id=:ID", h=generate_password_hash(request.form.get("password")), ID=session["user_id"])
    return redirect("/")


@app.route("/add", methods=["GET"])
@login_required
def load_add():
    return render_template("add.html")

@app.route("/add", methods=["POST"])
@login_required
def add():
    if not request.form.get("amount"):
        return apology("Please select an amount")
    balance = db.execute("SELECT cash FROM users WHERE id = :ID", ID=session["user_id"])
    balance = balance[0].get("cash")
    balance += float(request.form.get("amount"))
    db.execute("UPDATE users SET cash=:c WHERE id=:ID", c=balance, ID=session["user_id"])
    return redirect("/")


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
