import argparse
import requests
from toolbox import *

try:
    AUTH_TOKEN = os.environ["PAPERLESS_AUTH_TOKEN"]
except:
    print("API authorization token not found in environment")
    exit()

"""
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

class PaperItem:
    __slots__ = ("id", "name", "slug", "count")

    def __init__(self, id=None, name=None, slug=None, **kwargs):
        self.id = id
        self.name = name
        self.slug = slug
        self.count = 0

    def __str__(self):
        return "Tag: %d '%s' %d documents" % (self.id, self.name, self.count)

    @staticmethod
    def from_result(cls, result):
        item = cls()
        item.id = result["id"]
        item.name = result["name"]
        item.slug = result["slug"]
        item.count = result["document_count"]
        return item

    @staticmethod
    def from_lookup(result, all_items):
        if not isinstance(result, list):
            results = [result]
        else:
            results = result
        vals = []
        for r in results:
            for item in all_items:
                if r == item.id:
                    vals.append(item)
        if len(vals) > 1:
            return vals
        if len(vals) == 1:
            return vals[0]
        return None


class PaperTag(PaperItem):
    def __init__(self, **kwargs):
        super().__init__(kwargs)

    def __str__(self):
        return self.name

    def pprint(self):
        return "Tag: %d '%s' %d documents" % (self.id, self.name, self.count)

    @staticmethod
    def from_result(result):
        return PaperItem.from_result(PaperTag, result)


class PaperCorrespondent(PaperItem):
    def __init__(self, **kwargs):
        super().__init__(kwargs)

    def __str__(self):
        return self.name

    def pprint(self):
        return "Correspondent: %d '%s' (%s) %d documents" % (
            self.id,
            self.name,
            self.slug,
            self.count,
        )

    @staticmethod
    def from_result(result):
        return PaperItem.from_result(PaperCorrespondent, result)


class PaperDocType(PaperItem):
    def __init__(self, **kwargs):
        super().__init__(kwargs)

    def __str__(self):
        return self.name

    def pprint(self):
        return "Doc Type: %d '%s' (%s) %d documents" % (
            self.id,
            self.name,
            self.slug,
            self.count,
        )

    @staticmethod
    def from_result(result):
        return PaperItem.from_result(PaperDocType, result)


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
        self.base_url = "http://paperless.home.lan:8000/api/"
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
        self.tags = []
        for tag in tags:
            t = PaperTag.from_result(tag)
            self.tags.append(t)
        return self.tags

    def get_correspondents(self):
        correspondents = self.multi_page_get("correspondents")
        self.correspondents = []
        for c in correspondents:
            pc = PaperCorrespondent.from_result(c)
            self.correspondents.append(pc)
        return self.correspondents

    def get_doc_types(self):
        docs = self.multi_page_get("document_types")
        self.doc_types = []
        for d in docs:
            dt = PaperDocType.from_result(d)
            self.doc_types.append(dt)
        return self.doc_types

    def get_doc_thumbnail(self, doc_id, fn=None, show=False):
        fn = "doc.pdf" if fn is None else fn
        api_str = "documents/%s/thumb/" % (str(doc_id))
        r = self.get(api_str, as_is=True)
        if r.status_code == 200:
            with open(fn, "wb") as f:
                f.write(r.content)
            if show:
                os.system("open %s" % (fn))

    def get_doc_pdf(self, doc_id, fn=None, show=False):
        fn = "doc.pdf" if fn is None else fn
        api_str = "documents/%s/download/" % (str(doc_id))
        r = self.get(api_str, as_is=True)
        if r.status_code == 200:
            with open(fn, "wb") as f:
                f.write(r.content)
            if show:
                os.system("open %s" % (fn))

    def get_docs(
        self,
        doc_id=None,
        correspondent=None,
        doc_type=None,
        tags=None,
        title_labels=None,
        with_content=False,
    ):
        api_str = "documents/"
        api_str += self.query_str(
            correspondent=correspondent, doc_type=doc_type, tags=tags
        )
        if doc_id is not None:
            docs = []
            if isinstance(doc_id, int):
                doc_ids = [doc_id]
            else:
                doc_ids = doc_id
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

    def query_str(self, correspondent=None, doc_type=None, tags=None):
        s = ["?"]
        if correspondent is not None:
            itemid = self.lookup_item_id(correspondent, self.correspondents)
            s.append("correspondent__id=%d&" % (itemid))
        if doc_type is not None:
            itemid = self.lookup_item_id(doc_type, self.doc_types)
            s.append("document_type__id=%d&" % (itemid))
        if tags is not None:
            for t in tags:
                itemid = self.lookup_item_id(t, self.tags)
                s.append("tags__id=%d&" % (itemid))
        if len(s) > 1:
            return "".join(s).rstrip("&")
        return ""


def main():
    parser = argparse.ArgumentParser(prefix_chars="-+")
    parser.add_argument(
        "-c",
        "--correspondent",
        action="store",
        default=None,
        nargs="?",
        help="Include correspondent filter",
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
        help="Include document type filter (Statement, Bill, etc.)",
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
        help="Include tags filter (bill, visa, receipt, etc.)",
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
        help="Include labels in title filter",
    )
    parser.add_argument(
        "-n",
        "--number",
        action="store",
        default=None,
        nargs="?",
        help="Fetch document(s) with document id number",
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
        help="Show downloaded thumbnail or PDF",
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
        print(", ".join([str(t) for t in tags]))
    cs = pc.get_correspondents()
    if opts["listcorr"]:
        print(", ".join([str(c) for c in cs]))
    ds = pc.get_doc_types()
    if opts["listdoc"]:
        print(", ".join([str(d) for d in ds]))
    if opts["tags"] is not None:
        opts["tags"] = opts["tags"].split(",")
    docs = None
    get_content = opts["verbose"] or opts["year"] or opts["veryverbose"] or opts["printdate"] or opts["verbosedate"]
    if opts["number"] is not None:
        opts["number"] = opts["number"].split(",")
        docs = pc.get_docs(doc_id=opts["number"], with_content=get_content)
    else:
        if any([opts["correspondent"], opts["doctype"], opts["tags"], opts["title"]]):
            docs = pc.get_docs(
                correspondent=opts["correspondent"],
                doc_type=opts["doctype"],
                tags=opts["tags"],
                title_labels=opts["title"],
                with_content=get_content,
            )
    if docs is not None and len(docs) == 1 and opts["output"] is not None:
        doc_id = docs[0].id
        if opts["output"].lower().endswith("pdf"):
            pc.get_doc_pdf(doc_id, opts["output"], opts["show"])
        else:
            pc.get_doc_thumbnail(doc_id, opts["output"], opts["show"])
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
            if get_content:
                tp = TextProc(text=d.content)
                if opts["verbosedate"]:
                    tp.debug = True
                    tp.dates = tp.get_dates()
                if opts["strictdate"]:
                    tp.dates = tp.get_dates(preferred_format=["%b %d %Y"])
                if opts["printdate"] or opts["verbosedate"]:
                    toolboxprint(
                        "Document %d best date: %s using %d date candidates"
                        % (d.id, tp.best_date, len(tp.dates)), yellow_words=[(str(d.id))]
                    )
                if opts["year"] is not None:
                    if not str(tp.best_date)[:4] == opts["year"]:
                        print(
                            "Skipping document %d (%s) with date %s"
                            % (d.id, d.title, tp.best_date)
                        )
                        continue
                    else:
                        found.append(d)
            ts = [str(t) for t in d.tags]
            toolboxprint(
                "%3d %3d %-32s %-12s %-16s %s"
                % (i + 1, d.id, d.title, d.correspondent, d.doc_type, ",".join(ts)),
                yellow_words=[str(d.id)],
                magenta_words=[str(d.doc_type)],
                green_words=[d.title],
            )
            if opts["verbose"] or opts["veryverbose"]:
                toolboxprint(tp)
            if opts["veryverbose"]:
                toolboxprint(tp.tokens)
        if len(found) > 0:
            for i, d in enumerate(found):
                toolboxprint(
                    "%3d %3d %-32s %-12s %-16s %s"
                    % (i + 1, d.id, d.title, d.correspondent, d.doc_type, ",".join(ts)),
                    yellow_words=[str(d.id)],
                    magenta_words=[str(d.doc_type)],
                    green_words=[d.title],
                )

if __name__ == "__main__":
    main()