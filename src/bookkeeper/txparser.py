from lark import Lark, UnexpectedInput, ParseError
import datetime
from decimal import Decimal
from .ledger import Transaction, Entry, InvalidInputError

grammar = r"""
start: transaction*

%import common.NEWLINE
%import common.WS_INLINE
%import common.WS

_ALLWS: WS
_WS: WS_INLINE
_NL: NEWLINE

transaction: ID _WS+ date _WS+ DESCRIPTION _NL entry* _ALLWS?

%import common.INT -> NUMBER
%import common.DIGIT

ID: INT

date: YEAR MONTH DAY
YEAR: DIGIT DIGIT DIGIT DIGIT
MONTH: DIGIT DIGIT
DAY: DIGIT DIGIT

DESCRIPTION: /.+/

%import common.INT

entry: _WS+ ACCOUNT _WS+ CHANGE _WS* ( _WS DESCRIPTION )? _NL
    
ACCOUNT: INT
CHANGE: ["+"|"-"]? INT "." DIGIT DIGIT

"""

parser = Lark(grammar, propagate_positions=True)


def _parse_entry(entry):
    account, change = entry.children[0:2]
    if len(entry.children) > 2:
        description = entry.children[2]
    else:
        description = None

    return Entry(int(account), Decimal(change), description)


def parse(tx_file):
    """
    Parse the given file `tx_file`.
    """
    try:
        tree = parser.parse(tx_file.read())
    except UnexpectedInput as exc:
        raise InvalidInputError(str(exc), getattr(tx_file, 'name', None),
                                exc.line, exc.column)
    except ParseError as exc:
        raise InvalidInputError(str(exc), getattr(tx_file, 'name', None))

    txs = []
    for tx in tree.children:
        id, date, description = tx.children[0:3]
        entries = tx.children[3:]
        year, month, day = date.children

        try:
            datetime_date = datetime.date(int(year), int(month), int(day))
        except ValueError as e:
            raise InvalidInputError(str(e), getattr(tx_file, 'name', None),
                                    line=tx.line, column=tx.column, transaction_id=id) from None
        txs.append(Transaction.create(int(id),
                                      datetime_date,
                                      description,
                                      [_parse_entry(entry) for entry in
                                       entries]))

    return txs
