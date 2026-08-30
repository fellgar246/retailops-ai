"""Deterministic catalog: categories, products, suppliers, terms and stores."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from random import Random

from retailops_api.dataset.contract import (
    Catalog,
    CategoryRow,
    ProductRow,
    StoreRow,
    SupplierProductRow,
    SupplierRow,
    quantize_money,
)
from retailops_api.synthetic.config import GeneratorConfig

# Department → (name, children). Children are the leaves products hang off.
_DEPARTMENTS: tuple[tuple[str, str, tuple[tuple[str, str], ...]], ...] = (
    (
        "BEV",
        "Beverages",
        (
            ("BEV-SOFT", "Soft Drinks"),
            ("BEV-WATER", "Water"),
            ("BEV-COFFEE", "Coffee & Tea"),
            ("BEV-JUICE", "Juices"),
        ),
    ),
    (
        "SNACK",
        "Snacks",
        (
            ("SNACK-CHIPS", "Chips & Crisps"),
            ("SNACK-CANDY", "Candy & Chocolate"),
            ("SNACK-NUTS", "Nuts & Seeds"),
        ),
    ),
    (
        "HOME",
        "Household",
        (
            ("HOME-CLEAN", "Cleaning Supplies"),
            ("HOME-PAPER", "Paper Goods"),
            ("HOME-KITCHEN", "Kitchen Basics"),
        ),
    ),
    (
        "DAIRY",
        "Dairy",
        (
            ("DAIRY-MILK", "Milk"),
            ("DAIRY-YOG", "Yogurt"),
            ("DAIRY-CHEESE", "Cheese"),
        ),
    ),
    (
        "BAKERY",
        "Bakery",
        (
            ("BAKERY-BREAD", "Bread"),
            ("BAKERY-SWEET", "Pastry"),
        ),
    ),
    (
        "PERSONAL",
        "Personal Care",
        (
            ("PERSONAL-SOAP", "Soap & Body"),
            ("PERSONAL-ORAL", "Oral Care"),
        ),
    ),
    (
        "FROZEN",
        "Frozen",
        (
            ("FROZEN-MEAL", "Frozen Meals"),
            ("FROZEN-ICE", "Ice Cream"),
        ),
    ),
    (
        "GROCERY",
        "Grocery",
        (
            ("GROCERY-CAN", "Canned Goods"),
            ("GROCERY-PASTA", "Pasta & Grains"),
            ("GROCERY-BREAK", "Breakfast"),
        ),
    ),
)

_PRODUCT_TEMPLATES: dict[str, tuple[str, ...]] = {
    "BEV-SOFT": (
        "Cola Classic 355ml Can",
        "Cola Zero 355ml Can",
        "Orange Soda 600ml Bottle",
        "Lemon-Lime Soda 600ml Bottle",
        "Ginger Ale 355ml Can",
    ),
    "BEV-WATER": (
        "Still Water 1L Bottle",
        "Sparkling Water 500ml Bottle",
        "Still Water 500ml Bottle",
        "Mineral Water 1.5L Bottle",
    ),
    "BEV-COFFEE": (
        "Ground Coffee 500g",
        "Loose Leaf Green Tea 100g",
        "Instant Coffee 200g",
        "Black Tea Bags 25-Pack",
    ),
    "BEV-JUICE": (
        "Orange Juice 1L",
        "Apple Juice 1L",
        "Mango Nectar 500ml",
    ),
    "SNACK-CHIPS": (
        "Salted Potato Chips 150g",
        "Spicy Tortilla Chips 180g",
        "Sour Cream Chips 150g",
        "Plantain Chips 120g",
    ),
    "SNACK-CANDY": (
        "Milk Chocolate Bar 100g",
        "Fruit Gummies 90g",
        "Dark Chocolate Bar 80g",
        "Mint Hard Candy 120g",
    ),
    "SNACK-NUTS": (
        "Salted Peanuts 200g",
        "Mixed Nuts 150g",
        "Roasted Almonds 120g",
    ),
    "HOME-CLEAN": (
        "Multi-Surface Cleaner 750ml",
        "Dishwashing Liquid 500ml",
        "Laundry Detergent 1L",
        "All-Purpose Bleach 1L",
    ),
    "HOME-PAPER": (
        "Paper Towels 2-Pack",
        "Toilet Paper 4-Pack",
        "Facial Tissues 3-Pack",
    ),
    "HOME-KITCHEN": (
        "Aluminium Foil 10m",
        "Garbage Bags 20-Pack",
        "Cling Film 30m",
    ),
    "DAIRY-MILK": (
        "Whole Milk 1L",
        "Low-Fat Milk 1L",
        "Lactose-Free Milk 1L",
    ),
    "DAIRY-YOG": (
        "Natural Yogurt 1kg",
        "Strawberry Yogurt 4-Pack",
        "Greek Yogurt 500g",
    ),
    "DAIRY-CHEESE": (
        "Panela Cheese 400g",
        "Manchego Slice 250g",
        "Cream Cheese 200g",
    ),
    "BAKERY-BREAD": (
        "White Loaf 680g",
        "Whole Wheat Loaf 680g",
        "Bolillo 6-Pack",
    ),
    "BAKERY-SWEET": (
        "Conchas 4-Pack",
        "Butter Cookies 200g",
        "Pound Cake 350g",
    ),
    "PERSONAL-SOAP": (
        "Bar Soap 3-Pack",
        "Body Wash 400ml",
        "Hand Soap 250ml",
    ),
    "PERSONAL-ORAL": (
        "Toothpaste 100ml",
        "Toothbrush 2-Pack",
        "Mouthwash 500ml",
    ),
    "FROZEN-MEAL": (
        "Frozen Enchiladas 400g",
        "Vegetable Mix 500g",
        "Frozen Pizza 350g",
    ),
    "FROZEN-ICE": (
        "Vanilla Ice Cream 1L",
        "Chocolate Ice Cream 1L",
        "Fruit Paletas 6-Pack",
    ),
    "GROCERY-CAN": (
        "Canned Tuna 140g",
        "Black Beans 400g",
        "Crushed Tomatoes 400g",
    ),
    "GROCERY-PASTA": (
        "Spaghetti 500g",
        "White Rice 1kg",
        "Corn Tortillas 500g",
    ),
    "GROCERY-BREAK": (
        "Corn Flakes 500g",
        "Oat Flakes 400g",
        "Granola 350g",
    ),
}

_GENERIC_TEMPLATES = (
    "House Brand Item 250g",
    "House Brand Item 500g",
    "House Brand Item 1kg",
)

_SUPPLIER_NAMES = (
    "BevCo Distribution",
    "Snackworks Wholesale",
    "HomeSupply Partners",
    "National Grocery Group",
    "Lácteos del Valle",
    "Panadería Central",
    "Cuidado Diario SA",
    "Frío Express",
    "Abarrotes Unidos",
    "Costa Pacífico Foods",
    "Altiplano Trading",
    "Sierra Norte Supply",
)

_STORE_TEMPLATES: tuple[tuple[str, str, str, str], ...] = (
    ("ST-001", "Centro Flagship", "Central", "flagship"),
    ("ST-002", "Norte Supermarket", "North", "supermarket"),
    ("ST-003", "Sur Supermarket", "South", "supermarket"),
    ("ST-004", "Poniente Express", "West", "express"),
    ("ST-005", "Oriente Express", "East", "express"),
    ("ST-006", "Bajío Supermarket", "Bajio", "supermarket"),
    ("ST-007", "Sureste Supermarket", "Southeast", "supermarket"),
    ("ST-008", "Centro Express", "Central", "express"),
    ("ST-009", "Norte Express", "North", "express"),
    ("ST-010", "Sur Flagship", "South", "flagship"),
)

_REGIONS = ("Central", "North", "South", "West", "East", "Bajio", "Southeast")
_STORE_TYPES = ("flagship", "supermarket", "express")
_STORE_TYPE_EFFECT = {"flagship": 1.35, "supermarket": 1.00, "express": 0.70}

_CASE_PACKS = (6, 8, 12, 18, 24)

# Typical unit-cost bands by leaf category, used to keep prices plausible.
_COST_BANDS: dict[str, tuple[Decimal, Decimal]] = {
    "BEV-SOFT": (Decimal("6.50"), Decimal("11.00")),
    "BEV-WATER": (Decimal("4.50"), Decimal("8.00")),
    "BEV-COFFEE": (Decimal("28.00"), Decimal("55.00")),
    "BEV-JUICE": (Decimal("12.00"), Decimal("22.00")),
    "SNACK-CHIPS": (Decimal("10.00"), Decimal("16.00")),
    "SNACK-CANDY": (Decimal("8.00"), Decimal("18.00")),
    "SNACK-NUTS": (Decimal("14.00"), Decimal("28.00")),
    "HOME-CLEAN": (Decimal("16.00"), Decimal("32.00")),
    "HOME-PAPER": (Decimal("22.00"), Decimal("36.00")),
    "HOME-KITCHEN": (Decimal("18.00"), Decimal("30.00")),
    "DAIRY-MILK": (Decimal("14.00"), Decimal("20.00")),
    "DAIRY-YOG": (Decimal("12.00"), Decimal("24.00")),
    "DAIRY-CHEESE": (Decimal("28.00"), Decimal("48.00")),
    "BAKERY-BREAD": (Decimal("18.00"), Decimal("28.00")),
    "BAKERY-SWEET": (Decimal("14.00"), Decimal("26.00")),
    "PERSONAL-SOAP": (Decimal("16.00"), Decimal("30.00")),
    "PERSONAL-ORAL": (Decimal("18.00"), Decimal("34.00")),
    "FROZEN-MEAL": (Decimal("24.00"), Decimal("42.00")),
    "FROZEN-ICE": (Decimal("20.00"), Decimal("38.00")),
    "GROCERY-CAN": (Decimal("8.00"), Decimal("16.00")),
    "GROCERY-PASTA": (Decimal("10.00"), Decimal("22.00")),
    "GROCERY-BREAK": (Decimal("22.00"), Decimal("40.00")),
}
_DEFAULT_COST_BAND = (Decimal("10.00"), Decimal("25.00"))


@dataclass
class CatalogArtifacts:
    """Generated catalog plus the latent factors demand generation needs."""

    catalog: Catalog
    list_price: dict[str, Decimal]
    popularity: dict[str, float]
    category_effect: dict[str, float]
    store_effect: dict[str, float]
    case_pack: dict[str, int]


def generate_catalog(config: GeneratorConfig) -> CatalogArtifacts:
    """Build a catalog that is fully determined by ``config.catalog_seed``."""
    rng = Random(config.catalog_seed)
    categories = _categories(config.category_count)
    stores = _stores(config.store_count)
    suppliers = _suppliers(config.supplier_count)
    leaves = _leaf_categories(categories)
    products = _products(config.product_count, leaves)
    terms, list_price, case_pack = _supplier_terms(rng, products, suppliers)

    popularity = _popularity(rng, [product.sku for product in products])
    category_effect = {category.code: rng.uniform(0.75, 1.25) for category in categories}
    store_effect = {
        store.code: _STORE_TYPE_EFFECT.get(store.store_type, 1.0) * rng.uniform(0.85, 1.15)
        for store in stores
    }

    return CatalogArtifacts(
        catalog=Catalog(
            categories=tuple(categories),
            products=tuple(products),
            suppliers=tuple(suppliers),
            supplier_products=tuple(terms),
            stores=tuple(stores),
        ),
        list_price=list_price,
        popularity=popularity,
        category_effect=category_effect,
        store_effect=store_effect,
        case_pack=case_pack,
    )


def _categories(count: int) -> list[CategoryRow]:
    selected: list[CategoryRow] = []
    for root_code, root_name, children in _DEPARTMENTS:
        if len(selected) >= count:
            break
        selected.append(CategoryRow(root_code, root_name))
        for child_code, child_name in children:
            if len(selected) >= count:
                break
            selected.append(CategoryRow(child_code, child_name, root_code))

    extra = 1
    while len(selected) < count:
        # Keep leftover nodes as extra leaves under the last root so the
        # parent always exists and the identifier shape still holds.
        root = next(row for row in reversed(selected) if row.parent_code is None)
        selected.append(
            CategoryRow(f"{root.code}-X{extra:02d}", f"{root.name} Extra {extra}", root.code)
        )
        extra += 1
    return selected


def _leaf_categories(categories: list[CategoryRow]) -> list[CategoryRow]:
    parent_codes = {row.parent_code for row in categories if row.parent_code}
    leaves = [row for row in categories if row.code not in parent_codes]
    return leaves or list(categories)


def _stores(count: int) -> list[StoreRow]:
    stores = [
        StoreRow(code, name, region, store_type)
        for code, name, region, store_type in _STORE_TEMPLATES[:count]
    ]
    next_number = len(stores) + 1
    while len(stores) < count:
        region = _REGIONS[(next_number - 1) % len(_REGIONS)]
        store_type = _STORE_TYPES[(next_number - 1) % len(_STORE_TYPES)]
        stores.append(
            StoreRow(
                code=f"ST-{next_number:03d}",
                name=f"{region} {store_type.title()} {next_number:02d}",
                region=region,
                store_type=store_type,
            )
        )
        next_number += 1
    return stores


def _suppliers(count: int) -> list[SupplierRow]:
    suppliers: list[SupplierRow] = []
    for index in range(count):
        name = (
            _SUPPLIER_NAMES[index]
            if index < len(_SUPPLIER_NAMES)
            else f"Regional Supplier {index + 1:02d}"
        )
        tax_id = None if index % 4 == 3 else f"SYN{index + 1:06d}{chr(ord('A') + index % 26)}"
        suppliers.append(SupplierRow(code=f"SUP-{index + 1:03d}", name=name, tax_id=tax_id))
    return suppliers


def _products(count: int, leaves: list[CategoryRow]) -> list[ProductRow]:
    products: list[ProductRow] = []
    used_names: dict[str, int] = {}
    for index in range(count):
        category = leaves[index % len(leaves)]
        templates = _PRODUCT_TEMPLATES.get(category.code, _GENERIC_TEMPLATES)
        slot = index // len(leaves)
        if slot < len(templates):
            name = templates[slot]
        else:
            name = f"{templates[slot % len(templates)]} Pack {slot // len(templates) + 1}"
        seen = used_names.get(name, 0)
        if seen:
            name = f"{name} ({seen + 1})"
        used_names[name] = seen + 1

        sku = f"SKU-{index + 1:04d}"
        ean = None if index % 7 == 6 else _ean13(index + 1)
        products.append(
            ProductRow(
                sku=sku,
                name=name,
                category_code=category.code,
                ean=ean,
                description=f"{name} in {category.name}.",
            )
        )
    return products


def _supplier_terms(
    rng: Random,
    products: list[ProductRow],
    suppliers: list[SupplierRow],
) -> tuple[list[SupplierProductRow], dict[str, Decimal], dict[str, int]]:
    terms: list[SupplierProductRow] = []
    list_price: dict[str, Decimal] = {}
    case_pack: dict[str, int] = {}

    for index, product in enumerate(products):
        primary = suppliers[index % len(suppliers)]
        pack = rng.choice(_CASE_PACKS)
        cost = _cost(rng, product.category_code)
        markup = Decimal(str(round(rng.uniform(1.40, 2.20), 4)))
        list_price[product.sku] = quantize_money(cost * markup)
        case_pack[product.sku] = pack
        terms.append(
            _term(
                primary,
                product,
                cost=cost,
                case_pack=pack,
                minimum_order_quantity=rng.choice((1, 1, 2)),
                lead_time_days=rng.randint(2, 10),
            )
        )

    if len(suppliers) > 1:
        dual_count = max(1, len(products) // 4)
        for product in products[:dual_count]:
            primary_code = next(
                row.supplier_code for row in terms if row.product_sku == product.sku
            )
            primary_index = next(
                i for i, supplier in enumerate(suppliers) if supplier.code == primary_code
            )
            secondary = suppliers[(primary_index + 1) % len(suppliers)]
            primary_cost = next(
                row.cost
                for row in terms
                if row.product_sku == product.sku and row.supplier_code == primary_code
            )
            terms.append(
                _term(
                    secondary,
                    product,
                    cost=quantize_money(primary_cost * Decimal("1.08")),
                    case_pack=rng.choice(_CASE_PACKS),
                    minimum_order_quantity=1,
                    lead_time_days=rng.randint(8, 14),
                )
            )

    return terms, list_price, case_pack


def _term(
    supplier: SupplierRow,
    product: ProductRow,
    *,
    cost: Decimal,
    case_pack: int,
    minimum_order_quantity: int,
    lead_time_days: int,
) -> SupplierProductRow:
    return SupplierProductRow(
        supplier_code=supplier.code,
        product_sku=product.sku,
        cost=quantize_money(cost),
        case_pack=case_pack,
        minimum_order_quantity=minimum_order_quantity,
        lead_time_days=lead_time_days,
        supplier_sku=f"{supplier.code}-{product.sku[-4:]}",
    )


def _cost(rng: Random, category_code: str) -> Decimal:
    low, high = _COST_BANDS.get(category_code, _DEFAULT_COST_BAND)
    span = high - low
    draw = low + span * Decimal(str(round(rng.random(), 6)))
    return quantize_money(draw)


def _popularity(rng: Random, skus: list[str]) -> dict[str, float]:
    """Zipf-like popularity so a few SKUs dominate without making demand a constant."""
    ranked = list(skus)
    rng.shuffle(ranked)
    raw = {sku: (rank + 1) ** -0.75 for rank, sku in enumerate(ranked)}
    mean = sum(raw.values()) / len(raw)
    return {sku: value / mean for sku, value in raw.items()}


def _ean13(number: int) -> str:
    body = f"750{number:09d}"[:12]
    digits = [int(char) for char in body]
    checksum = (10 - (sum(digits[0::2]) + 3 * sum(digits[1::2])) % 10) % 10
    return f"{body}{checksum}"
