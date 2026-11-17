"""Check which registry boards actually answer RIGHT NOW, without writing to the database.
Run this first on your own machine/server: it is how you learn which sources are live."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from opportunities.http import FetchError, PoliteClient  # noqa: E402
from opportunities.sources.adapters import ADAPTERS  # noqa: E402
from services.ingestion import load_registry  # noqa: E402


def main() -> int:
    client, ok = PoliteClient(), 0
    reg = load_registry()
    for e in reg:
        url_fn, parse_fn = ADAPTERS[e["ats"]]
        try:
            items = parse_fn(client.get_json(url_fn(e["board"], region=e.get("region", ""))), e)
            n_int = sum(1 for i in items if i.is_internship)
            print(f"OK      {e['ats']}:{e['board']:35s} {len(items):5d} listings, {n_int:3d} internships")
            ok += 1
        except (FetchError, ValueError, KeyError, TypeError) as exc:
            print(f"FAILED  {e['ats']}:{e['board']:35s} {exc}")
    print(f"\n{ok}/{len(reg)} boards responded")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
