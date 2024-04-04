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

import os
import requests
import cv2
from PIL import Image, ImageDraw, ImageFont, ImageOps
from pypdf import PdfMerger
from rich import print

from paperpy import (
    SERVER_URL,
    AUTH_TOKEN,
    TAG_COLOUR,
    DOC_COLOUR,
    CORR_COLOUR,
    TITLE_COLOUR,
    DATE_COLOUR,
)

MONTH_DICT = {
    "01": "Jan",
    "02": "Feb",
    "03": "Mar",
    "04": "Apr",
    "05": "May",
    "06": "Jun",
    "07": "Jul",
    "08": "Aug",
    "09": "Sep",
    "10": "Oct",
    "11": "Nov",
    "12": "Dec",
}


def listify(x):
    if isinstance(x, (list, tuple)):
        return x
    return [x]


class PaperItem:
    __slots__ = ("id", "name", "slug", "count")

    def __init__(self, id=None, name=None, slug=None, **kwargs):
        self.id = id
        self.name = name
        self.slug = slug
        self.count = 0

    def __str__(self):
        return self.name

    def __repr__(self):
        return "%d: %s" % (self.id, self.slug)

    def colour_str(self, colour="#F0E0C0"):
        return "[%s]%s[/]" % (colour, self.name)

    def pprint(self):
        return "PaperItem: %d '%s' %d documents" % (self.id, self.name, self.count)

    @classmethod
    def from_result(cls, result):
        item = cls()
        item.id = result["id"]
        item.name = result["name"]
        item.slug = result["slug"]
        item.count = result["document_count"]
        return item

    @staticmethod
    def from_lookup(result, all_items):
        results = listify(result)
        vals = [item for r in results for item in all_items if r == item.id]
        if len(vals) > 1:
            return vals
        if len(vals) == 1:
            return vals[0]
        return None


class PaperTag(PaperItem):
    def __init__(self, **kwargs):
        super().__init__(kwargs)

    def pprint(self):
        return "Tag: %d '%s' %d documents" % (self.id, self.name, self.count)

    @staticmethod
    def colour_str(tags, sep=" "):
        tags = listify(tags)
        return "".join(["[%s]%s[/]%s" % (TAG_COLOUR, t, sep) for t in tags]).rstrip(",")


class PaperCorrespondent(PaperItem):
    def __init__(self, **kwargs):
        super().__init__(kwargs)

    def pprint(self):
        return "Correspondent: %d '%s' (%s) %d documents" % (
            self.id,
            self.name,
            self.slug,
            self.count,
        )

    def colour_str(self, length=9, colour=CORR_COLOUR):
        fmt = "[%%s]%%-%ds[/]" % (length)
        return fmt % (colour, self.name[:length])


class PaperDocType(PaperItem):
    def __init__(self, **kwargs):
        super().__init__(kwargs)

    def pprint(self):
        return "Doc Type: %d '%s' (%s) %d documents" % (
            self.id,
            self.name,
            self.slug,
            self.count,
        )

    def colour_str(self, length=12, colour=DOC_COLOUR):
        fmt = "[%%s]%%-%ds[/]" % (length)
        return fmt % (colour, self.name[:length])


