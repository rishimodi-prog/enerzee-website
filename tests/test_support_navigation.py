"""Offline regressions for the scoped Support-copy and deletion-navigation repair."""

import hashlib
from html.parser import HTMLParser
from pathlib import Path
import unittest
from urllib.parse import urljoin, urlsplit


ROOT = Path(__file__).resolve().parents[1]
PROTECTED_FILES = {
    "terms.html": "e7b66f79f21eba8caf6ee94ecbd79274be4be45138974359244f961676d8af7b",
    "privacy.html": "d2f7cd5feef12de1ea11cef72ebfacaadc4834c4da0d50c9d59d60020cd47591",
    "delete-account.html": "739fdf86d0140d3fc5aabf604e9fd1029d9ac9045849681a3ca4051b038d8aad",
    "delete-account/index.html": "615f655fb0aa0374e0e4f6b04206ea3b399d56edef025ad5812f4f12007d9318",
}
VOID_ELEMENTS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}


class Element:
    def __init__(self, tag, attrs=()):
        self.tag = tag
        self.attrs = dict(attrs)
        self.children = []

    def find_all(self, tag=None, class_name=None):
        for child in self.children:
            if not isinstance(child, Element):
                continue
            classes = child.attrs.get("class", "").split()
            if (tag is None or child.tag == tag) and (
                class_name is None or class_name in classes
            ):
                yield child
            yield from child.find_all(tag, class_name)

    def text(self):
        return " ".join("".join(
            child.text() if isinstance(child, Element) else child
            for child in self.children
        ).split())

    def snapshot(self):
        return [self.tag, sorted(self.attrs.items()), [
            child.snapshot() if isinstance(child, Element) else child
            for child in self.children
        ]]


class Page(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.root = Element("document")
        self.stack = [self.root]
        self.feed(source)
        self.close()

    def handle_starttag(self, tag, attrs):
        node = Element(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in VOID_ELEMENTS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID_ELEMENTS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)

    def faq_answers(self):
        result = {}
        for item in self.root.find_all(class_name="faq-item"):
            question = next(item.find_all(class_name="faq-q")).text().rstrip(" \u25bc")
            result[question] = next(item.find_all(class_name="faq-a")).text()
        return result


class SupportNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.support = Page((ROOT / "support.html").read_text(encoding="utf-8"))
        cls.faq = cls.support.faq_answers()
        cls.deletion = Page((ROOT / "delete-account/index.html").read_text(encoding="utf-8"))
        cls.root_deletion = Page((ROOT / "delete-account.html").read_text(encoding="utf-8"))

    def test_free_has_no_ongoing_or_extra_hosted_chat_trial(self):
        answer = self.faq["Is Iron Chapter free to use?"]
        self.assertIn("core food and workout tracking", answer)
        self.assertIn("basic Progress", answer)
        self.assertIn("does not include an ongoing", answer)
        self.assertIn("no additional AI chat trial", answer)

    def test_pro_is_separate_from_hosted_ai_pro(self):
        answer = self.faq["How do Pro and AI Pro differ?"]
        self.assertIn("Connected AI (MCP)", answer)
        self.assertIn("does not by itself include AI Coach chat hosted by Iron Chapter", answer)
        self.assertIn("AI Pro includes Pro features", answer)
        self.assertIn("up to 100 Coach messages per day", answer)
        self.assertIn("Other AI features have their own limits", answer)

    def test_legacy_access_and_store_trial_eligibility_are_preserved(self):
        answer = self.faq["What happens to legacy purchases and trials?"]
        self.assertIn("both Pro and AI Pro retain that access", answer)
        self.assertIn("separate from a store subscription trial", answer)
        self.assertIn("does not automatically charge you or grant AI Pro", answer)
        self.assertIn("only when the store confirms", answer)
        self.assertIn("eligibility", answer)

    def test_no_obsolete_daily_chat_or_unlimited_claim(self):
        text = " ".join(self.faq.values()).lower()
        self.assertNotIn("5 ai messages per day", text)
        self.assertNotIn("unlimited ai", text)
        self.assertNotIn("midnight utc", text)

    def test_coach_requires_review_confirmation_and_saved_entry_check(self):
        answer = self.faq["How does the AI coach work?"]
        self.assertIn("Review", answer)
        self.assertIn("confirm", answer)
        self.assertIn("saved entry and totals", answer)
        self.assertNotIn("logs everything automatically", answer)

    def test_legal_documents_and_deletion_page_match_reviewed_publication(self):
        for name, expected in PROTECTED_FILES.items():
            with self.subTest(file=name):
                actual = (ROOT / name).read_bytes()
                self.assertEqual(hashlib.sha256(actual).hexdigest(), expected)

    def test_support_hands_off_to_the_branded_form(self):
        self.assertEqual(list(self.support.root.find_all("form")), [])
        destinations = {link.attrs["href"] for link in self.support.root.find_all("a")}
        self.assertIn("https://theironchapter.com/support", destinations)
        self.assertIn("mailto:support@theironchapter.com", destinations)

    def test_deletion_navigation_targets_site_root(self):
        expected = {
            "Iron Chapter": "/index.html",
            "\u2190 Back to Home": "/index.html",
            "Home": "/index.html",
            "Privacy Policy": "/privacy.html",
            "Terms of Use": "/terms",
            "Support": "/support",
        }
        links = list(self.deletion.root.find_all("a"))
        for label, destination in expected.items():
            with self.subTest(label=label):
                matches = [link for link in links if link.text() == label]
                self.assertEqual(len(matches), 1)
                for base in (
                    "https://enerzee.app/delete-account/",
                    "https://enerzee.app/delete-account/index.html",
                ):
                    resolved = urlsplit(urljoin(base, matches[0].attrs["href"]))
                    self.assertEqual(resolved.netloc, "enerzee.app")
                    self.assertEqual(resolved.path, destination)
                    member = ROOT / resolved.path.lstrip("/")
                    self.assertTrue(member.is_file() or (member / "index.html").is_file())

    def test_extensionless_pages_match_the_historical_html_aliases(self):
        for name in ("download", "privacy", "support", "terms"):
            with self.subTest(page=name):
                self.assertEqual(
                    (ROOT / name / "index.html").read_bytes(),
                    (ROOT / (name + ".html")).read_bytes(),
                )

    def test_deletion_instructions_and_cancellation_warning_unchanged(self):
        actual = next(self.deletion.root.find_all(class_name="legal"))
        original = next(self.root_deletion.root.find_all(class_name="legal"))
        self.assertEqual(actual.snapshot(), original.snapshot())
        self.assertIn("does not automatically cancel", actual.text())
        links = [a.attrs["href"] for a in actual.find_all("a")]
        self.assertIn("mailto:support@theironchapter.com?subject=Delete%20my%20Iron%20Chapter%20account", links)


if __name__ == "__main__":
    unittest.main()
