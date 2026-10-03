-- Apply after migrations as the table owner (analytics_app).
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM analytics_reader;
GRANT SELECT ON countries, categories, products, orders, order_items TO analytics_reader;
-- Names/emails are unnecessary for this aggregated sales workspace.
GRANT SELECT (id, country_id, created_at) ON customers TO analytics_reader;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM analytics_reader;
