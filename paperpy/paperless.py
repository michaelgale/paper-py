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
  Find documents with search terms in the document contents:
    paperless -w pizza,receipt
    paperless -w mac*
    paperless -w "air* AND (parking OR tickets)"
  Filter options: -t, -c, -d, -l, -w can be used in any combination
  
  Filter documents by year (using extra processing to estimate document date):
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

  Download document thumbnail:
    paperless -n 200 -o doc.png
  Download and show thumbnail:
    paperless -n 200 -st
  Download PDF:
    with document title as filename:
    paperless -n 200 -o
    with a new filename:
    paperless -n 200 -o new_filename.pdf
  Show PDF (launches macOS open app):
    paperless -n 200 -s
  Download several documents (filenames are the document titles):
    paperless -t statement,visa -w pizza -o
  Download several documents and merge into one composite PDF and show it:
    paperless -t statement,visa -w 2020 -m -s
    or merge the thumbnails into one PDF:
    paperless -t statement,visa -w 2020 -m -st    
"""


def print_obj_list(obj, verbose, colour):
    if verbose:
        print(", ".join([repr(o) for o in obj]))
    else:
        print(", ".join([PaperItem.colour_str(o, colour) for o in obj]))


def safe_add_file(files, newfile):
    for f in files:
        if f == newfile:
            f, e = split_filename(newfile)
            newfile = f + "-1" + e
    files.append(newfile)
    return files


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
        "-cd",
        "--changedate",
        action="store",
        default=None,
        nargs="?",
        help="Modify document created date",
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
        "-mt",
        "--modtitle",
        action="store",
        default=None,
        nargs="?",
        help="Modify document title",
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
        help="Filter documents by 4-digit year or ISO date YYYY-MM, YYYY-MM-DD",
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
        "-r",
        "--rename",
        action="store",
        default=None,
        nargs="?",
        help="Rename files when using the -o argument based on a specification",
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
        or opts["veryverbose"]
        or opts["printdate"]
        or opts["verbosedate"]
    )
    if opts["number"] is not None:
        # search by document number(s)
        opts["number"] = opts["number"].split(",")
        docs = pc.get_docs(doc_id=opts["number"], with_content=get_content)
    else:
        # search by correspondent, tags, type, title, words, year
        if any(
            [
                opts["correspondent"],
                opts["doctype"],
                opts["tags"],
                opts["title"],
                opts["words"],
                opts["year"],
            ]
        ):
            docs = pc.get_docs(
                correspondent=opts["correspondent"],
                doc_type=opts["doctype"],
                tags=opts["tags"],
                title_labels=opts["title"],
                content_terms=opts["words"],
                date=opts["year"],
                with_content=get_content,
            )
    FILE_ARGS = ["-s", "-o", "-st", "-m"]
    if docs is not None and any([e in sys.argv for e in FILE_ARGS]):
        print("Downloading %d files..." % (len(docs)))
        all_files = []
        dates = []
        all_ids = []
        for i, d in enumerate(docs):
            date = d.created[:10]
            date_count = None
            if opts["printdate"]:
                tp = TextProc(text=d.content)
                date = tp.best_date
                date_count = len(tp.dates)
                d.set_date(date)
            dates.append(date)
            all_ids.append(d.id)

            fn = "doc.pdf"
            if opts["output"] is not None:
                fn = opts["output"]
            elif (not opts["show"] and not opts["showthumb"]) or len(docs) > 1:
                fn = d.title
                if opts["rename"] is not None:
                    fn = d.filename_with_pattern(opts["rename"])
                    print(
                        "  Renaming [%s bold]%s[/] to [#C060F0 bold]%s[/]"
                        % (TITLE_COLOUR, d.title, fn)
                    )
                fn = fn + ".pdf"
            if opts["showthumb"]:
                fn = fn.replace(".pdf", ".png")
            all_files = safe_add_file(all_files, fn)
            fn = all_files[-1]
            if not opts["showthumb"]:
                show = opts["show"] and not opts["merge"]
                pc.get_doc_pdf(d.id, fn, show)
            else:
                show = opts["showthumb"] and not opts["merge"]
                pc.get_doc_thumbnail(d.id, fn, show)
            print(d.colour_str(i + 1, date, date_count))

        if opts["merge"]:
            mergefn = ["Docs-"]
            for o in [
                opts["correspondent"],
                opts["doctype"],
                opts["tags"],
                opts["title"],
                opts["words"],
                opts["year"],
            ]:
                if o is None:
                    continue
                if isinstance(o, list):
                    for e in o:
                        mergefn.append(str(e))
                else:
                    mergefn.append(str(o))
            mergefn = slugify("-".join(mergefn))
            mergefn = mergefn + ".pdf"
            print("Merging documents into [#40D0FF bold]%s[/]..." % (mergefn))
            merge_docs(mergefn, all_files, dates, opts["showthumb"], all_ids)
            if opts["show"] or opts["showthumb"]:
                os.system("open %s" % (mergefn))
        return

    if docs is not None:
        print("Found %d documents" % (len(docs)))
        for i, d in enumerate(docs):
            if opts["modcorrespondent"]:
                d = pc.set_doc_correspondent(d.id, opts["modcorrespondent"])
            if opts["moddoctype"]:
                d = pc.set_doc_type(d.id, opts["moddoctype"])
            if opts["modtitle"] and not opts["rename"]:
                d = pc.set_doc_title(d.id, opts["modtitle"])
            if "-mt" in sys.argv and opts["rename"] is not None:
                fn = d.filename_with_pattern(opts["rename"])
                if fn is not None and len(fn) > 0:
                    print(
                        "  Changing title [%s bold]%s[/] to [#C060F0 bold]%s[/]"
                        % (TITLE_COLOUR, d.title, fn)
                    )
                    d = pc.set_doc_title(d.id, fn)
            if opts["addtag"]:
                d = pc.add_doc_tags(d.id, opts["addtag"])
            if opts["removetag"]:
                d = pc.remove_doc_tags(d.id, opts["removetag"])
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
                    if date_str is not None and opts["printdate"]:
                        d.set_date(date_str)
                    if date_str is None:
                        date_str = "----------"
                        date_count = "--"
                if "-cd" in sys.argv:
                    if opts["printdate"] and date_str is not None:
                        if not date_str == "----------":
                            d = pc.set_doc_created_date(d.id, date_str)
                    elif opts["changedate"] is not None:
                        d = pc.set_doc_created_date(d.id, opts["changedate"])

            if date_str is None:
                date_str = d.created[:10]
            print(d.colour_str(i + 1, date_str, date_count))

            if opts["verbose"] or opts["veryverbose"]:
                print(str(d))
                print(tp)
            if opts["veryverbose"]:
                print(tp.tokens)


if __name__ == "__main__":
    main()
