-- Role used by the run_sql tool: SELECT on Olist tables only, read-only, 5s timeout.

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'agent_readonly') THEN
        CREATE ROLE agent_readonly LOGIN PASSWORD 'agent_readonly'
            NOSUPERUSER NOCREATEDB NOCREATEROLE;
    END IF;
END
$$;

GRANT CONNECT ON DATABASE chatdata TO agent_readonly;
GRANT USAGE ON SCHEMA public TO agent_readonly;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM agent_readonly;

GRANT SELECT ON customers, orders, order_items, products, sellers, payments, reviews
    TO agent_readonly;

ALTER ROLE agent_readonly SET default_transaction_read_only = on;
ALTER ROLE agent_readonly SET statement_timeout = '5s';
