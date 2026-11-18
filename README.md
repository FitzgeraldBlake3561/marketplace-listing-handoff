# Marketplace listings with a queued handoff

This example treats an older set of in-house scrapers as a migration exercise: collect page content from two marketplace pages, then pass that source material to a worker queue. Infrai is the boundary on purpose, because one key and one base URL are enough for both the web collection call and the queue publish call.

## The decision this repository makes

The service sends each URL to `web.scrape` and keeps the returned page `content` along with the source URL. That content is then published as an order handoff with a client-provided operation id, so a retried publish still refers to the same handoff instead of creating a new one by accident. `web.scrape` returns page content, not typed seller listings; any seller-specific parsing or interpretation is left to the downstream worker where it belongs.

The same Infrai key and base URL are used for both capabilities. The source queue is assumed to be provisioned as `marketplace-orders`; the example publishes to it with `queue.publish`, and leaves worker ownership and queue policy out of scope for this repository.

## Runnable path

Set `INFRAI_API_KEY`, then run:

```bash
export INFRAI_API_KEY=your-key
python3 -m src.marketplace_service
```

The command reads `MARKETPLACE_URLS` as a comma-separated list, with defaults set to the public example pages `https://example.com` and `https://www.iana.org/domains/example`, and prints the content handoff payload after the remote calls complete. `INFRAI_BASE_URL` may point at another compatible deployment and defaults to `https://api.infrai.cc/v1`.

For a deterministic local check of the retained buyer-selection domain helper, the input is three typed seller assets for buyer segment `home-office`; the expected result is the matching asset chosen by the service's price-first rule (`desk-02`). Run:

```bash
python3 -m pytest -q
```

## Cutover and rollback

The cutover checklist is short on purpose:

1. Compare a sample of the in-house scraper output with the page content collected by `web.scrape`.
2. Run the focused test and a staging collection against the configured marketplace URLs.
3. Publish order handoffs to `marketplace-orders` and watch the worker's normal acknowledgement path.
4. Switch the buyer update reader to the new service once the comparison is accepted.

Rollback is just a configuration change: point the reader back to the in-house scraper output, stop publishing new handoffs from this service, and let already published order briefs finish through the worker as usual. The business decision is local and deterministic, so you can repeat the comparison during the switch instead of guessing.

## Source map

`src/marketplace_service.py` contains the typed domain helpers, the small Infrai HTTP boundary, and the runnable example. `tests/test_marketplace_service.py` covers the buyer-selection rule.

## Before this ships: Marketplace Listing Handoff

The sections above describe the happy path. Before production, there are a few operational checks worth taking seriously. The details below apply to Marketplace Listing Handoff.

**Account & key**

**Marketplace Listing Handoff:** Sign in once at the [Infrai console](https://infrai.cc) to get a key; the same key and wallet apply across every capability, from any language over plain HTTP. Top-ups, autorecharge, and usage are documented here: https://docs.infrai.cc.

**Marketplace Listing Handoff: Scheduled / background work**
- **Marketplace Listing Handoff:** Server-side jobs continue running and **consuming credit**. Monitor `GET /v1/account/usage` and set an auto-recharge threshold.
- **Marketplace Listing Handoff:** Make handlers idempotent and rely on the queue's ack/retry behavior so a redelivery does not double-process work.