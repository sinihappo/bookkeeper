#!/usr/bin/env python

# TODO: eventually this system should allow inserting these records to a
# web-backend.
import click
import os.path
import pathlib
import os
import re
from bookkeeper import txparser
from bookkeeper import defparser
from bookkeeper import ledger


trspace = ''.maketrans('.,',', ')
trpoint = ''.maketrans('.,',',.')

def dformat_point(value):
    return '{:>,}'.format(value).translate(trpoint)

def dformat_comma(value):
    return '{:>,}'.format(value)

def dformat_space(value):
    return '{:>,}'.format(value).translate(trspace)

def dformat_plain(value):
    return str(value)

dformats = {
    'plain': dformat_plain,
    'space': dformat_space,
    'comma': dformat_comma,
    'point': dformat_point,
    }

dformat = dformat_plain
numeric_width_ = 10
plain_format = True

def set_numeric_format(numeric_format,numeric_width):
    global dformat,numeric_width_,plain_format
    numeric_width_ = numeric_width
    dformat = dformats.get(numeric_format)
    plain_format = (numeric_format == 'plain')
    if not dformat:
        raise Exception('Illegal numeric format "{}"'.format(numeric_format))

def output_general_ledger(ledger, output):
    nwidth = numeric_width_
    print("{:>6} {:39} {:10} {:>{}} {:>{}} {:>{}}".format('','','','Debet €',nwidth,'Kredit €',nwidth,'Saldo €',nwidth), file=output)

    tot_cumulative = 0
    tot_debits = 0
    tot_credits = 0

    sep = "=" * nwidth

    for account in sorted(ledger.accounts.values(),
                          key=lambda acc: acc.number):
        if not account.entries:
            continue

        print("{:4} {}".format(account.number,account.name), file=output)
        cumulative = 0
        debits = 0
        credits = 0
        for entry in account.entries:
            debits += entry.debits
            credits += entry.credits
            cumulative += entry.change

            tot_debits += entry.debits
            tot_credits += entry.credits
            tot_cumulative += entry.change

            description = entry.description or entry.transaction.description
            if len(description) > 39:
                description = description[:36] + "..."

            print("{:>6} {:39} {} {:>{}} {:>{}} {:>{}}".
                      format(entry.transaction.id,description,entry.transaction.date,
                                 dformat(entry.debits),nwidth,
                                 dformat(entry.credits),nwidth,
                                 dformat(cumulative),nwidth,
                                 ),
                      file=output)
        print("{:>57}{:>{}}".format('',sep,(nwidth+1)*3), file=output)
        print("{:>57}{:>{}}".format('',dformat(account.balance),(nwidth+1)*3), file=output)

    print("",file=output)
    print("{:>6} {:39} {:10} {:>{}} {:>{}} {:>{}}".
              format('','','',
                         sep,nwidth,
                         sep,nwidth,
                         sep,nwidth,
                         ),
              file=output)

    print("{:>6} {:39} {:10} {:>{}} {:>{}} {:>{}}".
              format('','Yhteensä','',
                         dformat(tot_debits),nwidth,
                         dformat(tot_credits),nwidth,
                         dformat(tot_cumulative),nwidth,
                         ),
              file=output)


def output_statement(entity, output):
    nwidth = numeric_width_
    def print_block(block, out, indent=0, width=68, change_sign=False):
        if block.sum() == 0:
            return

        given_indent = indent
        indent = given_indent if given_indent > 0 else 0
        ind = " " * 2 * indent

        print("{}{}".format(ind,block.title), file=out)

        name_width = width - 2 * indent - 1 - 10 - 12
        summary_width = width - 2 * indent - 1 - 10

        multiplier = -1 if change_sign else 1

        acc = 0
        for member in block.members:
            acc += member.sum()
            if isinstance(member, ledger.Block):
                print_block(member, out, indent=given_indent + 1,
                            change_sign=change_sign)
            elif isinstance(member, ledger.SummaryLine):
                print(
                    "{}{:{}} {:>{}}".format(ind,member.summary,summary_width,dformat(multiplier * acc),nwidth),
                    file=out)
            else:
                assert (isinstance(member, ledger.Account) or
                        isinstance(member, ledger.Profit)), \
                    "Unexcepted type, got {}".format(type(member))
                if member.sum() != 0:
                    print(
                        "{}  {:{}} {:>{}}".format(ind,member.description(),name_width,dformat(multiplier * member.sum()),nwidth),
                        file=out)
        print(
            "{}{:{}} {:>{}}".format(ind,block.summary,summary_width,dformat(multiplier * block.sum()),nwidth),
            file=out)

    print("{}   {} - {}\n".format(entity.name,entity.fiscal_year_start,entity.fiscal_year_end), file=output)
    print_block(entity.income_statement, output, width=78, indent=-1,
                change_sign=True)
    print("\n\f", file=output)
    print_block(entity.assets, output, width=78, indent=-1)
    print("\n", file=output)
    # print("\f", file=output)
    print_block(entity.liabilities, output, width=78, indent=-1,
                change_sign=True)


