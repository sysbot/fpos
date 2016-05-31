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

from .core import money
from .cdesc import cdesc
from .predict import prune_groups, pd, icmf, last as last_cyclic
from .visualise import extract_month, PeriodGroup, blacklist
from .db import find_config, as_toml
from collections import namedtuple
import csv
import sys
import datetime
import monthdelta
from itertools import chain

mtt = namedtuple("mtt", [ "month", "transactions" ])
tt = namedtuple("tt", [ "month", "income", "expenses" ])
cdt = namedtuple("cdt", [ "name", "period", "last", "mean", "next" ])

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
        cyclic_descriptors.append(cdt(name, period, last, mean, None))
    return cyclic_descriptors

def balance(margins, longest):
    nmonths = len(margins)
    assert longest <= nmonths, "longest = {}, nmonths = {}".format(longest, nmonths)
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

def calculate_targets(cyclic):
    return { cd : cd.mean / (cd.period / 31) if cd.period else cd.mean
            for cd in cyclic }

def calculate_actuals(cyclic, balanced, last):
    ibalanced = balanced[:]
    actuals = { cd : 0 for cd in cyclic }
    for cd in cyclic:
        md = monthdelta.monthmod(cd.last, last)[0].months
        if md < 1 and ibalanced[-1] > 0:
            v = min(-(cd.mean * (31 / cd.period)), ibalanced[-1])
            ibalanced[-1] -= v
            actuals[cd] += v
        else:
            for month in range(-md, 0):
                if ibalanced[month] > 0:
                    v = min(-(cd.mean / (cd.period / 31)), ibalanced[month])
                    ibalanced[month] -= v
                    actuals[cd] += v
    return actuals

def calculate_due(cyclic, last):
    due = {}
    for cd in cyclic:
        when = cd.last + datetime.timedelta(cd.period)
        if when.month == last.month and when.year == last.year:
            due[cd.name] = cd
    return due

def savings_targets(config):
    targets = []
    if "save" not in config:
        return targets
    for elem in config["save"].values():
        targets.append(cdt(elem["name"], None, pd(elem["entered"]), elem["amount"], pd(elem["deadline"])))
    return targets

def synthetic_cycles(config):
    cycles = []
    if "periodic" not in config:
        return cycles
    for elem in config["periodic"].values():
        entered = pd(elem["entered"])
        start = pd(elem["start"])
        if entered < start:
            cycle = cdt(elem["name"], elem["period"], entered, elem["amount"], start)
        else:
            cycle = cdt(elem["name"], elem["period"], start, elem["amount"], None)
        cycles.append(cycle)
    return cycles

def render_cycle(cycle, start, days):
    if cycle.next and cycle.next > start:
        i = (cycle.next - start).days
        if not days[i]:
            days[i] = []
        days[i].append(cycle)
        return days
    delta = (start - cycle.last).days
    for i in range(cycle.period - delta, len(days), cycle.period):
        if not days[i]:
            days[i] = []
        days[i].append(cycle)
    return days

def psave(transactions, config):
    external = [ elem for elem in transactions if elem[3] != "Internal" ]
    monthly_transactions = to_month_groups(external)
    completed = \
        list(chain(*[mts.transactions for mts in monthly_transactions[:-1]]))
    incomplete = monthly_transactions[-1].transactions
    groups = cdesc(t for t in completed if t[3] not in blacklist)
    last_completed = pd(completed[-1][0])
    cyclic_groups = list(prune_groups(groups, last_completed))
    monthly_tts = to_month_tts(monthly_transactions[:-1])
    sorted_monthly_tts = sorted(monthly_tts, key=lambda x: pm(x.month))
    cyclic_descriptors = to_cycle_descriptors(cyclic_groups)
    cyclic_descriptors.extend(savings_targets(config))
    cyclic_descriptors.extend(synthetic_cycles(config))
    sorted_cyclic_descriptors = \
            sorted(cyclic_descriptors, key=lambda x: x.period, reverse=True)
    unbalanced = [ elem.income + elem.expenses for elem in sorted_monthly_tts ]
    longest_cycle = int(sorted_cyclic_descriptors[0].period / 31)
    balanced = balance(unbalanced, longest_cycle)
    targets = calculate_targets(cyclic_descriptors)
    actuals = calculate_actuals(sorted_cyclic_descriptors, balanced, last_completed)
    last_incomplete = pd(transactions[-1][0])
    due = calculate_due(sorted_cyclic_descriptors, last_incomplete)

    plan = [ None ] * sorted_cyclic_descriptors[0].period
    first_day = \
            datetime.datetime(last_incomplete.year, last_incomplete.month, 1)
    for d in sorted_cyclic_descriptors:
        plan = render_cycle(d, first_day, plan)

    print("Date | Description | Cost | Effective | Sum Cost | Sum Effective")
    agg_cost = 0
    agg_effective = 0
    for i, cts in enumerate(plan):
        if not cts:
            continue
        date = first_day + datetime.timedelta(i)
        for cd in cts:
            saved = actuals[cd]
            effective = min(0, cd.mean + saved)
            actuals[cd] = max(0, cd.mean + saved)
            agg_cost += cd.mean
            agg_effective += effective
            print("{} | {} | {} | {} | {} | {}"
                    .format(date.strftime("%d/%m/%Y"), cd.name, money(cd.mean), money(effective), money(agg_cost), money(agg_effective)))

if __name__ == "__main__":
    transactions = [ row for row in csv.reader(sys.stdin) ]
    if 2 > len(sys.argv):
        print("Need a database name as an argument")
    psave(transactions, as_toml(find_config())[sys.argv[1]])
