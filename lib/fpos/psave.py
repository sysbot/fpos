#!/usr/bin/python3
#
#    Saving for periodic expenses
#    Copyright (C) 2016  Andrew Jeffery <andrew@aj.id.au>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

from .cdesc import cdesc
from .predict import prune_groups, pd, icmf, last as last_cyclic
from .visualise import extract_month, PeriodGroup, blacklist
from collections import namedtuple
import csv
from pprint import pprint
import sys
import datetime
import monthdelta
from itertools import chain

mtt = namedtuple("mtt", [ "month", "transactions" ])
tt = namedtuple("tt", [ "month", "income", "expenses" ])
cdt = namedtuple("cdt", [ "name", "period", "last", "mean" ])

def pm(datestr):
    return datetime.datetime.strptime(datestr, "%m/%Y")

def to_month_groups(transactions):
    monthly_grouper = PeriodGroup(extract_month)
    monthly_grouper.add_all(transactions)
    monthly_transactions, = monthly_grouper.groups()
    mtl = [ mtt(month, mts) for month, mts in monthly_transactions.items() ]
    return sorted(mtl, key=lambda x: pm(x.month))

def to_month_tts(transactions):
    months = [] 
    for mts in transactions:
        income = sum(float(elem[1]) for elem in mts.transactions
                if float(elem[1]) >= 0)
        expenses = sum(float(elem[1]) for elem in mts.transactions
                if float(elem[1]) < 0)
        mtt = tt(mts.month, income, expenses)
        months.append(mtt)
    return months

def to_cycle_descriptors(groups):
    cyclic_descriptors = []
    for gd in groups:
        name = gd.group[0][2]
        period = icmf(gd.deltas)
        last = last_cyclic(gd.group)
        mean = sum(float(elem[1]) for elem in gd.group) / sum(gd.deltas)
        cyclic_descriptors.append(cdt(name, period, last, mean))
    return cyclic_descriptors

def balance(margins, longest):
    nmonths = len(margins)
    assert longest < nmonths, "longest = {}, nmonths = {}".format(longest, nmonths)
    for i in range(nmonths - longest, nmonths):
        if margins[i] < 0:
            # Find savings, i.e. backwards in time
            for j in range(i, -1, -1):
                if margins[j] > 0:
                    v = min(-margins[i], margins[j])
                    margins[i] += v
                    margins[j] -= v
                if margins[i] == 0:
                    break
    return margins

def psave(transactions):
    external = [ elem for elem in transactions if elem[2] != "Internal" ]
    monthly_transactions = to_month_groups(external)
    completed = list(chain(*[mts.transactions for mts in monthly_transactions[:-1]]))
    incomplete = monthly_transactions[-1].transactions
    assert 3 < len(completed)
    groups = cdesc(t for t in completed if t[2] not in blacklist)
    last_completed = pd(completed[-1][0])
    cyclic_groups = list(prune_groups(groups, last_completed))
    monthly_tts = sorted(to_month_tts(monthly_transactions[:-1]), key=lambda x: pm(x.month))
    cyclic_descriptors = to_cycle_descriptors(cyclic_groups)
    sorted_cyclic_descriptors = \
            sorted(cyclic_descriptors, key=lambda x: x.period, reverse=True)
    unbalanced = [ elem.income + elem.expenses for elem in monthly_tts ]
    balanced = balance(unbalanced, int(sorted_cyclic_descriptors[0].period / 31))
    # Expenses are negative
    targets = { cd : cd.mean / (cd.period / 31) for cd in cyclic_descriptors }
    actuals = { cd : 0 for cd in sorted_cyclic_descriptors }
    for cd in sorted_cyclic_descriptors:
        md = monthdelta.monthmod(cd.last, last_completed)[0].months
        if md == 0 and balanced[-1] > 0:
            v = min(-(cd.mean * (31 / cd.period)), balanced[-1])
            balanced[-1] -= v
            actuals[cd] += v
        else:
            for month in range(-md, 0):
                if balanced[month] > 0:
                    v = min(-(cd.mean / (cd.period / 31)), balanced[month])
                    balanced[month] -= v
                    actuals[cd] += v

    due = {}
    current = pd(transactions[-1][0])
    for cd in sorted_cyclic_descriptors:
        when = cd.last + datetime.timedelta(cd.period)
        if when.month == current.month and when.year == current.year:
            due[cd.name] = cd
    pprint(due)
    print()

    for transaction in incomplete:
        if transaction[3] in blacklist:
            continue
        # FIXME: Use nlcs() to test membership
        desc = transaction[2]
        if desc in due:
            print("Found {} in due".format(desc))
            spent = float(transaction[1])
            saved = actuals[due[desc]]
            effective = min(0, spent + saved)
            remaining = max(0, spent + saved)
            print("{} saved {}, spent {}, effective {}, impact {}"
                    .format(desc, saved, spent, effective, remaining))
            print()
            actuals[due[desc]] = remaining

    print("TARGETS")
    print("-------")
    #pprint({ (k.name, k.period) : v for k, v in targets.items() if v != 0 })
    pprint(targets)
    print()
    print("ACTUALS")
    print("-------")
    #pprint({ (k.name, k.period) : v for k, v in actuals.items() if v != 0 })
    pprint(actuals)
    print()
    print("MARGINS")
    print("-------")
    pprint(balanced)

if __name__ == "__main__":
    transactions = [ row for row in csv.reader(sys.stdin) ]
    psave(transactions)