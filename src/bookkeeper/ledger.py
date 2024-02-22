import itertools
from decimal import Decimal


class InvalidTransactionError(Exception):

    def __init__(self, message, filename=None, line=None, column=None):
        self.message = message
        self.filename = filename
        self.line = line
        self.column = column


class InvalidInputError(Exception):

    def __init__(self, message, filename=None, line=None, column=None, transaction_id=None):
        self.message = message
        self.filename = filename
        self.line = line
        self.column = column
        self.transaction_id = transaction_id


class Transaction:
    def __init__(self, given_id, date, description, entries):
        self.id = given_id
        self.date = date
        self.description = description
        self.entries = entries

    @classmethod
    def create(cls, given_id, date, description, entries):
        sum = 0

        tx = Transaction(given_id, date, description, entries)

        for entry in entries:
            sum += entry.change
            entry.transaction = tx

        if sum != 0:
            raise InvalidTransactionError(f"Transaction {given_id} does not "
                                          f"sum up to zero, got {sum}")

        return tx


class Entry:
    def __init__(self, account, change, description=None):
        self.account = account
        if isinstance(change,(tuple,list)):
            self.debits, self.credits = change
            self.change = self.debits-self.credits
        else:
            self.change = change
            if self.change < 0:
                self.debits, self.credits = Decimal('0.00'),-change
            else:
                self.debits, self.credits = change,Decimal('0.00')
            
        self.description = description
        self.transaction = None


class Account:
    def __init__(self, number, name):
        self.number = number
        self.name = name
        self.entries = []
        self._balance = None

    @property
    def balance(self):
        return self.sum()

    def sum(self):
        if self._balance is None:
            self._balance = sum([ent.change for ent in self.entries])
        return self._balance

    def add_entry(self, entry):
        self.entries.append(entry)
        self._balance = None

    def description(self):
        return f"{self.number} {self.name}"


class Profit:
    """
    Profit is like an account, but the number actually indicates which
    account the profit should be put for the opening transaction of the
    next year.
    """
    def __init__(self, number, name):
        self.number = number
        self.name = name
        self._balance = None

    def sum(self):
        assert self._balance is not None, "Balance not set for Profit"
        return self._balance

    def set(self, balance):
        self._balance = balance

    def description(self):
        return self.name


class Entity:
    """
    This represents a business entity, such as a company.
    """
    def __init__(self, name, accounts, income_statement=None,
                 assets=None,
                 liabilities=None,
                 fiscal_year_start=None, fiscal_year_end=None):
        self.name = name
        self.accounts = accounts
        self.income_statement = income_statement or Block([])
        self.assets = assets or Block([])
        self.liabilities = liabilities or Block([])
        self.fiscal_year_start = fiscal_year_start
        self.fiscal_year_end = fiscal_year_end
        self.transactions = []

    def add_transactions(self, transactions):
        if not transactions:
            # empty transaction list is ok.
            self._set_profit()
            return

        ll = sorted(transactions, key=lambda tr: tr.id)
        if ll[0].id != 0:
            raise InvalidTransactionError("Transaction log must begin with"
                                          " transaction 0")
        prev_id = None
        for tx in ll:
            if prev_id is not None:
                if tx.id != prev_id + 1:
                    raise InvalidTransactionError(
                        f"Missing or extra transactions between {prev_id} and {tx.id}")
            prev_id = tx.id

            for ent in tx.entries:
                try:
                    self.accounts[ent.account].add_entry(ent)
                except KeyError:
                    raise InvalidTransactionError(f"no such account: {ent.account}")
        self.transactions = ll
        self._set_profit()

    @classmethod
    def create_from_transactions(cls, transactions):
        accounts = dict([(ent.account, Account(ent.account, "auto"))
                         for tx in transactions for ent in tx.entries])
        entity = cls("Automatic entity", accounts)
        entity.add_transactions(transactions)
        return entity

    def get_accounts(self):
        return self.accounts.values()

    def _set_profit(self):
        ll = list(Block.find(itertools.chain(self.income_statement.members,
                                             self.assets.members,
                                             self.liabilities.members),
                             Profit))
        if len(ll) > 1:
            raise RuntimeError("There should be at most one Profit object")
        elif len(ll) == 1:
            ll[0].set(self.income_statement.sum())


class SummaryLine:
    def __init__(self, summary):
        self.summary = summary

    def sum(self):
        """
        Does not contribute to account.
        """
        return 0


class Block:
    """
    Block contains Accounts or Blocks.
    """

    def __init__(self, members=None, title=None, summary=None):
        self.members = members
        self.title = title
        self.summary = summary
        self._sum = None

    def sum(self):
        """
        Sum of a block is the sum of the top level Accounts and Blocks.
        """
        # return sum([member.sum() for member in (self.members or [])])
        if self._sum is None:
            self._sum = sum([member.sum() for member in (self.members or [])])
        return self._sum

    @staticmethod
    def find(it, klass):
        """
        Find all instances of `klass` from iterable `it`, which may be a nested
        list of Blocks.
        """
        def visit(node):
            for cc in node.members:
                if isinstance(cc, klass):
                    yield cc
                elif isinstance(cc, Block):
                    yield from visit(cc)

        for node in it:
            if isinstance(node, Block):
                for acc in visit(node):
                    yield acc


