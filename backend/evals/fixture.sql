TRUNCATE query_history, order_items, orders, products, customers, categories, countries RESTART IDENTITY CASCADE;
INSERT INTO countries VALUES (1,'Germany','Europe'),(2,'France','Europe');
INSERT INTO categories VALUES (1,'Electronics'),(2,'Books');
INSERT INTO customers VALUES (1,'Synthetic A','a@example.invalid',1,'2024-01-01'),(2,'Synthetic B','b@example.invalid',2,'2024-01-01'),(3,'Synthetic C','c@example.invalid',1,'2024-02-01');
INSERT INTO products VALUES (1,'Keyboard',1,50),(2,'Book',2,20);
INSERT INTO orders VALUES (1,1,'2025-01-10','completed',100),(2,2,'2025-02-10','completed',200),(3,1,'2025-02-15','pending',60),(4,2,'2025-03-01','cancelled',40),(5,3,'2025-03-10','completed',60),(6,1,'2024-12-01','completed',40);
INSERT INTO order_items VALUES (1,1,1,2,50),(2,2,1,4,50),(3,3,2,3,20),(4,4,2,2,20),(5,5,2,3,20),(6,6,2,2,20);
