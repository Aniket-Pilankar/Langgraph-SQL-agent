"""Table cards and question-to-SQL exemplars embedded into schema_memory."""

TABLE_CARDS = [
    {
        "table": "customers",
        "content": (
            "Table: customers — who placed each order and where they live.\n"
            "Columns: customer_id (join key to orders.customer_id), "
            "customer_unique_id (identifies the real person across multiple orders), "
            "zip_code, city, state (2-letter Brazilian state code, e.g. 'SP','RJ','MG').\n"
            "Use for: customers, buyers, locations, states, cities, geography, "
            "where customers are located."
        ),
    },
    {
        "table": "orders",
        "content": (
            "Table: orders — each purchase and its status and delivery dates.\n"
            "Columns: order_id, customer_id (-> customers), status "
            "(delivered, shipped, canceled, processing, ...), "
            "purchase_timestamp (when placed), approved_at, "
            "delivered_at (when received, NULL if not delivered), "
            "estimated_delivery (promised date).\n"
            "Use for: order counts, order status, deliveries, late/on-time delivery, "
            "delivery delays, cancellations, trends over time by purchase date."
        ),
    },
    {
        "table": "order_items",
        "content": (
            "Table: order_items — the product lines inside orders, with prices.\n"
            "Columns: order_id (-> orders), order_item_id, product_id (-> products), "
            "seller_id (-> sellers), shipping_limit_date, price (item price in BRL), "
            "freight_value (shipping cost in BRL).\n"
            "Use for: revenue, sales, prices, how much was sold, items per order. "
            "CONVENTION: revenue = SUM(order_items.price). Join to products via "
            "product_id and to sellers via seller_id."
        ),
    },
    {
        "table": "products",
        "content": (
            "Table: products — the catalog of products and their category.\n"
            "Columns: product_id, category_name (English category, e.g. "
            "'health_beauty','bed_bath_table','sports_leisure'), name_length, "
            "description_length, photos_qty, weight_g.\n"
            "Use for: product categories, catalog size, number of products, "
            "product weight, category-level analysis. Prices live in order_items, "
            "so join via order_items.product_id for revenue per category."
        ),
    },
    {
        "table": "sellers",
        "content": (
            "Table: sellers — the merchants that fulfil orders, and where they are.\n"
            "Columns: seller_id, zip_code, city, state.\n"
            "Use for: sellers, merchants, seller location/state/city, which sellers "
            "sell the most (join via order_items.seller_id)."
        ),
    },
    {
        "table": "payments",
        "content": (
            "Table: payments — how orders were paid (one order can have several rows).\n"
            "Columns: order_id (-> orders), payment_sequential, payment_type "
            "(credit_card, boleto, voucher, debit_card), installments, payment_value.\n"
            "Use for: payment methods, payment type breakdown, installments, "
            "amount paid, payment value."
        ),
    },
    {
        "table": "reviews",
        "content": (
            "Table: reviews — customer satisfaction reviews.\n"
            "Columns: review_id, order_id (-> orders), review_score (1 to 5), "
            "comment_title, comment_message (free-text comment), review_creation_date.\n"
            "Use for: ratings, review scores, star ratings, satisfaction, "
            "customer feedback and comments."
        ),
    },
]


EXEMPLARS = [
    {
        "question": "What is the total revenue?",
        "sql": "SELECT ROUND(SUM(price), 2) AS revenue FROM order_items;",
    },
    {
        "question": "Total revenue by product category",
        "sql": (
            "SELECT p.category_name, ROUND(SUM(oi.price), 2) AS revenue\n"
            "FROM order_items oi JOIN products p USING (product_id)\n"
            "GROUP BY p.category_name ORDER BY revenue DESC LIMIT 10;"
        ),
    },
    {
        "question": "How many orders were placed each month in 2017?",
        "sql": (
            "SELECT DATE_TRUNC('month', purchase_timestamp) AS month, COUNT(*) AS orders\n"
            "FROM orders WHERE EXTRACT(YEAR FROM purchase_timestamp) = 2017\n"
            "GROUP BY 1 ORDER BY 1;"
        ),
    },
    {
        "question": "Top 5 states by number of customers",
        "sql": (
            "SELECT state, COUNT(*) AS customers FROM customers\n"
            "GROUP BY state ORDER BY customers DESC LIMIT 5;"
        ),
    },
    {
        "question": "Average delivery time in days by customer state",
        "sql": (
            "SELECT c.state,\n"
            "       ROUND(AVG(EXTRACT(EPOCH FROM (o.delivered_at - o.purchase_timestamp))/86400)::numeric, 2) AS avg_days\n"
            "FROM orders o JOIN customers c USING (customer_id)\n"
            "WHERE o.delivered_at IS NOT NULL\n"
            "GROUP BY c.state ORDER BY avg_days;"
        ),
    },
    {
        "question": "Payment type breakdown",
        "sql": (
            "SELECT payment_type, COUNT(*) AS count, ROUND(SUM(payment_value), 2) AS total\n"
            "FROM payments GROUP BY payment_type ORDER BY total DESC;"
        ),
    },
    {
        "question": "Average review score by product category",
        "sql": (
            "SELECT p.category_name, ROUND(AVG(r.review_score)::numeric, 2) AS avg_score, COUNT(*) AS reviews\n"
            "FROM reviews r JOIN order_items oi USING (order_id) JOIN products p USING (product_id)\n"
            "GROUP BY p.category_name ORDER BY avg_score DESC LIMIT 15;"
        ),
    },
    {
        "question": "How many orders were delivered later than estimated?",
        "sql": (
            "SELECT COUNT(*) AS late_orders FROM orders\n"
            "WHERE delivered_at IS NOT NULL AND delivered_at > estimated_delivery;"
        ),
    },
    {
        "question": "How many orders are there in total?",
        "sql": "SELECT COUNT(*) AS total_orders FROM orders;",
    },
    {
        "question": "Which sellers generate the most revenue?",
        "sql": (
            "SELECT seller_id, ROUND(SUM(price), 2) AS revenue\n"
            "FROM order_items GROUP BY seller_id ORDER BY revenue DESC LIMIT 10;"
        ),
    },
]
