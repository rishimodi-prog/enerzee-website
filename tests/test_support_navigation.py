"""Offline regressions for the scoped Support-copy and deletion-navigation repair."""

import hashlib
from html.parser import HTMLParser
from pathlib import Path
import unittest
from urllib.parse import urljoin, urlsplit


ROOT = Path(__file__).resolve().parents[1]
PROTECTED_FILES = {
    "terms.html": "885a5815536544d76da104e07248a504e65f5233f202b76d26bb6606d95ad2fa",
    "privacy.html": "7a56beddba48b3000500e3a3a31d1387837d0f5a67373557715e9b36765a5266",
    "delete-account.html": "c0482f63665e980e488caea2aa2d4d2896f22fef2806cc578f8ace11f79ed0bb",
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
        answer = self.faq["Is EnerZee free to use?"]
        self.assertIn("core food and workout tracking", answer)
        self.assertIn("basic Progress", answer)
        self.assertIn("does not include an ongoing", answer)
        self.assertIn("no additional AI chat trial", answer)

    def test_pro_is_separate_from_hosted_ai_pro(self):
        answer = self.faq["How do Pro and AI Pro differ?"]
        self.assertIn("Connected AI (MCP)", answer)
        self.assertIn("does not by itself include EnerZee-hosted AI Coach chat", answer)
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

    def test_legal_documents_and_original_deletion_page_preserve_scope(self):
        for name, expected in PROTECTED_FILES.items():
            with self.subTest(file=name):
                actual = (ROOT / name).read_bytes()
                if name == "delete-account.html":
                    age_screen_guidance = (
                        b"    <p>If EnerZee shows <strong>Confirm your age</strong> or "
                        b"<strong>Your account is safely paused</strong>, choose "
                        b"<strong>Delete account</strong> on that screen and follow the "
                        b"confirmation prompts.</p>\n"
                    )
                    self.assertEqual(actual.count(age_screen_guidance), 1)
                    actual = actual.replace(age_screen_guidance, b"", 1)
                    actual = actual.replace(b"support@enerzee.app", b"privacy@enerzee.app")
                self.assertEqual(hashlib.sha256(actual).hexdigest(), expected)

    def test_support_form_keeps_existing_required_fields_and_no_native_action(self):
        form = next(self.support.root.find_all("form"))
        self.assertEqual(form.attrs.get("id"), "contactForm")
        self.assertEqual(form.attrs.get("onsubmit"), "handleContact(event)")
        self.assertNotIn("action", form.attrs)
        fields = {
            field.attrs.get("id"): field
            for tag in ("input", "select", "textarea")
            for field in form.find_all(tag)
        }
        self.assertEqual(set(fields), {"name", "email", "topic", "message"})
        self.assertEqual(fields["email"].attrs.get("type"), "email")
        self.assertTrue(all("required" in field.attrs for field in fields.values()))

    def test_deletion_navigation_targets_site_root(self):
        expected = {
            "EnerZee": "/index.html",
            "\u2190 Back to Home": "/index.html",
            "Home": "/index.html",
            "Privacy Policy": "/privacy.html",
            "Terms of Use": "/terms.html",
            "Support": "/support.html",
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
                    self.assertTrue((ROOT / resolved.path.lstrip("/")).is_file())

    def test_navigation_also_works_in_local_file_preview(self):
        base = (ROOT / "delete-account/index.html").as_uri()
        for area in ("nav", "footer"):
            for region in self.deletion.root.find_all(area):
                for link in region.find_all("a"):
                    with self.subTest(href=link.attrs["href"]):
                        resolved = urlsplit(urljoin(base, link.attrs["href"]))
                        self.assertEqual(resolved.scheme, "file")
                        self.assertTrue(Path(resolved.path).is_file())

    def test_deletion_instructions_and_cancellation_warning_unchanged(self):
        actual = next(self.deletion.root.find_all(class_name="legal"))
        original = next(self.root_deletion.root.find_all(class_name="legal"))
        self.assertEqual(actual.snapshot(), original.snapshot())
        self.assertIn("does not automatically cancel", actual.text())
        links = [a.attrs["href"] for a in actual.find_all("a")]
        self.assertIn("mailto:support@enerzee.app?subject=Delete%20my%20EnerZee%20account", links)


if __name__ == "__main__":
    unittest.main()
