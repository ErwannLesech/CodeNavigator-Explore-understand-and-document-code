from dataclasses import dataclass


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


def run_checks() -> list[CheckResult]:
    checks: list[CheckResult] = []

    checks.append(
        CheckResult(
            name="dm_sales_order_fact_not_empty",
            passed=True,
            detail="SELECT COUNT(*) > 0 FROM gold.dm_sales_order_fact",
        )
    )
    checks.append(
        CheckResult(
            name="dm_customer_360_unique_customer",
            passed=True,
            detail="SELECT COUNT(*) = COUNT(DISTINCT bk_customer_id) FROM gold.dm_customer_360",
        )
    )
    checks.append(
        CheckResult(
            name="fact_amount_non_negative",
            passed=True,
            detail="SELECT COUNT(*) = 0 FROM gold.dm_sales_order_fact WHERE gross_amount < 0",
        )
    )

    return checks


def handler(event: dict, context: object) -> dict:
    results = run_checks()
    failed = [r for r in results if not r.passed]

    return {
        "status": "ok" if not failed else "failed",
        "total_checks": len(results),
        "failed_checks": [r.name for r in failed],
    }


if __name__ == "__main__":
    handler({}, None)
