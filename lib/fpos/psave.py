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

tt = namedtuple("tt", [ "month", "income", "expenses" ])
cdt = namedtuple("cdt", [ "name", "period", "last", "mean" ])

def pm(datestr):
    return datetime.datetime.strptime(datestr, "%m/%Y")

def to_month_groups(transactions):
    monthly_grouper = PeriodGroup(extract_month)
    monthly_grouper.add_all(transactions)
    monthly_transactions, = monthly_grouper.groups()
    return monthly_transactions

def to_month_tts(transactions):
    months = [] 
    for month, mts in transactions.items():
        income = sum(float(elem[1]) for elem in mts
                if float(elem[1]) >= 0)
        expenses = sum(float(elem[1]) for elem in mts
                if float(elem[1]) < 0)
        mtt = tt(month, income, expenses)
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

def balance(tts, longest):
    assert longest < len(tts)
    ltts = len(tts)
    margins = [ elem.income + elem.expenses for elem in tts ]
    for i in range(ltts - longest, ltts):
        if margins[i] < 0:
            for j in range(i, -1, -1):
                if margins[j] > 0:
                    v = min(-margins[i], margins[j])
                    margins[i] += v
                    margins[j] -= v
                if margins[i] == 0:
                    break
    return margins

def psave(transactions):
    groups = cdesc(t for t in transactions if t[3] not in blacklist)
    last = pd(transactions[-1][0])
    cyclic_groups = list(prune_groups(groups, last))
    acyclic_transactions = [ elem for elem in transactions
            if elem[3] != "Internal" ]
    monthly_transactions = to_month_groups(acyclic_transactions)
    monthly_tts = sorted(to_month_tts(monthly_transactions),
            key=lambda x: pm(x.month))
    pprint(monthly_tts)
    cyclic_descriptors = to_cycle_descriptors(cyclic_groups)
    sorted_cyclic_descriptors = \
            sorted(cyclic_descriptors, key=lambda x: x.period, reverse=True)
    margins = balance(monthly_tts, int(sorted_cyclic_descriptors[0].period / 31))
    # Expenses is negative
    pprint(margins)
    targets = { cd : cd.mean / (cd.period / 31) for cd in cyclic_descriptors }
    actuals = { cd : 0 for cd in sorted_cyclic_descriptors }
    for cd in sorted_cyclic_descriptors:
        print(cd.name)
        md = monthdelta.monthmod(cd.last, last)[0].months
        print(md)
        if md == 0 and margins[-1] > 0:
            v = min(-(cd.mean * (31 / cd.period)), margins[-1])
            margins[-1] -= v
            actuals[cd] += v
        else:
            for month in range(-md, 0):
                print("month index: {}".format(month))
                if margins[month] > 0:
                    v = min(-(cd.mean / (cd.period / 31)), margins[month])
                    print(v)
                    margins[month] -= v
                    actuals[cd] += v
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
    pprint(margins)

if __name__ == "__main__":
    transactions = [ row for row in csv.reader(sys.stdin) ]
    psave(transactions)
