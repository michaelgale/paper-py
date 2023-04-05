#! /usr/bin/env python3
#
# Copyright (C) 2023  Michael Gale

# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import argparse
import sys

from slugify import slugify
from rich import print

from toolbox import *
from paperpy import *
from paperpy import TITLE_COLOUR

"""
Command line tool to access paperless-ng server

EXAMPLE USE CASES:
  List all tags, correspondents and doc types in database:
    paperless -lt -lc -ld

  Find documents with any combination of tag, correspondent, or doc type filters:
    paperless -t bmo,2018 -c Michael -d Statement
  Find documents with text label(s) in document title:
    paperless -l Bank,2017,TD
    paperless -l Insurance
  Filter options: -t, -c, -d, -l can be used in any combination
  
  Filter documents by year (using extension processing to estimate document date):
    paperless -t statement,bank -y 2019
  
  Find documents with document id(s):
    paperless -n 200
    paperless -n 200,201,300
  
  Change correspondent:
    paperless -n 300 -mc Michael
  Change doc type:
    paperless -n 300 -md Bill
  Add tag(s):
    paperless -n 300 -at bank,statement
  Remove tag(s):
    paperless -n 300 -rt bank,statement
  
  Process documents using natural language processing and show results:
    paperless -n 300 -v
  Show with more details including all text and numeric tokens:
    paperless -n 300 -vv
  Show best estimate of document date (using deep analysis of any date references in text):
    paperless -n 300 -pd
  Show best date estimate with verbose details:
    paperless -n 300 -vd
    
"""


def print_obj_list(obj, verbose, colour):
    if verbose:
        print(", ".join([repr(o) for o in obj]))
    else:
        print(", ".join([PaperItem.colour_str(o, colour) for o in obj]))


