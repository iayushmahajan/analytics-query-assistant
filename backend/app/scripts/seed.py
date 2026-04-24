import random
from datetime import date, timedelta
from decimal import Decimal

from faker import Faker
from sqlalchemy import text

from app.core.db import SessionLocal, engine
from app.models import Base, Category, Country, Customer, Order, OrderItem, Product

fake = Faker()


COUNTRIES = [
    {"name": "Germany", "region": "Europe"},
    {"name": "France", "region": "Europe"},
    {"name": "United Kingdom", "region": "Europe"},
    {"name": "United States", "region": "North America"},
    {"name": "Canada", "region": "North America"},
    {"name": "India", "region": "Asia"},
    {"name": "Japan", "region": "Asia"},
    {"name": "Australia", "region": "Oceania"},
]

CATEGORIES = [
    "Electronics",
    "Accessories",
    "Home & Kitchen",
    "Sports",
    "Books",
    "Beauty",
]

PRODUCTS = {
    "Electronics": [
        ("Wireless Headphones", Decimal("129.99")),
        ("Bluetooth Speaker", Decimal("79.99")),
        ("Smart Watch", Decimal("199.99")),
        ("Mechanical Keyboard", Decimal("149.99")),
    ],
    "Accessories": [
        ("Laptop Sleeve", Decimal("29.99")),
        ("USB-C Hub", Decimal("49.99")),
        ("Phone Stand", Decimal("19.99")),
        ("Backpack", Decimal("89.99")),
    ],
    "Home & Kitchen": [
        ("Coffee Grinder", Decimal("59.99")),
        ("Electric Kettle", Decimal("44.99")),
        ("Air Fryer", Decimal("119.99")),
        ("Ceramic Mug Set", Decimal("24.99")),
    ],
    "Sports": [
        ("Yoga Mat", Decimal("34.99")),
        ("Resistance Bands", Decimal("22.99")),
        ("Dumbbell Set", Decimal("89.99")),
        ("Running Bottle", Decimal("18.99")),
    ],
    "Books": [
        ("Data Analytics Basics", Decimal("39.99")),
        ("SQL for Business", Decimal("34.99")),
        ("Python for Data Work", Decimal("44.99")),
        ("E-commerce Growth", Decimal("29.99")),
    ],
    "Beauty": [
        ("Skin Cleanser", Decimal("16.99")),
        ("Vitamin C Serum", Decimal("24.99")),
        ("Moisturizer", Decimal("19.99")),
        ("Sunscreen SPF 50", Decimal("21.99")),
    ],
}

ORDER_STATUSES = ["pending", "completed", "cancelled"]


def reset_database() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def seed_countries(session):
    countries = [Country(**country_data) for country_data in COUNTRIES]
    session.add_all(countries)
    session.commit()
    return countries


def seed_categories_and_products(session):
    category_objects = []
    product_objects = []

    for category_name in CATEGORIES:
        category = Category(name=category_name)
        session.add(category)
        session.flush()
        category_objects.append(category)

        for product_name, price in PRODUCTS[category_name]:
            product = Product(
                name=product_name,
                category_id=category.id,
                price=price,
            )
            session.add(product)
            product_objects.append(product)

    session.commit()
    return category_objects, product_objects


def seed_customers(session, countries):
    customers = []

    for _ in range(40):
        country = random.choice(countries)
        full_name = fake.name()
        email = fake.unique.email()

        customer = Customer(
            full_name=full_name,
            email=email,
            country_id=country.id,
            created_at=fake.date_time_between(start_date="-2y", end_date="now"),
        )
        session.add(customer)
        customers.append(customer)

    session.commit()
    return customers


def build_order_total(items):
    total = Decimal("0.00")
    for item in items:
        line_total = item["unit_price"] * item["quantity"]
        total += line_total
    return total.quantize(Decimal("0.01"))


def seed_orders(session, customers, products):
    orders_created = 0

    for customer in customers:
        order_count = random.randint(1, 6)

        for _ in range(order_count):
            status = random.choices(
                ORDER_STATUSES,
                weights=[15, 75, 10],
                k=1
            )[0]

            order_date = fake.date_between(start_date="-18m", end_date="today")

            selected_products = random.sample(products, k=random.randint(1, 4))
            item_payloads = []

            for product in selected_products:
                quantity = random.randint(1, 5)
                item_payloads.append(
                    {
                        "product": product,
                        "quantity": quantity,
                        "unit_price": Decimal(product.price),
                    }
                )

            total_amount = build_order_total(item_payloads)

            order = Order(
                customer_id=customer.id,
                order_date=order_date,
                status=status,
                total_amount=total_amount,
            )
            session.add(order)
            session.flush()

            for item in item_payloads:
                order_item = OrderItem(
                    order_id=order.id,
                    product_id=item["product"].id,
                    quantity=item["quantity"],
                    unit_price=item["unit_price"],
                )
                session.add(order_item)

            orders_created += 1

    session.commit()
    return orders_created


def print_summary(session):
    tables = [
        "countries",
        "customers",
        "categories",
        "products",
        "orders",
        "order_items",
    ]

    print("\nSeed summary:")
    for table in tables:
        count = session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
        print(f"- {table}: {count}")


def main():
    print("Resetting database and seeding sample data...")
    reset_database()

    session = SessionLocal()

    try:
        countries = seed_countries(session)
        _, products = seed_categories_and_products(session)
        customers = seed_customers(session, countries)
        orders_count = seed_orders(session, customers, products)

        print_summary(session)
        print(f"\nOrders created: {orders_count}")
        print("Seeding completed successfully.")
    finally:
        session.close()


if __name__ == "__main__":
    main()