from bookkeeper import txparser
from bookkeeper import ledger
import io
import datetime
from decimal import Decimal
import pytest


def test_parser():
    assert txparser.parse(io.StringIO("")) == [], \
        "Empty file should result in empty array of transactions"

    txs = txparser.parse(io.StringIO("""1 20180301 foo

"""))
    assert len(txs) == 1, "Single empty transactions should get parsed"
    tx = txs[0]
    assert isinstance(tx, ledger.Transaction)
    assert tx.id == 1
    assert tx.date == datetime.date(2018, 3, 1)
    assert tx.description == "foo"

    txs = txparser.parse(io.StringIO("""1 20180301 foo

2 20180302 bar

"""))
    assert len(txs) == 2, "List of empty transactions should get parsed"
    assert txs[1].description == "bar"

    txs = txparser.parse(io.StringIO("""1 20180301 foo
  45 -100.00
  65 100.00  Zappadai zupaduu

"""))
    tx = txs[0]

    assert len(tx.entries) == 2, "The transaction should have 2 entries"
    entry = tx.entries[1]

    assert isinstance(entry, ledger.Entry)
    assert entry.account == 65
    assert entry.change == Decimal(100)
    assert entry.description.startswith("Zappa")
    assert isinstance(entry.transaction, ledger.Transaction)
    assert entry.transaction.id == 1

    txs = txparser.parse(io.StringIO("""1 20180301 foo
  45 -100.00\t
  65 100.00  

"""))
    assert len(txs[0].entries) == 2, "Extra whitespace should be ok"


def test_invalid_transactions():
    with pytest.raises(ledger.InvalidInputError):
        txparser.parse(io.StringIO("""1 tsup foo
        
        """))

    with pytest.raises(ledger.InvalidTransactionError):
        txparser.parse(io.StringIO("""1 20180301 foo
  45 -100.00

"""))


def test_invalid_date():
    with pytest.raises(ledger.InvalidInputError):
        txparser.parse(io.StringIO("""1 20180332 foo
          45 -100.00\t
          65 100.00
        """))