class PaperDoc:
    def __init__(self, **kwargs):
        self.id = id
        self.title = ""
        self.correspondent = PaperCorrespondent()
        self.doc_type = PaperDocType()
        self.tags = []
        self.created = None
        self.added = None
        self.asn = 0
        self.original_fn = ""
        self.archive_fn = ""
        self.content = None
        self.year = ""
        self.month = ""
        self.day = ""
        for k, v in kwargs.items():
            if k in self.__dict__:
                self.__dict__[k] = v

    def __str__(self):
        s = []
        s.append("Document: %d '%s'" % (self.id, self.title))
        s.append("  correspondent: %s  type: %s" % (self.correspondent, self.doc_type))
        s.append("  created: %s  added: %s" % (self.created, self.added))
        ts = [str(t) for t in self.tags]
        s.append("  tags: %s" % (",".join(ts)))
        s.append("  serial no: %s" % (self.asn))
        s.append("  original filename: %s" % (self.original_fn))
        s.append("  archived filename: %s" % (self.archive_fn))
        return "\n".join(s)

    def colour_str(self, idx, date=None, date_count=None):
        def diff_date(a, b):
            dstr = ""
            for ca, cb in zip(a, b):
                if ca == cb:
                    dstr += "[green]%1s[/]" % (cb)
                else:
                    dstr += "[yellow]%1s[/]" % (cb)
            return dstr

        date_str = ""
        if date is not None and date_count is not None:
            cdate = str(self.created)[:10]
            date_str = "[%s]%s[/][white]/%2s[/] " % (DATE_COLOUR, cdate, date_count)
            date_str = date_str + diff_date(cdate, date) + " "
        if date is not None and date_count is None:
            date_str = "[%s]%s[/][white][/] " % (DATE_COLOUR, date)
        return "[#606060]%3d[/] [white]%4d[/] %s[%s bold]%-31s[/] %s %s %s" % (
            idx,
            self.id,
            date_str,
            TITLE_COLOUR,
            str(self.title)[:31],
            self.correspondent.colour_str(),
            self.doc_type.colour_str(),
            str(PaperTag.colour_str(self.tags)),
        )

    def set_date(self, date):
        if date is None:
            return
        self.year = date[:4]
        self.month = date[5:7]
        self.month_str = MONTH_DICT[self.month]
        self.day = date[8:10]

    def has_title_labels(self, labels):
        labels = labels.split(",")
        for label in labels:
            if not all([label.lower() in self.title.lower()]):
                return False
        return True

    def has_tags(self, tags):
        tags = listify(tags)
        for tag in tags:
            if isinstance(tag, int):
                if not any([tag == t.id for t in self.tags]):
                    return False
            elif not any([tag == t.name for t in self.tags]):
                return False
        return True

    def has_any_tags(self, tags):
        tags = listify(tags)
        for tag in tags:
            if isinstance(tag, int):
                if any([tag == t.id for t in self.tags]):
                    return True
            elif any([tag == t.name for t in self.tags]):
                return True
        return False

    def is_type(self, doc_type):
        if doc_type == self.doc_type.name:
            return True
        if doc_type.lower() == self.doc_type.slug:
            return True
        if isinstance(doc_type, int) and doc_type == self.doc_type.id:
            return True
        return False

    def has_correspondent(self, correspondent):
        if correspondent == self.correspondent.name:
            return True
        if correspondent.lower() == self.correspondent.slug:
            return True
        if isinstance(correspondent, int) and correspondent == self.correspondent.id:
            return True
        return False

    def filename_with_pattern(self, pattern):
        """pattern specifies:
        [usertext]
        c or ccc... - correspondent or up to no. of characters
        d or ddd... - document type or up to no. of characters
        t or ttt... - token or up to no. of tokens
        YYYY or YY - year
        MMM or MM - month
        DD - day
        e.g. [EM-Invoices]-c-YYYY-MM
            EM-Invoices-Alice-2020-02
            EM-Invoices-Alice-2020-03 ... etc.
        e.g. [Bank]_dddc_MMM-YY
            Bank_StaAlice_Jan-20
            Bank_StaAlice_Feb-20 etc.
        """

        def token_fill(token, prefix, content):
            tl = int(token.replace(prefix, ""))
            if tl == 1:
                return content
            return content[:tl]

        text_chunks = []
        fmt = ""
        in_braces = False
        for c in pattern:
            if c == "[":
                in_braces = True
                text = ""
                fmt += " [*] "
            elif c == "]":
                in_braces = False
                text_chunks.append(text)
            elif not in_braces:
                fmt += c
            elif in_braces:
                text += c
        fmt = fmt.replace("YYYY", " *Y ")
        fmt = fmt.replace("YY", " *y ")
        fmt = fmt.replace("MMM", " *M ")
        fmt = fmt.replace("MM", " *m ")
        fmt = fmt.replace("DD", " *D ")
        for sz in range(32, 0, -1):
            fmt = fmt.replace("c" * sz, " *(%d " % (sz))
        for sz in range(32, 0, -1):
            fmt = fmt.replace("d" * sz, " *)%d " % (sz))
        for sz in range(32, 0, -1):
            fmt = fmt.replace("t" * sz, " *^%d " % (sz))
        fmt = fmt.split()
        idx = 0
        fn = []
        for token in fmt:
            if token == "*Y":
                fn.append(self.year)
            elif token == "*y":
                fn.append(self.year[2:4])
            elif token == "*M":
                fn.append(self.month_str)
            elif token == "*m":
                fn.append(self.month)
            elif token == "*D":
                fn.append(self.day)
            elif token.startswith("*("):
                fn.append(token_fill(token, "*(", str(self.correspondent)))
            elif token.startswith("*^"):
                tl = int(token.replace("*^", ""))
                tm = min(tl, len(self.tags))
                for i in range(tm):
                    fn.append(str(self.tags[i]))
            elif token.startswith("*)"):
                fn.append(token_fill(token, "*)", str(self.doc_type)))
            elif token == "[*]":
                fn.append(text_chunks[idx])
                idx += 1
            else:
                fn.append(token)
        fn = "".join(fn)
        return fn

    @staticmethod
    def from_result(
        result, tags=None, correspondents=None, doc_types=None, with_content=False
    ):
        d = PaperDoc()
        d.id = result["id"]
        d.title = result["title"]
        if correspondents is not None:
            d.correspondent = PaperItem.from_lookup(
                result["correspondent"], correspondents
            )
        else:
            d.correspondent = result["correspondent"]
        if doc_types is not None:
            d.doc_type = PaperItem.from_lookup(result["document_type"], doc_types)
        else:
            d.doc_type = result["document_type"]
        if tags is not None:
            d.tags = PaperItem.from_lookup(result["tags"], tags)
        else:
            d.tags = result["tags"]
        d.created = result["created"]
        d.set_date(str(d.created)[:10])
        d.added = result["added"]
        d.asn = result["archive_serial_number"]
        d.original_fn = result["original_file_name"]
        d.archive_fn = result["archived_file_name"]
        if with_content:
            d.content = result["content"]
        return d