def main():
    parser = argparse.ArgumentParser(
        prefix_chars="-+",
        prog="paperless",
        description="""Command line utility to access a paperless-ng server. 
        Environment variables PAPERLESS_SERVER_URL and PAPERLESS_AUTH_TOKEN must be configured to use this utility.""",
        epilog="""Arguments using multiple comma separated terms should not have spaces before or after the commas
        e.g. -t bill,phone,2019""",
    )
    parser.add_argument(
        "-c",
        "--correspondent",
        action="store",
        default=None,
        nargs="?",
        help="Filter documents by correspondent",
    )
    parser.add_argument(
        "-mc",
        "--modcorrespondent",
        action="store",
        default=None,
        nargs="?",
        help="Modify correspondent",
    )
    parser.add_argument(
        "-d",
        "--doctype",
        action="store",
        default=None,
        nargs="?",
        help="Filter by document type (Statement, Bill, etc.)",
    )
    parser.add_argument(
        "-md",
        "--moddoctype",
        action="store",
        default=None,
        nargs="?",
        help="Modify document type",
    )
    parser.add_argument(
        "-t",
        "--tags",
        action="store",
        default=None,
        nargs="?",
        help="Filter by tags separated with commas (no spaces) (bill,visa,receipt etc.)",
    )
    parser.add_argument(
        "-at",
        "--addtag",
        action="store",
        default=None,
        nargs="?",
        help="Add tag to document",
    )
    parser.add_argument(
        "-rt",
        "--removetag",
        action="store",
        default=None,
        nargs="?",
        help="Remove tag from document",
    )
    parser.add_argument(
        "-l",
        "--title",
        action="store",
        default=None,
        nargs="?",
        help="Filter by terms in the document title",
    )
    parser.add_argument(
        "-w",
        "--words",
        action="store",
        default=None,
        nargs="?",
        help="Filter by words in document content (comma separated)",
    )
    parser.add_argument(
        "-n",
        "--number",
        action="store",
        default=None,
        nargs="?",
        help="Fetch document(s) with document id number (comma separated)",
    )
    parser.add_argument(
        "-y",
        "--year",
        action="store",
        default=None,
        nargs="?",
        help="Filter documents by 4-digit year",
    )
    parser.add_argument(
        "-o",
        "--output",
        action="store",
        default=None,
        nargs="?",
        help="Output document filename for PDF or thumbnail",
    )
    parser.add_argument(
        "-m",
        "--merge",
        action="store_true",
        default=False,
        help="Merge downloaded files into one multi-page PDF",
    )
    parser.add_argument(
        "-lt",
        "--listtags",
        action="store_true",
        default=False,
        help="List all tags in document database",
    )
    parser.add_argument(
        "-lc",
        "--listcorr",
        action="store_true",
        default=False,
        help="List all correspondents in document database",
    )
    parser.add_argument(
        "-ld",
        "--listdoc",
        action="store_true",
        default=False,
        help="List all document types in document database",
    )
    parser.add_argument(
        "-sd",
        "--strictdate",
        action="store_true",
        default=False,
        help="Use strict date formatting",
    )
    parser.add_argument(
        "-pd",
        "--printdate",
        action="store_true",
        default=False,
        help="Print best representative date in document",
    )
    parser.add_argument(
        "-s",
        "--show",
        action="store_true",
        default=False,
        help="Show document PDF",
    )
    parser.add_argument(
        "-st",
        "--showthumb",
        action="store_true",
        default=False,
        help="Show document thumbnail PNG",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=False,
        help="Show verbose details of processed document",
    )
    parser.add_argument(
        "-vv",
        "--veryverbose",
        action="store_true",
        default=False,
        help="Show more verbose details of processed document",
    )
    parser.add_argument(
        "-vd",
        "--verbosedate",
        action="store_true",
        default=False,
        help="Show debug info when finding representative date in document",
    )
    args = parser.parse_args()
    opts = vars(args)

    pc = PaperClient()
    tags = pc.get_tags()
    if opts["listtags"]:
        print_obj_list(tags, opts["verbose"], TAG_COLOUR)
    cs = pc.get_correspondents()
    if opts["listcorr"]:
        print_obj_list(cs, opts["verbose"], CORR_COLOUR)
    ds = pc.get_doc_types()
    if opts["listdoc"]:
        print_obj_list(ds, opts["verbose"], DOC_COLOUR)

    if opts["tags"] is not None:
        opts["tags"] = opts["tags"].split(",")
    docs = None
    get_content = (
        opts["verbose"]
        or opts["year"]
        or opts["veryverbose"]
        or opts["printdate"]
        or opts["verbosedate"]
    )
    if opts["number"] is not None:
        opts["number"] = opts["number"].split(",")
        docs = pc.get_docs(doc_id=opts["number"], with_content=get_content)
    else:
        if any(
            [
                opts["correspondent"],
                opts["doctype"],
                opts["tags"],
                opts["title"],
                opts["words"],
            ]
        ):
            docs = pc.get_docs(
                correspondent=opts["correspondent"],
                doc_type=opts["doctype"],
                tags=opts["tags"],
                title_labels=opts["title"],
                with_content=get_content,
                content_terms=opts["words"],
            )
    if docs is not None and any([e in sys.argv for e in ["-s", "-o", "-st"]]):
        print("Downloading %d files..." % (len(docs)))
        all_files = []
        dates = []
        for i, d in enumerate(docs):
            fn = "doc.pdf"
            if opts["output"] is not None:
                fn = opts["output"]
            elif (not opts["show"] and not opts["showthumb"]) or len(docs) > 1:
                fn = d.title + ".pdf"
            if opts["showthumb"]:
                fn = fn.replace(".pdf", ".png")
            all_files.append(fn)
            if not opts["showthumb"]:
                show = opts["show"] and not opts["merge"]
                pc.get_doc_pdf(d.id, fn, show)
            else:
                show = opts["showthumb"] and not opts["merge"]
                pc.get_doc_thumbnail(d.id, fn, show)
            date = ""
            date_count = 0
            if opts["printdate"]:
                tp = TextProc(text=d.content)
                date = tp.best_date
                date_count = len(tp.dates)
            dates.append(date)
            print(d.colour_str(i + 1, date, date_count))

        if opts["merge"]:
            new_args = [str(e) for e in sys.argv[1:]]
            new_args = [e for e in new_args if e not in ["-o", "-s", "-st", "-m"]]
            mergefn = "-".join([str(e) for e in new_args])
            mergefn = slugify(mergefn)
            mergefn = "Docs-" + mergefn + ".pdf"
            print("Merging documents into [%s bold]%s[/]..." % (TITLE_COLOUR, mergefn))
            merge_docs(mergefn, all_files, dates, opts["showthumb"])
            if opts["show"] or opts["showthumb"]:
                os.system("open %s" % (mergefn))
        return

    if docs is not None:
        print("Found %d documents" % (len(docs)))
        found = []
        for i, d in enumerate(docs):
            if opts["modcorrespondent"]:
                pc.set_doc_correspondent(d.id, opts["modcorrespondent"])
            if opts["moddoctype"]:
                pc.set_doc_type(d.id, opts["moddoctype"])
            if opts["addtag"]:
                pc.add_doc_tags(d.id, opts["addtag"])
            if opts["removetag"]:
                pc.remove_doc_tags(d.id, opts["removetag"])
            dd = pc.get_docs(doc_id=d.id, with_content=True)
            d = dd[0]
            date_str = None
            date_count = None
            if get_content:
                tp = TextProc(text=d.content)
                if opts["verbosedate"]:
                    tp.debug = True
                    tp.dates = tp.get_dates()
                if opts["strictdate"]:
                    tp.dates = tp.get_dates(preferred_format=["%b %d %Y"])
                if opts["printdate"] or opts["verbosedate"]:
                    date_str = tp.best_date
                    date_count = len(tp.dates)
                    if date_str is None:
                        date_str = "----------"
                        date_count = "--"

                if opts["year"] is not None:
                    if not str(tp.best_date)[:4] == opts["year"]:
                        print(
                            "Skipping document %d (%s) with date %s"
                            % (d.id, d.title, tp.best_date)
                        )
                        continue
                    else:
                        found.append(d)
            print(d.colour_str(i + 1, date_str, date_count))
            if opts["verbose"] or opts["veryverbose"]:
                print(tp)
            if opts["veryverbose"]:
                print(
                    tp.tokens,
                )
        if len(found) > 0:
            for i, d in enumerate(found):
                print(d.colour_str(i + 1))


if __name__ == "__main__":
    main()
