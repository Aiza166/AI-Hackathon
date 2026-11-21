"""Link check (deterministic, no network): lookalikes, shorteners, punycode, raw IPs, TLDs, http, login words."""
from app.scam import links


def codes(text: str) -> set[str]:
    return {f for link in links.analyse_text(text) for f in link.findings}


def test_extracts_urls_with_and_without_scheme():
    found = links.extract_urls("Open https://a.example/x or www.b.example and c-d.xyz/pay now.")
    assert [u.host for u in found] == ["a.example", "www.b.example", "c-d.xyz"]


def test_official_mock_and_real_domains_are_allowlisted():
    result = links.analyse_text("Check https://pension.gov.example/status and https://www.bisp.gov.pk/")
    assert all(link.official for link in result)
    assert codes("https://pension.gov.example/status") == set()


def test_subdomain_of_official_domain_is_official_but_suffix_trick_is_not():
    assert links.analyse_text("https://portal.bisp.gov.pk/login")[0].official
    trick = links.analyse_text("https://bisp.gov.pk.verify-now.xyz/claim")[0]
    assert not trick.official
    assert "lookalike" in trick.findings


def test_typosquat_and_brand_in_domain_are_lookalikes():
    assert "lookalike" in codes("http://bisp-gov.pk/claim")
    assert "lookalike" in codes("https://pensi0n.gov.example/")
    assert "lookalike" in codes("https://bisp-relief.com/form")


def test_homoglyph_cyrillic_and_punycode_are_flagged():
    assert {"lookalike", "non_latin"} <= codes("https://bіsp.gov.pk/")  # Cyrillic i
    assert "punycode" in codes("https://xn--bsp-gov-xyz.com/")


def test_shortener_flagged_without_fetching():
    result = links.analyse_text("Details: bit.ly/3abcXYZ")
    assert "shortener" in result[0].findings
    assert result[0].fetched is False


def test_raw_ip_http_suspicious_tld_and_login_words():
    assert {"raw_ip", "insecure_http"} <= codes("http://192.0.2.10/bisp/login")
    assert "suspicious_tld" in codes("https://relief-fund.top/")
    assert "login_or_payment_path" in codes("https://relief.example.com/verify-account?otp=1")


def test_userinfo_at_trick_uses_real_host():
    result = links.analyse_text("https://bisp.gov.pk@evil.example/claim")[0]
    assert result.host == "evil.example"
    assert "userinfo_trick" in result.findings


def test_unrelated_genuine_looking_domain_has_no_lookalike_finding():
    assert "lookalike" not in codes("https://weather.example.com/today")


def test_no_links_returns_empty_list():
    assert links.analyse_text("Your claim was received. No fee is charged.") == []


def test_registrable_domain_handles_pk_second_levels():
    assert links.registrable_domain("a.b.bisp.gov.pk") == "bisp.gov.pk"
    assert links.registrable_domain("shop.example.com") == "example.com"
    assert links.registrable_domain("x.easypaisa.com.pk") == "easypaisa.com.pk"
