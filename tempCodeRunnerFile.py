    return render_template("vendor_dashboard.html", vendor_name=vendor_name)


@app.route("/products")
def products():
    category = request.args.get('category')
    color = request.args.get('color')
    size = request.args.get('size')
    availability = request.args.get('availability')  # 'in' or 'out'

    query_base = """
        SELECT p.ProductID, p.Title, p.DiscountedPrice, pi.ImageURL, p.Color, p.Size, 
               p.InventoryAmount, p.Category
        FROM Products p
        LEFT JOIN ProductImages pi ON p.ProductID = pi.ProductID
        WHERE 1=1
    """
    filters = {}
    if category:
        query_base += " AND p.Category = :category"
        filters['category'] = category
    if color:
        query_base += " AND FIND_IN_SET(:color, p.Color)"
        filters['color'] = color
    if size:
        query_base += " AND FIND_IN_SET(:size, p.Size)"
        filters['size'] = size
    if availability == 'in':
        query_base += " AND p.InventoryAmount > 0"
    elif availability == 'out':
        query_base += " AND p.InventoryAmount = 0"

    result = conn.execute(text(query_base), filters)
    products = result.fetchall()
    return render_template("products.html", products=products)

@app.route("/product/<int:product_id>")
def product_detail(product_id):
    query = text("""
        SELECT p.ProductID, p.Title, p.Description, p.DiscountedPrice, p.Category, 
               p.Color, p.Size, p.InventoryAmount, p.WarrantyPeriod, pi.ImageURL
        FROM Products p
        LEFT JOIN ProductImages pi ON p.ProductID = pi.ProductID
        WHERE p.ProductID = :product_id
    """)
    result = conn.execute(query, {"product_id": product_id}).fetchone()
    if not result:
        return "<h3>Product not found.</h3>"

    product = dict(result._mapping)
    product["colors"] = product["Color"].split() if product["Color"] else []
    product["sizes"] = product["Size"].split() if product["Size"] else []
    product["categories"] = product["Category"].split() if product["Category"] else []
    return render_template("product_detail.html", product=product)

# Cart item model for SQLAlchemy (manages cart items in the database)
class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    product = db.relationship('Product', back_populates='cart_items')

# Product model for SQLAlchemy (manages product information in the database)
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    cart_items = db.relationship('CartItem', back_populates='product')

@app.route("/add_to_cart/<int:product_id>", methods=["POST"])
def add_to_cart(product_id):
    if 'cart' not in session:
        session['cart'] = []  # Initialize the cart if it doesn't exist

    # Retrieve form data for color, size, and quantity
    color = request.form.get('color')
    size = request.form.get('size')
    quantity = int(request.form.get('quantity', 1))

    # Check if the item with selected color and size already exists in the cart
    product_in_cart = next((item for item in session['cart'] if item['product_id'] == product_id and item['color'] == color and item['size'] == size), None)

    if product_in_cart:
        product_in_cart['quantity'] += quantity  # Increment quantity if the item is already in the cart
    else:
        session['cart'].append({
            'product_id': product_id,
            'color': color,
            'size': size,
            'quantity': quantity
        })

    session.modified = True  # Ensure session changes are saved
    return redirect(url_for('cart'))  # Redirect to cart page

@app.route('/cart')
def cart():
    cart = session.get('cart', [])  # Retrieve cart from session
    print("Cart:", cart)  # Debug: Check the contents of the cart

    if not cart:  # If the cart is empty
        return render_template("cart.html", products=[], total_price=0, cart=cart)

    # Continue with your logic here to fetch product details
    # Extract product_ids from cart
    product_ids = [item['product_id'] for item in cart]
    print("Product IDs:", product_ids)  # Debug: Check extracted product IDs

    query = text("""
        SELECT p.ProductID, p.Title, p.DiscountedPrice, pi.ImageURL
        FROM Products p
        LEFT JOIN ProductImages pi ON p.ProductID = pi.ProductID
        WHERE p.ProductID IN :product_ids
    """)
    
    try:
        result = conn.execute(query, {"product_ids": tuple(product_ids)})
        products = result.mappings().fetchall()  # Use mappings to return rows as dictionaries
        print("Products Fetched:", products)  # Debug: Check fetched products
    except Exception as e:
        print("Error executing query:", e)
        return "There was an error fetching products"

    # Merge the DiscountedPrice with each cart item
    for item in cart:
        for product in products:
            if item['product_id'] == product['ProductID']:
                item['DiscountedPrice'] = product['DiscountedPrice']
                item['Title'] = product['Title']
                item['ImageURL'] = product['ImageURL']

    # Calculate total price based on cart items
    total_price = 0
    for item in cart:
        if 'DiscountedPrice' in item:
            total_price += item['DiscountedPrice'] * item['quantity']
