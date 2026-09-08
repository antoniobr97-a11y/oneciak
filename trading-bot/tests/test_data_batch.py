"""Scaricamento a lotti delle barre: e' quello che rende possibile
analizzare tutto il mercato invece dei soli titoli piu' scambiati, quindi
un suo errore silenzioso significa "il bot non ha visto quei titoli"."""
import pandas as pd
import pytest

from common import data


def _frame(n=5, base=100.0):
    idx = pd.date_range("2026-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {"Open": base, "High": base + 2, "Low": base - 2, "Close": base + 1, "Volume": 1_000_000.0},
        index=idx,
    )


def _grouped_by_ticker(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """La forma che yfinance restituisce con group_by='ticker': colonne a
    due livelli (titolo, campo)."""
    return pd.concat(frames, axis=1)


def _grouped_by_field(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """L'altra forma possibile: (campo, titolo)."""
    return _grouped_by_ticker(frames).swaplevel(axis=1).sort_index(axis=1)


def test_batch_download_splits_the_multiindex_into_one_frame_per_symbol(monkeypatch):
    raw = _grouped_by_ticker({"AAPL": _frame(base=100.0), "MSFT": _frame(base=200.0)})
    monkeypatch.setattr(data.yf, "download", lambda tickers, **kw: raw)

    out = data.get_daily_bars_batch(["AAPL", "MSFT"])

    assert set(out) == {"AAPL", "MSFT"}
    assert list(out["AAPL"].columns) == ["open", "high", "low", "close", "volume"]
    assert out["AAPL"]["close"].iloc[-1] == 101.0
    assert out["MSFT"]["close"].iloc[-1] == 201.0
    assert out["AAPL"].index.name == "date"


def test_batch_download_handles_the_field_first_shape(monkeypatch):
    raw = _grouped_by_field({"AAPL": _frame(base=100.0), "MSFT": _frame(base=200.0)})
    monkeypatch.setattr(data.yf, "download", lambda tickers, **kw: raw)

    out = data.get_daily_bars_batch(["AAPL", "MSFT"])

    assert out["MSFT"]["close"].iloc[-1] == 201.0


def test_a_symbol_with_no_data_is_absent_not_flat(monkeypatch):
    """Yahoo restituisce colonne di NaN per un titolo che non conosce.
    Passarle alla pipeline come "grafico piatto" sarebbe peggio che
    ometterle: diventerebbero un'analisi su dati inventati."""
    empty = _frame() * float("nan")
    raw = _grouped_by_ticker({"AAPL": _frame(), "FANTASMA": empty})
    monkeypatch.setattr(data.yf, "download", lambda tickers, **kw: raw)

    out = data.get_daily_bars_batch(["AAPL", "FANTASMA"])

    assert set(out) == {"AAPL"}


def test_a_failed_chunk_loses_only_that_chunk(monkeypatch):
    calls = []

    def _download(tickers, **kw):
        calls.append(list(tickers))
        if "B1" in tickers:
            raise RuntimeError("Yahoo ha chiuso la connessione")
        return _grouped_by_ticker({t: _frame() for t in tickers})

    monkeypatch.setattr(data.yf, "download", _download)

    out = data.get_daily_bars_batch(["A1", "A2", "B1", "B2"], chunk_size=2)

    assert set(out) == {"A1", "A2"}
    assert len(calls) == 2          # il secondo lotto e' fallito, non ha fermato il primo


def test_duplicate_symbols_are_requested_once(monkeypatch):
    calls = []

    def _download(tickers, **kw):
        calls.append(list(tickers))
        return _grouped_by_ticker({t: _frame() for t in tickers})

    monkeypatch.setattr(data.yf, "download", _download)

    data.get_daily_bars_batch(["AAPL", "AAPL", "MSFT"])

    assert calls == [["AAPL", "MSFT"]]


def test_weekly_batch_drops_the_week_in_progress(monkeypatch):
    # ultima barra di mercoledi': la settimana non e' chiusa
    idx = pd.date_range("2026-01-05", periods=10, freq="B")   # lun 5 gen -> ven 16 gen
    frame = pd.DataFrame(
        {"Open": 100.0, "High": 102.0, "Low": 98.0, "Close": 101.0, "Volume": 1e6}, index=idx
    ).iloc[:8]                                                # taglia a mercoledi' 14
    monkeypatch.setattr(data.yf, "download", lambda tickers, **kw: _grouped_by_ticker({"AAPL": frame}))

    weekly = data.get_weekly_bars_batch(["AAPL"])["AAPL"]

    assert len(weekly) == 1          # solo la prima settimana, chiusa


# --- scaricamento per singolo titolo (il ripiego) -----------------------------

def test_single_download_normalises_the_columns(monkeypatch):
    monkeypatch.setattr(data.yf, "download", lambda symbol, **kw: _frame())

    df = data.get_daily_bars("AAPL")

    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert df.index.name == "date"
    assert df["close"].iloc[-1] == 101.0


def test_single_download_flattens_a_multiindex(monkeypatch):
    """Con un solo ticker yfinance restituisce comunque colonne a due
    livelli: senza appiattirle il resto della pipeline non troverebbe
    "close" e il titolo sparirebbe."""
    raw = _grouped_by_ticker({"AAPL": _frame()})
    monkeypatch.setattr(data.yf, "download", lambda symbol, **kw: raw.swaplevel(axis=1))

    df = data.get_daily_bars("AAPL")

    assert df["close"].iloc[-1] == 101.0


def test_an_empty_answer_raises_instead_of_returning_an_empty_frame(monkeypatch):
    """Un DataFrame vuoto passato alla pipeline diventerebbe "nessun
    setup". Deve invece essere un errore, cosi' lo screener lo conta fra i
    titoli falliti e fa scattare l'avviso di scansione incompleta."""
    monkeypatch.setattr(data.yf, "download", lambda symbol, **kw: pd.DataFrame())

    with pytest.raises(ValueError):
        data.get_daily_bars("FANTASMA")


# --- barre settimanali/mensili ------------------------------------------------

def test_resample_aggregates_ohlcv_correctly():
    idx = pd.date_range("2026-01-05", periods=5, freq="B")   # una settimana intera
    df = pd.DataFrame(
        {"open": [10, 11, 12, 13, 14], "high": [20, 21, 30, 23, 24],
         "low": [5, 4, 6, 7, 8], "close": [15, 16, 17, 18, 19], "volume": [1, 1, 1, 1, 1]},
        index=idx, dtype=float,
    )

    weekly = data.resample(df, "W")

    assert len(weekly) == 1
    assert weekly["open"].iloc[0] == 10      # la prima
    assert weekly["high"].iloc[0] == 30      # la piu' alta
    assert weekly["low"].iloc[0] == 4        # la piu' bassa
    assert weekly["close"].iloc[0] == 19     # l'ultima
    assert weekly["volume"].iloc[0] == 5     # la somma


def test_a_closed_week_is_kept_whole():
    idx = pd.date_range("2026-01-05", periods=5, freq="B")   # lun-ven: settimana chiusa
    df = pd.DataFrame(
        {"open": 10.0, "high": 20.0, "low": 5.0, "close": 15.0, "volume": 1.0}, index=idx
    )

    assert len(data.closed_weekly_bars(df)) == 1


def test_the_week_in_progress_is_dropped():
    idx = pd.date_range("2026-01-05", periods=8, freq="B")   # arriva a mercoledi' 14
    df = pd.DataFrame(
        {"open": 10.0, "high": 20.0, "low": 5.0, "close": 15.0, "volume": 1.0}, index=idx
    )

    # due settimane grezze, ma la seconda non e' finita
    assert len(data.resample(df, "W")) == 2
    assert len(data.closed_weekly_bars(df)) == 1
