"""Design selection is explicit and does not fall back to old memories."""
from dse.designs import resolve


def main() -> int:
    gcd = resolve("gcd")
    aes = resolve("aes")
    assert gcd.id == "gcd"
    assert aes.id == "aes"
    assert gcd.rtl.is_file() and aes.rtl.is_file()
    assert gcd.constraint != aes.constraint
    print("ok  design specs expose live RTL and design-specific constraints")
    print("ALL test_designs PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
