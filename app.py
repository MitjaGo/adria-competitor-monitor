def scrape_apify(client, urls, checkin, checkout, adults):

    # ─────────────────────────────
    # 1. CALL APIFY (STABLE FORMAT)
    # ─────────────────────────────
    try:
        run = client.actor("pAk2GX3uArJTHBc9g").call(
            run_input={
                "startUrls": [{"url": u} for u in urls],
                "checkin": checkin.strftime("%Y-%m-%d"),
                "checkout": checkout.strftime("%Y-%m-%d"),
                "adults": adults,
                "rooms": 1,
                "currency": "EUR",
                "language": "en-us",
                "maxResults": 20,
            }
        )
    except Exception as e:
        print("Apify call error:", e)
        return []

    # ─────────────────────────────
    # 2. SAFE dataset ID extraction
    # ─────────────────────────────
    dataset_id = None

    if isinstance(run, dict):
        dataset_id = run.get("defaultDatasetId")

    if not dataset_id:
        dataset_id = getattr(run, "defaultDatasetId", None)

    if not dataset_id:
        print("No dataset ID returned from Apify")
        return []

    # ─────────────────────────────
    # 3. READ RESULTS (with retry)
    # ─────────────────────────────
    dataset = client.dataset(dataset_id)

    items = []

    for _ in range(20):
        items = list(dataset.iterate_items())
        if items:
            break

    if not items:
        print("No data returned from Apify dataset")
        return []

    # ─────────────────────────────
    # 4. RETURN RAW ITEMS
    # ─────────────────────────────
    return items
        
