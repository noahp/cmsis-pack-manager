# ARM Pack Manager
# Copyright (c) 2017 ARM Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import operator
from os.path import basename, join, dirname, exists
from os import makedirs
from itertools import takewhile
from functools import reduce
from json import dump
import yaml
from cmsis_pack_manager import Cache

parser = argparse.ArgumentParser(description='A utility that keeps your cache of pack files up to date.')
subparsers = parser.add_subparsers(title="Commands")

def subcommand(name, *args, **kwargs):
    def subcommand(command):
        subparser = subparsers.add_parser(name, **kwargs)

        for arg in args:
            arg = dict(arg)
            opt = arg['name']
            del arg['name']

            if isinstance(opt, basestring):
                subparser.add_argument(opt, **arg)
            else:
                subparser.add_argument(*opt, **arg)

        subparser.add_argument("-v", "--verbose", action="store_true", dest="verbose", help="Verbose diagnostic output")
        subparser.add_argument("-vv", "--very-verbose", action="store_true", dest="very_verbose", help="Very verbose diagnostic output")
        subparser.add_argument("--no-timeouts", action="store_true", help="Remove all timeouts and try to download unconditionally")
        subparser.add_argument("--and", action="store_true", dest="intersection", help="Combine search terms as if with an `and`")
        subparser.add_argument("--or", action="store_false", dest="intersection", help="Combine search terms as if with an `or`")
        subparser.add_argument("--union", action="store_false", dest="intersection", help="Combine search terms as if with a set union")
        subparser.add_argument("--intersection", action="store_true", dest="intersection", help="Combine search terms as if with a set intersection")
        subparser.add_argument("--vidx-list", dest="vidx_list")
        subparser.add_argument("--data-path", dest="data_path")
        subparser.add_argument("--json-path", dest="json_path")
        
        def thunk(parsed_args):
            cache = Cache(not parsed_args.verbose, parsed_args.no_timeouts,
                          vidx_list=parsed_args.vidx_list,
                          data_path=parsed_args.data_path,
                          json_path=parsed_args.json_path)
            argv = [arg['dest'] if 'dest' in arg else arg['name'] for arg in args]
            argv = [(arg if isinstance(arg, basestring) else arg[-1]).strip('-')
                    for arg in argv]
            argv = {arg: vars(parsed_args)[arg] for arg in argv
                    if vars(parsed_args)[arg] is not None}

            return command(cache, **argv)

        subparser.set_defaults(command=thunk)
        return command
    return subcommand

def fuzzy_find(matches, options, oper=operator.and_):
    return reduce(oper, (set(filter(lambda x: match in x, options))
                         for match in matches))

@subcommand('cache',
            dict(name=['-e','--everything'], action="store_true",
                 help="Download everything possible"),
            dict(name=['-d','--descriptors'], action="store_true",
                 help="Download all descriptors"),
            help="Cache PACK or PDSC files")
def command_cache (cache, everything=False, descriptors=False, verbose=False, intersection=True) :
    if everything :
        cache.cache_everything()
        print("Packs Cached")
        return True
    if descriptors :
        cache.cache_descriptors()
        print("Descriptors Cached")
        return True
    print("No action specified nothing to do")

@subcommand('find-part',
            dict(name='matches', nargs="+", help="Words to match to processors"),
            dict(name=['-l',"--long"], action="store_true",
                 help="Print out part details with part"),
            dict(name=['-p', '--parts-only'], action="store_false", dest="print_aliases"),
            dict(name=['-a', '--aliases-only'], action="store_false", dest="print_parts"),
            help="Find a part and its description within the cache")
def command_find_part (cache, matches, long=False, intersection=True,
                       print_aliases=True, print_parts=True) :
    op = operator.and_ if intersection else operator.or_
    to_dump = {} if long else []
    if print_parts:
        for part in fuzzy_find(matches, cache.index.keys(), op):
            if long:
                to_dump.update({part: cache.index[part]})
            else:
                to_dump.append(part)
    if print_aliases:
        for alias in fuzzy_find(matches, cache.aliases.keys(), op):
            if long:
                if cache.aliases[alias]["mounted_devices"]:
                    part = cache.aliases[alias]["mounted_devices"][0]
                    try:
                        to_dump.update({alias: cache.index[part]})
                    except KeyError:
                        to_dump.update({alias: "Could not find part: %s" % part})
            else:
                to_dump.append(alias)
    print(yaml.safe_dump(to_dump, default_flow_style=None if long else False))

@subcommand('dump-parts',
            dict(name='out', help='Directory to dump to'),
            dict(name='parts', nargs='+', help='Parts to dump'),
            help='Create a directory with an `index.json` describing the part and all of the associated flashing algorithms.'
)
def command_dump_parts (cache, out, parts, intersection=False) :
    op = operator.and_ if intersection else operator.or_
    index = {part: cache.index[part] for part
             in fuzzy_find(parts, cache.index, op)}
    if not exists(out):
        makedirs(out)
    for n, p in index.items():
        try:
            for algo in p['algorithms']:
                if not exists(join(out, dirname(algo['file_name']))):
                    makedirs(join(out, dirname(algo['file_name'])))
                with open(join(out, algo['file_name']), "wb+") as fd:
                    fd.write(cache.pack_from_cache(p).open(algo['file_name']).read())
        except KeyError:
            print("[Warning] {} does not have an associated flashing algorithm".format(n))
    with open(join(out, "index.json"), "wb+") as fd:
        dump(index,fd)

def get_argparse() :
    return parser

def main() :
    args = parser.parse_args()
    args.command(args)