class PaperClient:
    def __init__(self, **kwargs):
        self.base_url = SERVER_URL
        if not self.base_url.endswith("/"):
            self.base_url += "/"
        self.headers = {"Authorization": "Token {}".format(AUTH_TOKEN)}
        self.tags = None
        self.correspondents = None
        self.doc_types = None
        self.dry_run = False

    def __getitem__(self, key):
        """Returns a PaperDoc object with specified ID as the key"""
        docs = self.get_docs(doc_id=key)
        if len(docs) > 0:
            return docs[0]
        return None

    def patch(self, endpoint, data):
        url = self.base_url + endpoint
        response = requests.patch(url, headers=self.headers, data=data)
        if not response.status_code == 200:
            print(
                "[red]Patch request at %s with data %s failed with code %s[/]"
                % (url, data, response.status_code)
            )
            return None
        pd = PaperDoc.from_result(
            response.json(),
            tags=self.tags,
            correspondents=self.correspondents,
            doc_types=self.doc_types,
            with_content=True,
        )
        return pd

    def get(self, endpoint, next_url=None, as_is=False):
        if next_url is not None:
            get_url = next_url
        else:
            get_url = self.base_url + endpoint
            if not endpoint[-1] == "/" and "?" not in endpoint:
                get_url += "/"
        response = requests.get(get_url, headers=self.headers)
        if not response.status_code == 200:
            print(
                "[red]Get request at %s failed with code %s[/]"
                % (get_url, response.status_code)
            )
            return None
        if as_is:
            return response
        return response.json()

    def multi_page_get(self, endpoint):
        results = []
        not_done = True
        next_url = None
        while not_done:
            if next_url is None:
                r = self.get(endpoint)
            else:
                r = self.get(endpoint, next_url=next_url)
            if r is not None:
                results.extend(r["results"])
                next_url = r["next"]
                if next_url is None:
                    not_done = False
            else:
                not_done = False
        return results

    def get_tags(self):
        tags = self.multi_page_get("tags")
        self.tags = [PaperTag.from_result(t) for t in tags]
        return self.tags

    def get_correspondents(self):
        correspondents = self.multi_page_get("correspondents")
        self.correspondents = [
            PaperCorrespondent.from_result(c) for c in correspondents
        ]
        return self.correspondents

    def get_doc_types(self):
        docs = self.multi_page_get("document_types")
        self.doc_types = [PaperDocType.from_result(d) for d in docs]
        return self.doc_types

    def get_doc_file(self, fn, endpoint, show=False):
        r = self.get(endpoint, as_is=True)
        if r.status_code == 200:
            with open(fn, "wb") as f:
                f.write(r.content)
            if show:
                os.system("open %s" % (fn))

    def get_doc_thumbnail(self, doc_id, fn=None, show=False):
        fn = "doc.png" if fn is None else fn
        api_str = "documents/%s/thumb/" % (str(doc_id))
        self.get_doc_file(fn, api_str, show=show)

    def get_doc_pdf(self, doc_id, fn=None, show=False):
        fn = "doc.pdf" if fn is None else fn
        api_str = "documents/%s/download/" % (str(doc_id))
        self.get_doc_file(fn, api_str, show=show)

    def get_docs(
        self,
        doc_id=None,
        correspondent=None,
        doc_type=None,
        tags=None,
        title_labels=None,
        content_terms=None,
        with_content=False,
        date=None,
        any_tags=None,
    ):
        api_str = "documents/"
        api_str += self.query_str(
            correspondent=correspondent,
            doc_type=doc_type,
            tags=tags,
            content=content_terms,
            date=date,
        )
        if doc_id is not None:
            docs = []
            doc_ids = listify(doc_id)
            for d in doc_ids:
                api_str = "documents/%s/" % (str(d))
                docs.append(self.get(api_str))
        else:
            docs = self.multi_page_get(api_str)
        self.docs = []
        for d in docs:
            pd = PaperDoc.from_result(
                d,
                tags=self.tags,
                correspondents=self.correspondents,
                doc_types=self.doc_types,
                with_content=with_content,
            )
            if tags is not None:
                if not pd.has_tags(tags):
                    continue
            if any_tags is not None:
                if not pd.has_any_tags(any_tags):
                    continue
            if title_labels is not None:
                if not pd.has_title_labels(title_labels):
                    continue
            self.docs.append(pd)
        return self.docs

    def set_doc_correspondent(self, doc_id, correspondent):
        api_str = "documents/%d/" % (doc_id)
        itemid = self.lookup_item_id(correspondent, self.correspondents)
        if itemid is not None:
            if self.dry_run:
                print(
                    "Would change document correspondent to [%s]%s[/]"
                    % (CORR_COLOUR, correspondent)
                )
                return self[doc_id]
            data = {"correspondent": str(itemid)}
            return self.patch(api_str, data=data)
        return None

    def set_doc_type(self, doc_id, doc_type):
        api_str = "documents/%d/" % (doc_id)
        itemid = self.lookup_item_id(doc_type, self.doc_types)
        if itemid is not None:
            if self.dry_run:
                print(
                    "Would change document type to [%s]%s[/]" % (DOC_COLOUR, doc_type)
                )
                return self[doc_id]
            data = {"document_type": str(itemid)}
            return self.patch(api_str, data=data)
        return None

    def set_doc_created_date(self, doc_id, date):
        api_str = "documents/%d/" % (doc_id)
        if date is not None:
            if self.dry_run:
                print("Would change document date to [%s]%s[/]" % (DATE_COLOUR, date))
                return self[doc_id]
            new_date = "%sT12:00:00-05:00" % (date)
            data = {"created": new_date}
            return self.patch(api_str, data=data)
        return None

    def set_doc_title(self, doc_id, title):
        api_str = "documents/%d/" % (doc_id)
        if title is not None:
            if self.dry_run:
                print(
                    "Would change document title to [%s]%s[/]" % (TITLE_COLOUR, title)
                )
                return self[doc_id]
            data = {"title": str(title)}
            return self.patch(api_str, data=data)
        return None

    def add_doc_tags(self, doc_id, tag):
        docs = self.get_docs(doc_id=doc_id)
        if not len(docs) == 1:
            print("Warning: could not find document id %d" % (doc_id))
            return
        doc = docs[0]
        unique_tags = []
        for t in tag.split(","):
            if doc.has_tags(t):
                print(
                    "Warning: document [white]%d[/] already has tag %s"
                    % (doc_id, PaperTag.colour_str(t))
                )
            else:
                unique_tags.append(t)
        if len(unique_tags) == 0:
            print("No new tags added")
            return self[doc_id]
        tag = ",".join(unique_tags)
        ts = [str(t.id) for t in doc.tags]
        new_tags = tag.split(",")
        ts.extend([str(self.lookup_item_id(t, self.tags)) for t in new_tags])
        api_str = "documents/%d/" % (doc_id)
        if self.dry_run:
            print("Would add document tags %s" % (PaperTag.colour_str(tag)))
            return self[doc_id]
        return self.patch(api_str, data={"tags": ts})

    def remove_doc_tags(self, doc_id, tag):
        docs = self.get_docs(doc_id=doc_id)
        if not len(docs) == 1:
            print("Warning: could not find document id [white]%d[/]" % (doc_id))
            return
        doc = docs[0]
        new_tags = tag.split(",")
        new_tags = [self.lookup_item_id(t, self.tags) for t in new_tags]
        ts = [str(t.id) for t in doc.tags if not t.id in new_tags]
        api_str = "documents/%d/" % (doc_id)
        if self.dry_run:
            print("Would remove document tags %s" % (PaperTag.colour_str(tag)))
            return self[doc_id]
        return self.patch(api_str, data={"tags": ts})

    def lookup_item_id(self, item, all_items):
        if isinstance(item, int):
            return item
        for e in all_items:
            if item == e.name or item.lower() == e.slug:
                return e.id
        print("[yellow]Warning: Could not find item id for [white]%s[/][/]" % (item))
        return None

    def query_str(
        self, correspondent=None, doc_type=None, tags=None, content=None, date=None
    ):
        s = ["?"]
        if content is not None:
            terms = listify(content.split(","))
            s.append("query=")
            for t in terms:
                s.append("%s%%20" % (t))
            s.append("&")
        if correspondent is not None:
            itemid = self.lookup_item_id(correspondent, self.correspondents)
            if itemid is not None:
                s.append("correspondent__id=%d&" % (itemid))
        if doc_type is not None:
            itemid = self.lookup_item_id(doc_type, self.doc_types)
            if itemid is not None:
                s.append("document_type__id=%d&" % (itemid))
        if tags is not None:
            for t in tags:
                itemid = self.lookup_item_id(t, self.tags)
                if itemid is not None:
                    s.append("tags__id=%d&" % (itemid))
        if date is not None:
            date = date.replace("-", "").replace("/", "")
            if len(date) >= 4:
                s.append("created__year=%s&" % (date[:4]))
            if len(date) >= 6:
                s.append("created__month=%s&" % (date[4:6]))
            if len(date) >= 8:
                s.append("created__day=%s&" % (date[6:8]))
        if len(s) > 1:
            return "".join(s).rstrip("&")
        return ""


