"""Create app tables, load the Olist CSVs, create the read-only role and seed schema memory.

Usage (from backend/):  uv run python -m db.setup
"""

import math
import os
import sys
from pathlib import Path

import pandas as pd
import psycopg
from dotenv import load_dotenv

load_dotenv()

from langchain_openai import OpenAIEmbeddings  # noqa: E402

from agent.memory_content import EXEMPLARS, TABLE_CARDS  # noqa: E402

DB_DIR = Path(__file__).parent
DATA_DIR = Path(__file__).parents[2] / "data"


def sql_file(name: str) -> str:
    return (DB_DIR / name).read_text(encoding="utf-8")


def _convert(value, kind):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if kind == "str":
        return str(value)
    if kind == "int":
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None
    if kind == "num":
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    if kind == "ts":
        ts = pd.to_datetime(value, errors="coerce")
        return None if pd.isna(ts) else ts.to_pydatetime()
    return value


# table -> (csv file, [(db column, csv column, kind)])
TABLE_SPECS = {
    "customers": ("olist_customers_dataset.csv", [
        ("customer_id", "customer_id", "str"),
        ("customer_unique_id", "customer_unique_id", "str"),
        ("zip_code", "customer_zip_code_prefix", "str"),
        ("city", "customer_city", "str"),
        ("state", "customer_state", "str"),
    ]),
    "orders": ("olist_orders_dataset.csv", [
        ("order_id", "order_id", "str"),
        ("customer_id", "customer_id", "str"),
        ("status", "order_status", "str"),
        ("purchase_timestamp", "order_purchase_timestamp", "ts"),
        ("approved_at", "order_approved_at", "ts"),
        ("delivered_at", "order_delivered_customer_date", "ts"),
        ("estimated_delivery", "order_estimated_delivery_date", "ts"),
    ]),
    "order_items": ("olist_order_items_dataset.csv", [
        ("order_id", "order_id", "str"),
        ("order_item_id", "order_item_id", "int"),
        ("product_id", "product_id", "str"),
        ("seller_id", "seller_id", "str"),
        ("shipping_limit_date", "shipping_limit_date", "ts"),
        ("price", "price", "num"),
        ("freight_value", "freight_value", "num"),
    ]),
    "sellers": ("olist_sellers_dataset.csv", [
        ("seller_id", "seller_id", "str"),
        ("zip_code", "seller_zip_code_prefix", "str"),
        ("city", "seller_city", "str"),
        ("state", "seller_state", "str"),
    ]),
    "payments": ("olist_order_payments_dataset.csv", [
        ("order_id", "order_id", "str"),
        ("payment_sequential", "payment_sequential", "int"),
        ("payment_type", "payment_type", "str"),
        ("installments", "payment_installments", "int"),
        ("payment_value", "payment_value", "num"),
    ]),
    "reviews": ("olist_order_reviews_dataset.csv", [
        ("review_id", "review_id", "str"),
        ("order_id", "order_id", "str"),
        ("review_score", "review_score", "int"),
        ("comment_title", "review_comment_title", "str"),
        ("comment_message", "review_comment_message", "str"),
        ("review_creation_date", "review_creation_date", "ts"),
    ]),
    "products": (None, [
        ("product_id", "product_id", "str"),
        ("category_name", "category_final", "str"),
        ("name_length", "product_name_lenght", "int"),  # sic: source column name
        ("description_length", "product_description_lenght", "int"),
        ("photos_qty", "product_photos_qty", "int"),
        ("weight_g", "product_weight_g", "num"),
    ]),
}


def _products_frame() -> pd.DataFrame:
    prod = pd.read_csv(DATA_DIR / "olist_products_dataset.csv")
    trans = pd.read_csv(DATA_DIR / "product_category_name_translation.csv", encoding="utf-8-sig")
    prod = prod.merge(trans, on="product_category_name", how="left")
    prod["category_final"] = prod["product_category_name_english"].fillna(prod["product_category_name"])
    return prod


def load_olist(conn: psycopg.Connection) -> None:
    conn.execute(sql_file("olist_schema.sql"))
    for table, (csv_name, cols) in TABLE_SPECS.items():
        df = _products_frame() if table == "products" else pd.read_csv(DATA_DIR / csv_name)
        kinds = [c[2] for c in cols]
        col_list = ", ".join(c[0] for c in cols)
        n = 0
        with conn.cursor() as cur:
            with cur.copy(f"COPY {table} ({col_list}) FROM STDIN") as copy:
                for row in df[[c[1] for c in cols]].itertuples(index=False, name=None):
                    copy.write_row([_convert(v, kinds[i]) for i, v in enumerate(row)])
                    n += 1
        print(f"  {table:<12} {n:>8,} rows")


def _vec(embedding: list[float]) -> str:
    return "[" + ",".join(map(str, embedding)) + "]"


def seed_memory(conn: psycopg.Connection) -> None:
    emb = OpenAIEmbeddings(model="text-embedding-3-small", dimensions=512)
    conn.execute("TRUNCATE schema_memory")

    card_vecs = emb.embed_documents([c["content"] for c in TABLE_CARDS])
    for card, v in zip(TABLE_CARDS, card_vecs):
        conn.execute(
            "INSERT INTO schema_memory (kind, table_name, content, embedding) VALUES ('card', %s, %s, %s::vector)",
            (card["table"], card["content"], _vec(v)),
        )

    # Exemplars are embedded by question so they match similar user questions.
    ex_vecs = emb.embed_documents([e["question"] for e in EXEMPLARS])
    for ex, v in zip(EXEMPLARS, ex_vecs):
        conn.execute(
            "INSERT INTO schema_memory (kind, content, embedding) VALUES ('exemplar', %s, %s::vector)",
            (f"-- Q: {ex['question']}\n{ex['sql']}", _vec(v)),
        )
    print(f"  {len(TABLE_CARDS)} cards, {len(EXEMPLARS)} exemplars")


def main() -> None:
    if not any(DATA_DIR.glob("*.csv")):
        sys.exit(f"No CSV files found in {DATA_DIR}")

    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as conn:
        print("Creating app tables")
        conn.execute(sql_file("app_schema.sql"))
        print("Loading Olist data")
        load_olist(conn)
        print("Creating read-only role")
        conn.execute(sql_file("readonly_role.sql"))
        print("Seeding schema memory")
        seed_memory(conn)
    print("Done")


if __name__ == "__main__":
    main()
