from .core import inr


def _number(n):
    return "{:,}".format(int(round(n)))


def generate(results: list) -> list:
    """Rule-based plain-English insights from computed KPI results. No LLM."""
    by_id = {r["id"]: r for r in results}
    insights = []

    # Biggest spending increase (from category movers)
    cat = by_id.get("category_share")
    if cat and cat.get("extras", {}).get("top_up"):
        m = cat["extras"]["top_up"][0]
        cur = m["current"]
        insights.append(
            "Spending rose the most in {} ({} this month vs {} before).".format(
                m["category"], inr(cur), inr(m["previous"] or 0)))
    elif cat and cat.get("extras", {}).get("top_down"):
        m = cat["extras"]["top_down"][0]
        insights.append(
            "Spending fell most in {} ({} vs {} before).".format(
                m["category"], inr(m["current"]), inr(m["previous"] or 0)))

    # Subscription total
    rec = by_id.get("recurring")
    if rec and rec.get("value"):
        total = rec["value"]
        insights.append(
            "Recurring subscriptions and fixed payments total {} per month.".format(inr(total)))
        hikes = rec["extras"].get("hikes", [])
        if hikes:
            names = ", ".join(h["merchant"] for h in hikes[:2])
            insights.append("Price increases detected on: {}.".format(names))
        new = rec["extras"].get("new", [])
        if new:
            names = ", ".join(n["merchant"] for n in new[:2])
            insights.append("New recurring items in the last 60 days: {}.".format(names))

    # Runway status
    rw = by_id.get("runway")
    if rw and rw.get("value") is not None:
        insights.append(
            "Your funds would last {:.1f} months at current spending (runway).".format(rw["value"]))

    # Savings rate trend
    sr = by_id.get("savings_rate")
    if sr and sr.get("value") is not None:
        trend = sr.get("extras", {}).get("trend", [])
        if len(trend) >= 2 and trend[-1]["rate"] > trend[0]["rate"]:
            insights.append("Your savings rate is improving month over month.")
        elif len(trend) >= 2:
            insights.append("Your savings rate has slipped versus earlier months.")

    # Cash withdrawal flag
    pm = by_id.get("payment_mode")
    if pm and pm.get("extras", {}).get("untracked_flag"):
        insights.append(
            "Cash withdrawals exceeded {}% of spending and may be untracked.".format(
                int(round(pm["extras"]["cash_share"] * 100))))

    # Emergency / DTI flags
    ef = by_id.get("emergency_fund")
    if ef and ef.get("status") == "bad":
        insights.append("Your emergency fund covers less than 3 months of essential spending.")
    dti = by_id.get("debt_to_income")
    if dti and dti.get("status") == "bad":
        insights.append("Debt payments are high relative to your income.")

    return insights[:5]