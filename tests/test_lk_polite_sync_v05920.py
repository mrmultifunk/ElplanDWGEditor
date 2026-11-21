import json
import urllib.parse
from pathlib import Path

import pytest

from elplan_catalog import lk_catalog_sync as sync


def _index(article_nos):
    return '<html><body>' + ''.join(
        f'<img src="/katalog/foto/jpg/{no}.jpg">' for no in article_nos
    ) + '</body></html>'


def _product(no):
    num = int(no[-4:])
    return f'''<html><body><h1>LK FUGA® testprodukt {num}</h1>
        <div>Varenummer: {no}</div>
        <div>EL nummer: {1017000000+num}</div>
        <div>EAN nummer: {5703302000000+num:013d}</div>
        </body></html>'''


def test_default_policy_is_single_connection_with_polite_delay():
    import inspect
    sig = inspect.signature(sync.collect_catalog)
    assert sig.parameters['workers'].default == 1
    assert sig.parameters['request_delay_min'].default == 0.8
    assert sig.parameters['request_delay_max'].default == 1.5
    assert sig.parameters['cache_max_age_hours'].default == 24.0 * 14.0
    assert sig.parameters['index_cache_hours'].default == 24.0


def test_http_429_uses_backoff_then_recovers(monkeypatch):
    article_nos = [f'500D{i:04d}' for i in range(100)]
    target = article_nos[25]
    calls = {target: 0}

    def fake_fetch(url, **_kwargs):
        if url == sync.CATALOG_ROOT:
            return _index(article_nos)
        no = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)['vnr'][0]
        if no == target:
            calls[target] += 1
            if calls[target] == 1:
                raise sync.CatalogHttpError('rate limited', status=429, url=url)
        return _product(no)

    monkeypatch.setattr(sync, 'fetch_text', fake_fetch)
    snap = sync.collect_catalog(
        max_products=500,
        request_delay_min=0,
        request_delay_max=0,
        backoff_seconds=(0,),
    )
    assert len(snap.articles) == 100
    assert calls[target] == 2
    assert snap.stats.rate_limit_events == 1
    assert snap.stats.workers == 1


def test_persistent_403_stops_entire_sync_and_keeps_checkpoint(monkeypatch, tmp_path):
    article_nos = [f'500D{i:04d}' for i in range(100)]
    target = article_nos[20]
    product_calls = []

    def fake_fetch(url, **_kwargs):
        if url == sync.CATALOG_ROOT:
            return _index(article_nos)
        no = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)['vnr'][0]
        product_calls.append(no)
        if no == target:
            raise sync.CatalogHttpError('blocked', status=403, url=url)
        return _product(no)

    monkeypatch.setattr(sync, 'fetch_text', fake_fetch)
    cache = tmp_path / 'lk_cache.json'
    with pytest.raises(sync.CatalogAccessLimitedError) as err:
        sync.collect_catalog(
            max_products=500,
            force_refresh=True,
            cache_path=cache,
            request_delay_min=0,
            request_delay_max=0,
            backoff_seconds=(0, 0),
        )
    assert 'stoppet' in str(err.value).casefold()
    # The crawler must not continue to later product refs after detecting a block.
    assert article_nos[21] not in product_calls
    raw = json.loads(cache.read_text(encoding='utf-8'))
    cp = raw['checkpoint']
    assert cp['active'] is True
    assert cp['force_refresh'] is True
    assert set(article_nos[:20]).issubset(set(cp['completed_refs']))
    assert target not in cp['completed_refs']


