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
from .visualise import extract_month, PeriodGroup
from collections import namedtuple

tt = namedtuple("tt", [ "income", "expenses" ])
cdt = namedtuple("cdt", [ "name", "period", "last", "mean" ])

def to_month_groups(transactions):
    monthly_grouper = PeriodGroup(extract_month)
    monthly_grouper.add_all(transactions)
    monthly_transactions, = monthly_grouper.groups()
    return monthly_transactions

def to_month_tts(transactions):
    months = []
    for month in transactions:
        income = sum(float(elem[1]) for elem in month
                if float(elem[1]) >= 0)
        expenses = sum(float(elem[1]) for elem in month
                if float(elem[1]) < 0)
        months.append(tt(income, expenses))
    return months

def to_cycle_descriptors(groups):
    cyclic_descriptors = []
    for gd in groups:
        n = len(gd.group)
        name = gd.group[0][0]
        period = icmf(gd.deltas)
        last = last_cyclic(gd.group)
        mean = sum(float(elem[1]) for elem in gd.group) / n
        cyclic_descriptors.append(cdt(name, period, last, mean))
    return cyclic_descriptors

def psave(transactions):
    groups = cdesc(transactions)
    last = pd(transactions[-1][0])
    cyclic_groups = prune_groups(groups, last)
    cyclic_group_descriptions = [ gd.group[0][0] for gd in cyclic_groups ]
    # FIXME: need to use normalised LCS
    acyclic_transactions = [ elem for elem in transactions
            if elem[2] not in cyclic_group_descriptions ]
    monthly_transactions = to_month_groups(acyclic_transactions)
    monthly_tts = to_month_tts(monthly_transactions)
    cyclic_descriptors = to_cycle_descriptors(cyclic_groups)
    sorted_cyclic_descriptors = \
            sorted(cyclic_descriptors, key=lambda x: x.period, reverse=True)
    # Expenses is negative
    margins = [ elem.income + elem.expenses for elem in monthly_tts ]
    targets = { cd : cd.mean / (cd.period / 31) for cd in cyclic_descriptors }
    actuals = {}
    now = None
    for cd in sorted_cyclic_descriptors:
        # Not semantically right
        for month in (now - cd.last).months:
            # Not semantically right
            if margins[month] > 0:
                v = min(cd.mean, margins[month])
                margins[month] -= v
                actuals[cd] += v
    print(targets)
    print(actuals)
    print(margins)
    
if __name__ == "__main__":
    psave()
