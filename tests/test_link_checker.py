from src.link_checker import check_affiliate_id_present, check_fact_consistency


def test_check_fact_consistency_pass():
    result = check_fact_consistency(
        post_text="今だけお得！\n\nワイヤレスイヤホン Pro\n3,980円\nhttps://example.com/xxx",
        item_name="ワイヤレスイヤホン Pro",
        item_price=3980,
    )
    assert result.passed


def test_check_fact_consistency_fail_on_price_mismatch():
    result = check_fact_consistency(
        post_text="今だけお得！\n\nワイヤレスイヤホン Pro\n2,980円\nhttps://example.com/xxx",
        item_name="ワイヤレスイヤホン Pro",
        item_price=3980,
    )
    assert not result.passed


def test_check_affiliate_id_present():
    result = check_affiliate_id_present("https://hb.afl.rakuten.co.jp/xxx?pc=abc123", "abc123")
    assert result.passed

    result_missing = check_affiliate_id_present("https://hb.afl.rakuten.co.jp/xxx?pc=other", "abc123")
    assert not result_missing.passed