def output_journal(entity, output):
    nwidth = numeric_width_
    if not plain_format:
        print("  {:4} {:>{}} {:>{}}".
                  format('','Debet €',nwidth,'Kredit €',nwidth,),
                  file=output)
    debits = 0
    credits = 0
    for tx in entity.transactions:
        print("{:<4} {:%Y%m%d} {}".format(tx.id,tx.date,tx.description), file=output)
        for entry in tx.entries:
            debits += entry.debits
            credits += entry.credits
            print(
                "  {} {:>{}} {:>{}} {}".format(entry.account,
                                            dformat(entry.debits),nwidth,
                                            dformat(entry.credits),nwidth,
                                            entry.description or ''),
                file=output)
        print(file=output)

    sep = "=" * nwidth
    if not plain_format:
        print("  {} {} {}".format('    ',sep,sep),file=output)
        print(
            "  {} {:>{}} {:>{}}".format('    ',
                                               dformat(debits),nwidth,
                                               dformat(credits),nwidth,
                                               ),
            file=output)


@click.command()
@click.argument('DIRECTORY', type=click.Path(dir_okay=True, file_okay=False))
@click.option('--output-directory', default="output", type=click.Path(dir_okay=True, file_okay=False, writable=True))
@click.option('--numeric-format', default="plain")
@click.option('--numeric-width', type=click.IntRange(min=10,max=20),default=10)
def main(directory, output_directory, numeric_format,numeric_width):
    """
    Reference command-line implementation of a Finnish double-entry
    bookkeeping utility.

    Input argument DIRECTORY should contain a directory of text files,
    one for each month, containing entries that contain a transaction number,
    description, and account entries that add up to zero.  The text files
    should be named with the template "YYYY-MM.txt", "YYYY" for the year and
    "MM" for the month.

    Output is written to directory "output" by default.
    """

    set_numeric_format(numeric_format,numeric_width)
    print('Numeric width = {}\n'.format(numeric_width))

    transactions = []
    input_files = list(
        filter(lambda ent: re.match("(data-)?[0-9]+-[0-9]+(\.txt)?$",
                                    ent.name),
               [entry for entry in pathlib.Path(directory).iterdir()
                if entry.is_file()]))

    if not input_files:
        raise click.ClickException("No input files found in current working "
                                   "directory.")

    print("Reading transactions from {} files...".format(len(input_files)))

    for entry in input_files:
        try:
            transactions.extend(txparser.parse(open(entry)))
        except txparser.InvalidInputError as e:
            if e.transaction_id is not None:
                tx = "TX {}: ".format(e.transaction_id)
            else:
                tx = ""
            raise click.ClickException("{}:{}[{}]:{} {}".format(entry,e.line,e.column,tx,str(e))) from None

    defs_path = os.path.join(directory, "ledger-defs.txt")
    if os.path.exists(defs_path):
        entity = defparser.parse(open(defs_path))
        entity.add_transactions(transactions)
    else:
        print("No ledger-defs.txt, deducing from transactions...")
        entity = ledger.Entity.create_from_transactions(transactions)

    output_directory = os.path.realpath(output_directory)
    print("Writing output to {}...".format(output_directory))

    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    output_general_ledger(entity,
                          open(os.path.join(output_directory,
                                            "general-ledger.txt"), "w"))

    output_statement(entity,
                     open(os.path.join(output_directory,
                                       "statement.txt"), "w"))

    output_journal(entity,
                   open(os.path.join(output_directory,
                                     "journal.txt"), "w"))


if __name__ == "__main__":
    main()