def test_full_refresh_resumes_completed_pages_from_checkpoint(monkeypatch, tmp_path):
    article_nos = [f'500D{i:04d}' for i in range(100)]
    target = article_nos[40]
    blocked = {'enabled': True}
    calls_first = []
    calls_second = []
    phase = {'n': 1}

    def fake_fetch(url, **_kwargs):
        if url == sync.CATALOG_ROOT:
            return _index(article_nos)
        no = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)['vnr'][0]
        (calls_first if phase['n'] == 1 else calls_second).append(no)
        if phase['n'] == 1 and blocked['enabled'] and no == target:
            raise sync.CatalogHttpError('blocked', status=429, url=url)
        return _product(no)

    monkeypatch.setattr(sync, 'fetch_text', fake_fetch)
    cache = tmp_path / 'lk_cache.json'
    with pytest.raises(sync.CatalogAccessLimitedError):
        sync.collect_catalog(
            max_products=500,
            force_refresh=True,
            cache_path=cache,
            request_delay_min=0,
            request_delay_max=0,
            backoff_seconds=(),
        )

    phase['n'] = 2
    blocked['enabled'] = False
    snap = sync.collect_catalog(
        max_products=500,
        force_refresh=True,
        cache_path=cache,
        request_delay_min=0,
        request_delay_max=0,
        backoff_seconds=(),
    )
    assert len(snap.articles) == 100
    assert snap.stats.checkpoint_resumed is True
    assert snap.stats.checkpoint_reused_products >= 40
    assert not any(no in calls_second for no in article_nos[:40])
    raw = json.loads(cache.read_text(encoding='utf-8'))
    assert raw['checkpoint'] == {}


def test_v2_cache_is_migrated_without_throwing_away_product_cache(tmp_path):
    cache = tmp_path / 'lk_cache.json'
    cache.write_text(json.dumps({
        'version': 2,
        'index': {'fetched_at': 1, 'refs': ['500D0001']},
        'products': {'500D0001': {'fetched_at': 2, 'article': {'article_no': '500D0001'}, 'extras': []}},
    }), encoding='utf-8')
    raw = sync._load_sync_cache(cache)
    assert raw['version'] == 3
    assert '500D0001' in raw['products']
    assert raw['checkpoint'] == {}


def test_qt_text_explains_rate_limit_and_single_connection():
    source = (Path(__file__).resolve().parents[1] / 'elplan_qt/qt_articles.py').read_text(encoding='utf-8')
    assert 'kun én forbindelse til LK.dk' in source
    assert '0,8–1,5 sek.' in source
    assert 'HTTP 403/429' in source
    assert 'Fuld genhentning (skånsom)' in source


def test_front_page_network_failure_does_not_trigger_450_fallback_requests(monkeypatch):
    calls = []

    def fake_fetch(url, **_kwargs):
        calls.append(url)
        raise sync.CatalogSyncError('offline')

    monkeypatch.setattr(sync, 'fetch_text', fake_fetch)
    with pytest.raises(sync.CatalogSyncError) as err:
        sync.collect_catalog(
            max_products=500,
            request_delay_min=0,
            request_delay_max=0,
        )
    assert 'uden fallback-probing' in str(err.value)
    assert calls == [sync.CATALOG_ROOT]


def test_force_refresh_can_reuse_fresh_index_but_refetches_products(monkeypatch, tmp_path):
    article_nos = [f'500D{i:04d}' for i in range(100)]
    root_calls = 0
    product_calls = 0

    def fake_fetch(url, **_kwargs):
        nonlocal root_calls, product_calls
        if url == sync.CATALOG_ROOT:
            root_calls += 1
            return _index(article_nos)
        product_calls += 1
        no = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)['vnr'][0]
        return _product(no)

    monkeypatch.setattr(sync, 'fetch_text', fake_fetch)
    cache = tmp_path / 'lk_cache.json'
    first = sync.collect_catalog(
        max_products=500,
        cache_path=cache,
        request_delay_min=0,
        request_delay_max=0,
    )
    assert len(first.articles) == 100
    assert root_calls == 1 and product_calls == 100

    root_calls = 0
    product_calls = 0
    second = sync.collect_catalog(
        max_products=500,
        cache_path=cache,
        force_refresh=True,
        request_delay_min=0,
        request_delay_max=0,
    )
    assert len(second.articles) == 100
    assert second.stats.index_cache_hit is True
    assert root_calls == 0
    assert product_calls == 100
