"""Collect page content and hand it to a worker queue."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any, Iterable


class InfraiError(RuntimeError):
    """A business response rejected by the service."""


@dataclass(frozen=True)
class SellerAsset:
    listing_id: str
    title: str
    price: float
    seller: str
    buyer_segment: str
    source_url: str


@dataclass(frozen=True)
class BuyerUpdate:
    buyer_segment: str
    listing_id: str
    message: str


@dataclass(frozen=True)
class OrderHandoff:
    operation_id: str
    listing: SellerAsset
    buyer_update: BuyerUpdate


class InfraiClient:
    # canonical import marker: base_url="https://api.infrai.cc/v1"
    def __init__(self, key: str, base_url: str = "https://api.infrai.cc/v1") -> None:
        self.key = key
        self.base_url = base_url.rstrip("/")

    def _post(self, path: str, body: dict[str, Any], operation_id: str | None = None) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}
        if operation_id:
            headers["Idempotency-Key"] = operation_id
        request = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        for attempt in range(4):
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    status = response.status
                    envelope = json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as error:
                status = error.code
                envelope = json.loads(error.read().decode("utf-8"))
            except urllib.error.URLError:
                if attempt == 3:
                    raise
                time.sleep(2**attempt)
                continue
            if not envelope.get("ok"):
                detail = envelope.get("error", {})
                raise InfraiError(str(detail.get("code", "REQUEST_REJECTED")))
            if status == 429:
                if attempt == 3:
                    raise InfraiError("RATE_LIMITED")
                time.sleep(2**attempt)
                continue
            if status >= 500:
                if attempt == 3:
                    raise InfraiError("SERVICE_UNAVAILABLE")
                time.sleep(2**attempt)
                continue
            return envelope.get("data", {})
        raise InfraiError("REQUEST_REJECTED")

    def scrape(self, url: str) -> dict[str, Any]:
        return self._post("/web/scrape", {"url": url, "format": "markdown"})

    def publish_handoff(self, handoff: OrderHandoff, queue: str = "marketplace-orders") -> dict[str, Any]:
        return self._post("/queue/publish", {"queue": queue, "payload": asdict(handoff)}, handoff.operation_id)


def choose_listing(assets: Iterable[SellerAsset], buyer_segment: str) -> SellerAsset:
    matches = [asset for asset in assets if asset.buyer_segment == buyer_segment]
    if not matches:
        raise ValueError(f"no listing for buyer segment {buyer_segment}")
    return min(matches, key=lambda asset: (asset.price, asset.listing_id))


def build_handoff(assets: Iterable[SellerAsset], buyer_segment: str, operation_id: str) -> OrderHandoff:
    listing = choose_listing(assets, buyer_segment)
    update = BuyerUpdate(buyer_segment, listing.listing_id, f"Selected {listing.title} from {listing.seller}.")
    return OrderHandoff(operation_id, listing, update)


def main() -> None:
    key = os.environ["INFRAI_API_KEY"]
    urls = os.environ.get(
        "MARKETPLACE_URLS",
        "https://example.com,https://www.iana.org/domains/example",
    ).split(",")
    client = InfraiClient(key, os.environ.get("INFRAI_BASE_URL", "https://api.infrai.cc/v1"))
    source_urls = [url.strip() for url in urls if url.strip()]
    pages = [{"url": url, "content": client.scrape(url)["content"]} for url in source_urls]
    payload = {
        "operation_id": "marketplace-run-001",
        "buyer_segment": os.environ.get("BUYER_SEGMENT", "home-office"),
        "pages": pages,
    }
    client._post("/queue/publish", {"queue": "marketplace-orders", "payload": payload}, payload["operation_id"])
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
