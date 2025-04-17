from flask import Flask, render_template, request, redirect, url_for, session
from sqlalchemy import create_engine, text
from flask_sqlalchemy import SQLAlchemy
import hashlib

app = Flask(__name__)

con_str = "mysql://root:cset155@localhost/MultiVendorEcommerce"
engine = create_engine(con_str, echo=True)
conn = engine.connect()
app.secret_key = "idkwhattoput"
app.config['SQLALCHEMY_DATABASE_URI'] = con_str
db = SQLAlchemy(app)


@app.route("/")
def home():
    query = text("""
        SELECT p.ProductID, p.Title, p.DiscountedPrice, pi.ImageURL
        FROM Products p
        LEFT JOIN ProductImages pi ON p.ProductID = pi.ProductID
        LIMIT 5
    """)
    result = conn.execute(query)
    products = result.fetchall()
    return render_template("home.html", products=products)

@app.route("/home")
def home2():
    query = text("""
        SELECT p.ProductID, p.Title, p.DiscountedPrice, pi.ImageURL
        FROM Products p
        LEFT JOIN ProductImages pi ON p.ProductID = pi.ProductID
        LIMIT 5
    """)
    result = conn.execute(query)
    products = result.fetchall()
    username = session.get("username")
    if not username:
        return redirect(url_for("login"))
    return render_template("home.html", username=username, products=products)


@app.route("/search")
def search():
    query = request.args.get('q')
    if not query:
        return redirect(url_for('products'))
    search_query = text("""
        SELECT p.ProductID, p.Title, p.DiscountedPrice, pi.ImageURL
        FROM Products p
        LEFT JOIN ProductImages pi ON p.ProductID = pi.ProductID
        WHERE p.Title LIKE :search
    """)
    result = conn.execute(search_query, {"search": f"%{query}%"})
    products = result.fetchall()
    return render_template("search_results.html", query=query, products=products)

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        username = request.form["username"]
        password = request.form["password"]
        role = request.form["role"]

        if not email or "@" not in email:
            return render_template("signup.html", error="Please enter a valid email address.")
        
        if len(password) < 6:
            return render_template("signup.html", error="Password must be at least 6 characters long.")

        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        if role == "vendor":
            username += "_vend"

        try:
            with engine.connect() as conn:
                check_email_query = text("SELECT * FROM User WHERE Email = :email")
                email_result = conn.execute(check_email_query, {"email": email}).fetchone()

                if email_result:
                    return render_template("signup.html", error="Email is already registered.")

             
                check_username_query = text("SELECT * FROM User WHERE Username = :username")
                username_result = conn.execute(check_username_query, {"username": username}).fetchone()

                if username_result:
                    return render_template("signup.html", error="Username is already taken.")

                insert_query = text("""
                    INSERT INTO User (Name, Email, Username, Password)
                    VALUES (:name, :email, :username, :password)
                """)
                with engine.begin() as conn:
                    conn.execute(insert_query, {
                        "name": name,
                        "email": email,
                        "username": username,
                        "password": hashed_password
                    })



            return render_template("signup_success.html", username=username)

        except Exception as e:
            return render_template("signup.html", error=f"An error occurred: {e}")

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["Email"] 
        password = request.form["password"]
        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        try:
            with engine.connect() as conn:
                query = text("""
                    SELECT * FROM User
                    WHERE Email = :email AND Password = :password
                """)
                result = conn.execute(query, {
                    "email": email,
                    "password": hashed_password
                }).fetchone()
                if result:
                    session["username"] = result[1]
                    return redirect(url_for("home2"))
                else:
                    return f"<h3>Invalid email or password.</h3><a href='{url_for('login')}'>Try again</a>"

        except Exception as e:
            return f"<h3>Login error: {e}</h3>"

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/products")
def products():
    query = text("""
        SELECT p.ProductID, p.Title, p.DiscountedPrice, pi.ImageURL, p.Color, p.Size, p.InventoryAmount
        FROM Products p
        LEFT JOIN ProductImages pi ON p.ProductID = pi.ProductID;

    """)
    result = conn.execute(query)
    products = result.fetchall()
    username = session.get("username")
    return render_template("products.html", products=products, username=username)

