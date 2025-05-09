        purchase_check = conn.execute(text("""
            SELECT 1 
            FROM Orders o
            JOIN OrderItems oi ON o.OrderID = oi.OrderID
            WHERE o.UserID = :customer_id AND oi.ProductID = :product_id
            LIMIT 1
        """), {
            "customer_id": customer_id,
            "product_id": product_id
        }).fetchone()
