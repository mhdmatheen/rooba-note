import re

CATEGORY_TRANSFER = "Transfer"
CATEGORY_OTHER = "Other"
CATEGORY_UNCATEGORIZED = "Uncategorized"
DEFAULT_CATEGORY = CATEGORY_UNCATEGORIZED

# Categories surfaced to the user. Transfers are excluded from analytics but are
# kept as a category so the user can see and override the internal-transfer flag.
CATEGORIES = [
    CATEGORY_TRANSFER,
    "Food",
    "Rent",
    "Utilities",
    "Shopping",
    "Travel",
    "EMI",
    "Subscriptions",
    "Cash Withdrawal",
    "Fees",
    CATEGORY_OTHER,
    CATEGORY_UNCATEGORIZED,
]

# Ordered rules: first match wins. More specific categories come first.
CATEGORY_RULES = [
    ("EMI", ["emi", "loan instal", "loan installment", "home loan", "personal loan", "car loan", "bajaj finserv", "hdb financial", "loan"]),
    ("Cash Withdrawal", ["nwd", "atm", "cash withdrawal", "ccwd", "cash wdl"]),
    ("Subscriptions", ["netflix", "prime video", "amazon prime", "hotstar", "spotify", "youtube premium", "google play", "playstation", "apple media", "sonyliv", "zee5", "subscription"]),
    ("Utilities", ["electricity", "power bill", "water bill", "gas bill", "broadband", "internet", "billpay", "bill pay", "recharge", "airtel", "jio", "vodafone", "bsnl", "bbps", "dth", "utility"]),
    ("Rent", ["house rent", "rent", "rental", "landlord"]),
    ("Food", ["restaurant", "hotel", "cafe", "coffee", "swiggy", "zomato", "dominos", "kfc", "mcdonald", "burger", "pizza", "bakery", "food", "tea stall", "bhavan", "dhaba", "juice", "supermarket", "grocery", "grofers", "big basket", "bigbasket", "dmart", "d-mart", "blinkit", "zepto", "instamart", "reliance fresh", "spencer", "provision"]),
    ("Travel", ["uber", "ola", "rapido", "irctc", "metro", "fuel", "petrol", "diesel", "redbus", "parking", "fastag", "toll", "cab", "auto", "airline", "goibibo", "makemytrip", "hotel booking", "oyo", "air ind", "indigo", "flight", "bus ticket"]),
    ("Shopping", ["amazon", "flipkart", "myntra", "ajio", "meesho", "snapdeal", "jewellery", "jewel", "lifestyle", "westside", "pantaloons", "decathlon", "online shopping", "shopping"]),
    ("Fees", ["bank charges", "service charge", "annual fee", "transaction fee", "penalty", "gst charge", "convenience fee", "late fee", "fee", "fees"]),
    # Known but not one of the named buckets.
    ("Other", ["pharmacy", "medical", "hospital", "clinic", "lab", "diagnostic", "apollo", "medplus", "netmeds", "1mg", "doctor", "dental", "salon", "spa", "parlour", "parlor", "barber", "beauty", "school", "college", "university", "tuition", "course", "udemy", "coursera", "insurance", "lic", "premium", "policybazaar", "mutual", "sip", "zerodha", "groww", "demat", "shares", "stocks", "smallcase", "etmoney", "income tax", "gst-pay", "tds", "advance tax", "tax payment", "salary", "interest paid", "int.pd", "interest credit"]),
]

_COMPILED_RULES = [
    (category, [re.compile(rf"(?<![a-z0-9]){re.escape(kw)}(?![a-z0-9])") for kw in keywords])
    for category, keywords in CATEGORY_RULES
]

# Kept last so merchant names containing weak transfer words still get a real
# category when a stronger rule matched first.
TRANSFER_KEYWORDS = [
    "transfer",
    "neft",
    "imps",
    "rtgs",
    "fund transfer",
    "inft",
    "internal fund",
]


def _text(remarks: str) -> str:
    return " " + str(remarks or "").lower().strip() + " "


def categorize(remarks: str) -> str:
    text = _text(remarks)
    for category, patterns in _COMPILED_RULES:
        for pattern in patterns:
            if pattern.search(text):
                return category
    if is_transfer_text(remarks):
        return CATEGORY_TRANSFER
    return DEFAULT_CATEGORY


def is_transfer_text(remarks: str) -> bool:
    """Keyword-only heuristic for money moved between the user's own accounts."""
    text = _text(remarks)
    strong = [
        "credit card payment",
        "cc bill",
        "cc payment",
        "card payment",
        "self transfer",
        "transfer to self",
        "own account",
        "to self",
        "from self",
    ]
    if any(k in text for k in strong):
        return True
    if "self" in text:
        return True
    return any(k in text for k in TRANSFER_KEYWORDS)
