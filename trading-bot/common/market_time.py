"""Il tempo della BORSA, non quello del computer.

Due bug reali sono nati dal confondere i due: il ciclo quotidiano
schedulato nel fuso locale (partiva a mercato aperto invece che dopo la
chiusura) e la data di borsa letta da `date.today()` (sabato all'una di
notte in Italia e' ancora venerdi' sera a New York). Un solo posto in cui
questa distinzione e' definita, cosi' non puo' divergere di nuovo."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

MARKET_TIMEZONE = "America/New_York"


def market_now() -> datetime:
    """Ora corrente nel fuso del mercato."""
    return datetime.now(ZoneInfo(MARKET_TIMEZONE))


def market_today() -> date:
    """Data di borsa corrente, non quella del PC."""
    return market_now().date()
