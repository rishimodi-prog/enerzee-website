# Support Copy And Deletion Navigation Regression Tests

Scoped repair based on website main
`f50603d57b9f73f2ece1b3b95600795ff475b5da`. No publication is implied.

Run with the Python standard library; no dependency installation is needed:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

The tests parse the HTML and cover Free/Pro/AI Pro wording, legacy access,
trial eligibility, logging confirmation, production and local-file link
resolution, unchanged deletion instructions and the existing contact form.
No network request, account operation, email or form submission is executed.

The scoped boundary checks pin the unchanged Terms, Privacy and original
root-level deletion page. A later approved change to those pages requires an
explicit review of those pins; do not update them to hide unrelated drift.

Browser visual verification completed locally on 22 October 2026 at 1440x900
and 390x844 using a temporary server bound only to 127.0.0.1. The four changed
FAQ answers fit without clipping or horizontal overflow, and all six repaired
deletion-page navigation links reached their correct settled destinations.
The server was stopped and browser sizing restored after the check. No form
was submitted. This verifies the local repair; publication remains separate.

The retained release evidence contains the local render screenshots and navigation readback. The PR changes the same two verified HTML files; it does not publish the separate Terms or Privacy drafts.