def merge_docs(fn, files, dates, using_images=False, other=None):
    """Merges a list of files (with date strings) into a consolidated pdf file.
    The input files can be other pdf files or image files (using_images=True)."""

    def file_to_image(fn, date, prefix=None):
        # open with cv2 instead of PIL since grayscale images don't
        # convert properly when merged
        im = cv2.imread(fn)
        im = cv2.cvtColor(im, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(im)
        image = image.convert("RGB")
        image = ImageOps.autocontrast(image)
        if prefix is not None:
            text = "%s: %s" % (prefix, fn.replace(".png", ""))
        else:
            text = "%s" % (fn.replace(".png", ""))
        draw = ImageDraw.Draw(image)
        try:
            font = ImageFont.truetype("DIN-Medium.ttf", 10)
        except OSError:
            font = ImageFont.load_default()
        draw.text((0, 0), text, (40, 20, 160), font=font)
        if date is not None:
            if len(date) >= 8:
                ds = date.split("-")
                if len(ds) == 3:
                    date = ds[0] + "-" + MONTH_DICT[ds[1]] + "-" + ds[2]
                x2 = image.width / 2
                draw.text((x2, 0), date, (160, 20, 20), font=font)
        return image

    if using_images:
        if other is not None:
            images = [file_to_image(f, d, o) for f, d, o in zip(files, dates, other)]
        else:
            images = [file_to_image(f, d) for f, d in zip(files, dates)]
        images[0].save(fn, save_all=True, append_images=images[1:])
    else:
        merger = PdfMerger()
        for f in files:
            merger.append(f)
        merger.write(fn)
        merger.close()
    for f in files:
        os.remove(f)
