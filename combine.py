#!/usr/bin/python3
#
#    Combines multiple budget IR documents into one
#    Copyright (C) 2013  Andrew Jeffery <andrew@aj.id.au>
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

import argparse
import csv
import datetime
import hashlib
import itertools
import sys

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("database", metavar="FILE", type=argparse.FileType('r'))
    parser.add_argument("updates", metavar="FILE", type=argparse.FileType('r'), nargs='*')
    parser.add_argument('--out', metavar="FILE", type=argparse.FileType('w'),
            default=sys.stdout)
    return parser.parse_args()

def digest_entry(entry):
    s = hashlib.sha1()
    for element in entry[:3]:
        s.update(str(element).encode("UTF-8"))
    return s.hexdigest()

def main():
    args = parse_args()
    try:
        readables = itertools.chain(args.updates, (args.database,))
        rcsvs = (csv.reader(x) for x in readables)
        entries = dict((digest_entry(x), x)
                for db in rcsvs for x in db if 3 <= len(x))
        ocsv = csv.writer(args.out)
        datesort = lambda x: datetime.datetime.strptime(x[0], "%d/%m/%Y").date()
        costsort = lambda x: float(x[1])
        descsort = lambda x: x[2]
        for v in sorted(sorted(sorted(entries.values(), key=descsort), key=costsort), key=datesort):
            ocsv.writerow(v)
    finally:
        args.database.close()
        for e in args.updates:
            e.close()
        args.out.close()

if __name__ == "__main__":
    main()
