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
from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfMerger

from paperpy import (
    SERVER_URL,
    AUTH_TOKEN,
    TAG_COLOUR,
    DOC_COLOUR,
    CORR_COLOUR,
    TITLE_COLOUR,
)


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
        date_str = ""
        if date is not None and date_count is not None:
            date_str = "[#FFA0E0]%s[/][white]/%2s[/] " % (date, date_count)
        return "[#606060]%3d[/] [white]%3d[/] %s[%s bold]%-31s[/] [%s]%-9s[/] [%s]%-12s[/] %s" % (
            idx,
            self.id,
            date_str,
            TITLE_COLOUR,
            str(self.title)[:31],
            CORR_COLOUR,
            str(self.correspondent)[:9],
            DOC_COLOUR,
            str(self.doc_type)[:12],
            str(PaperTag.colour_str(self.tags)),
        )

    def has_title_labels(self, labels):
        labels = labels.split(",")
        for label in labels:
            if not all([label.lower() in self.title.lower()]):
                return False
        return True

    def has_tags(self, tags):
        if not isinstance(tags, (tuple, list)):
            tags = [tags]
        for tag in tags:
            if isinstance(tag, int):
                if not any([tag == t.id for t in self.tags]):
                    return False
            elif not any([tag == t.name for t in self.tags]):
                return False
        return True

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
        self.headers = {"Authorization": "Token {}".format(AUTH_TOKEN)}
        self.tags = None
        self.correspondents = None
        self.doc_types = None

    def patch(self, endpoint, data):
        url = self.base_url + endpoint
        response = requests.patch(url, headers=self.headers, data=data)
        if not response.status_code == 200:
            print(
                "Patch request at %s with data %s failed with code %s"
                % (url, data, response.status_code)
            )
            return None
        return response.json()

    def get(self, endpoint, raw_url=None, as_is=False):
        if raw_url is not None:
            get_url = raw_url
        else:
            get_url = self.base_url + endpoint
            if not endpoint[-1] == "/" and "?" not in endpoint:
                get_url += "/"
        response = requests.get(get_url, headers=self.headers)
        if not response.status_code == 200:
            print(
                "Get request at %s failed with code %s"
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
                r = self.get(endpoint, raw_url=next_url)
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
    ):
        api_str = "documents/"
        api_str += self.query_str(
            correspondent=correspondent,
            doc_type=doc_type,
            tags=tags,
            content=content_terms,
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
            if title_labels is not None:
                if not pd.has_title_labels(title_labels):
                    continue
            self.docs.append(pd)
        return self.docs

    def set_doc_correspondent(self, doc_id, correspondent):
        api_str = "documents/%d/" % (doc_id)
        itemid = self.lookup_item_id(correspondent, self.correspondents)
        if itemid is not None:
            data = {"correspondent": str(itemid)}
            r = self.patch(api_str, data=data)

    def set_doc_type(self, doc_id, doc_type):
        api_str = "documents/%d/" % (doc_id)
        itemid = self.lookup_item_id(doc_type, self.doc_types)
        if itemid is not None:
            data = {"document_type": str(itemid)}
            r = self.patch(api_str, data=data)

    def add_doc_tags(self, doc_id, tag):
        docs = self.get_docs(doc_id=doc_id)
        if not len(docs) == 1:
            print("Warning: could not find document id %d" % (doc_id))
            return
        doc = docs[0]
        if doc.has_tags(tag):
            print("Warning: document %d already has tag %s" % (doc_id, tag))
            return
        ts = [str(t.id) for t in doc.tags]
        new_tags = tag.split(",")
        ts.extend([str(self.lookup_item_id(t, self.tags)) for t in new_tags])
        data = {"tags": ts}
        api_str = "documents/%d/" % (doc_id)
        r = self.patch(api_str, data=data)

    def remove_doc_tags(self, doc_id, tag):
        docs = self.get_docs(doc_id=doc_id)
        if not len(docs) == 1:
            print("Warning: could not find document id %d" % (doc_id))
            return
        doc = docs[0]
        new_tags = tag.split(",")
        new_tags = [self.lookup_item_id(t, self.tags) for t in new_tags]
        ts = [str(t.id) for t in doc.tags if not t.id in new_tags]
        data = {"tags": ts}
        api_str = "documents/%d/" % (doc_id)
        r = self.patch(api_str, data=data)

    def lookup_item_id(self, item, all_items):
        if isinstance(item, int):
            return item
        for e in all_items:
            if item == e.name or item.lower() == e.slug:
                return e.id
        print("Warning: Could not find item id for %s" % (item))
        return None

    def query_str(self, correspondent=None, doc_type=None, tags=None, content=None):
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
        if len(s) > 1:
            return "".join(s).rstrip("&")
        return ""


def merge_docs(fn, files, dates, using_images=False):
    """Merges a list of files (with date strings) into a consolidated pdf file.
    The input files can be other pdf files or image files (using_images=True)."""

    def file_to_image(fn, date):
        im = cv2.imread(fn)
        image = Image.fromarray(im)
        image = image.convert("RGB")
        text = fn.replace(".png", "")
        if len(date) > 0:
            text = text + "  Date: " + date
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype("DIN-Medium.ttf", 10)
        draw.text((0, 0), text, (200, 20, 20), font=font)
        return image

    if using_images:
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
