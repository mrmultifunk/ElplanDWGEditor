import threading
import time
import urllib.parse

import lk_catalog_sync as sync


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


def test_product_pages_are_forced_sequential_even_if_workers_is_higher(monkeypatch):
    article_nos = [f'500D{i:04d}' for i in range(100)]
    lock = threading.Lock()
    active = 0
    max_active = 0

    def fake_fetch(url, **_kwargs):
        nonlocal active, max_active
        if url == sync.CATALOG_ROOT:
            return _index(article_nos)
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        no = query['vnr'][0]
        with lock:
            active += 1
            max_active = max(max_active, active)
        try:
            time.sleep(0.006)
            return _product(no)
        finally:
            with lock:
                active -= 1

    monkeypatch.setattr(sync, 'fetch_text', fake_fetch)
    snapshot = sync.collect_catalog(max_products=500, workers=8, request_delay_min=0, request_delay_max=0)
    assert len(snapshot.articles) == 100
    assert snapshot.stats.workers == 1
    assert max_active == 1


def test_second_sync_reuses_index_and_product_cache(monkeypatch, tmp_path):
    article_nos = [f'500D{i:04d}' for i in range(100)]
    product_calls = 0
    root_calls = 0

    def fake_fetch(url, **_kwargs):
        nonlocal product_calls, root_calls
        if url == sync.CATALOG_ROOT:
            root_calls += 1
            return _index(article_nos)
        product_calls += 1
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        return _product(query['vnr'][0])

    monkeypatch.setattr(sync, 'fetch_text', fake_fetch)
    cache = tmp_path / 'lk_catalog_cache.json'
    first = sync.collect_catalog(max_products=500, workers=8, cache_path=cache, request_delay_min=0, request_delay_max=0)
    assert len(first.articles) == 100
    assert product_calls == 100
    assert root_calls == 1

    product_calls = 0
    root_calls = 0
    second = sync.collect_catalog(max_products=500, workers=8, cache_path=cache, request_delay_min=0, request_delay_max=0)
    assert len(second.articles) == 100
    assert second.stats.index_cache_hit is True
    assert second.stats.cached_products == 100
    assert product_calls == 0
    assert root_calls == 0


def test_only_failed_product_is_retried(monkeypatch):
    article_nos = [f'500D{i:04d}' for i in range(100)]
    target = article_nos[37]
    calls = {no: 0 for no in article_nos}

    def fake_fetch(url, **_kwargs):
        if url == sync.CATALOG_ROOT:
            return _index(article_nos)
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        no = query['vnr'][0]
        calls[no] += 1
        if no == target and calls[no] == 1:
            raise sync.CatalogSyncError('temporary')
        return _product(no)

    monkeypatch.setattr(sync, 'fetch_text', fake_fetch)
    snapshot = sync.collect_catalog(max_products=500, workers=8, retry_count=1, request_delay_min=0, request_delay_max=0)
    assert len(snapshot.articles) == 100
    assert snapshot.stats.retried_products == 1
    assert calls[target] == 2
    assert all(calls[no] == 1 for no in article_nos if no != target)


def test_recent_core_rows_can_seed_fast_sync_without_old_cache(monkeypatch):
    article_nos = [f'500D{i:04d}' for i in range(100)]
    existing = []
    from datetime import date
    for no in article_nos:
        num = int(no[-4:])
        existing.append({
            'article_no': no,
            'description': f'LK FUGA testprodukt {num}',
            'manufacturer': 'Schneider Electric / Lauritz Knudsen',
            'source': sync.product_detail_url(no),
            'source_checked': date.today().isoformat(),
            'ean': f'{5703302000000+num:013d}',
            'kind': 'component',
            'unit': 'stk',
        })
    product_calls = 0

    def fake_fetch(url, **_kwargs):
        nonlocal product_calls
        if url == sync.CATALOG_ROOT:
            return _index(article_nos)
        product_calls += 1
        raise AssertionError('fresh database records should have been reused')

    monkeypatch.setattr(sync, 'fetch_text', fake_fetch)
    snapshot = sync.collect_catalog(max_products=500, workers=8, existing_articles=existing, request_delay_min=0, request_delay_max=0)
    assert len(snapshot.articles) == 100
    assert snapshot.stats.database_reused_products == 100
    assert product_calls == 0


def test_qt_sync_thread_enables_polite_single_connection_cache_pipeline():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / 'qt_articles.py').read_text(encoding='utf-8')
    assert 'workers=1' in source
    assert 'product_timeout=8.0' in source
    assert 'lk_catalog_cache.json' in source
    assert 'Skånsom synkronisering' in source
    assert 'request_delay_min=0.8' in source
    assert 'backoff_seconds=(5.0, 15.0, 45.0, 120.0)' in source
    assert 'Fuld genhentning' in source
