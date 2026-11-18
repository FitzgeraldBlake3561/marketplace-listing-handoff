from src.marketplace_service import SellerAsset, choose_listing


def test_buyer_gets_lowest_priced_matching_listing() -> None:
    assets = [
        SellerAsset("desk-01", "Oak desk", 240.0, "A", "home-office", "one"),
        SellerAsset("desk-02", "Compact desk", 180.0, "B", "home-office", "two"),
        SellerAsset("lamp-01", "Reading lamp", 40.0, "C", "lighting", "three"),
    ]
    assert choose_listing(assets, "home-office").listing_id == "desk-02"