@app.route("/product/<int:product_id>")
def product_detail(product_id):
    query = text("""
        SELECT p.ProductID, p.Title, p.DiscountedPrice, pi.ImageURL
        FROM Products p
        LEFT JOIN ProductImages pi ON p.ProductID = pi.ProductID
        WHERE p.ProductID IN :product_id
    """)
    result = conn.execute(query, {"product_ids": tuple(product_id)})
    products = result.fetchall()
    return render_template("product_detail.html", product=products[0])


class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    product = db.relationship('Product', back_populates='cart_items')

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    cart_items = db.relationship('CartItem', back_populates='product')

@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    # Query to get product and image
    query = text("""
        SELECT p.ProductID, p.Title, p.DiscountedPrice, pi.ImageURL
        FROM Products p
        LEFT JOIN ProductImages pi ON p.ProductID = pi.ProductID
        WHERE p.ProductID = :product_id
        LIMIT 1
    """)
    result = conn.execute(query, {"product_id": product_id}).fetchone()

    if not result:
        return redirect(url_for('home'))

    if 'cart' not in session:
        session['cart'] = []

    product_in_cart = next((item for item in session['cart'] if item['product_id'] == product_id), None)

    if product_in_cart:
        product_in_cart['quantity'] += 1
    else:
        session['cart'].append({
            'product_id': result.ProductID,
            'name': result.Title,
            'price': result.DiscountedPrice,
            'quantity': 1,
            'image': result.ImageURL or "https://via.placeholder.com/150"
        })

    session.modified = True
    return redirect(url_for('cart'))


@app.route('/cart')
def cart():
    cart = session.get('cart', [])
    product_ids = [item['product_id'] for item in cart]
    
    if not product_ids:
        return render_template("cart.html", products=[], total_price=0, cart=cart)

    query = text("""
        SELECT p.ProductID, p.Title, p.DiscountedPrice, pi.ImageURL
        FROM Products p
        LEFT JOIN ProductImages pi ON p.ProductID = pi.ProductID
        WHERE p.ProductID IN :product_ids
    """)
    result = conn.execute(query, {"product_ids": tuple(product_ids)})
    products = result.fetchall()

    total_price = 0
    for product in products:
        for item in cart:
            if item['product_id'] == product.ProductID:
                total_price += product.DiscountedPrice * item['quantity']

    return render_template("cart.html", products=products, total_price=total_price, cart=cart)

@app.route('/update_cart', methods=['POST'])
def update_cart():
    if 'cart' not in session:
        return redirect(url_for('cart'))

    cart = session['cart']
    quantities = request.form.getlist('quantities')

    updated_cart = []
    for item in cart:
        product_id = item['product_id']
        quantity = int(request.form.get(f'quantities[{product_id}]', item['quantity']))

        # Delete button logic
        if f'delete_{product_id}' in request.form:
            continue  # skip adding to new cart

        item['quantity'] = quantity
        updated_cart.append(item)

    session['cart'] = updated_cart
    session.modified = True
    return redirect(url_for('cart'))


@app.route("/checkout")
def checkout():
    cart = session.get('cart', [])
    total_price = 0
    product_ids = [item['product_id'] for item in cart]
    query = text("""
        SELECT p.ProductID, p.DiscountedPrice
        FROM Products p
        WHERE p.ProductID IN :product_ids
    """)
    result = conn.execute(query, {"product_ids": tuple(product_ids)})
    products = result.fetchall()
    for product in products:
        for item in cart:
            if item['product_id'] == product['ProductID']:
                total_price += product['DiscountedPrice'] * item['quantity']

    return render_template("checkout.html", products=products, total_price=total_price)

if __name__ == '__main__':
    app.run(debug=True)
