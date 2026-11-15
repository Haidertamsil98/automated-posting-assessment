# Recruiter submission guide

The supplied assessment specifies a **public GitHub repository** and an email submission by **22 November 2026**. It does not give a deadline time or timezone, so submit before that date if possible.

## 1. Finish your live demonstration

The implementation and offline test evidence are included. Live publishing has not been verified because your platform credentials were not available.

Follow the README to configure your `.env`, start the server, and post once to your own accounts/channels. Add reviewed screenshots or redacted logs in `evidence/` showing the actual responses and links. The existing `offline-demo.json` is clearly labeled simulation and must not be presented as live publishing evidence.

Read the adapters and tests before your interview so you can explain the choices. Describe any assistance used accurately if the recruiter asks or has an AI-use policy.

## 2. Put the source on public GitHub

Extract/copy this project to a permanent folder on your computer first. Do not upload the ZIP as the only repository content: reviewers need the extracted source files.

If Git and GitHub CLI are available, run from the project folder:

```bash
git init -b main
git add app tests scripts docs evidence .env.example .gitignore \
  README.md SUBMISSION.md requirements.txt requirements-dev.txt \
  requirements-lock.txt pyproject.toml
git diff --cached --stat
# Inspect staged files before committing. Do not stage .env or secrets.
git commit -m "Implement multi-platform posting assessment"
gh auth login
gh repo create automated-posting-assessment --public --source=. --remote=origin --push
```

Alternatively, create a repository at <https://github.com/new>, name it `automated-posting-assessment`, select **Public**, and upload the extracted source files through **Add file > Upload files**. Include `.env.example` and `.gitignore`; keep `.env`, `.venv`, caches and credentials out. Check that directories and `README.md` are visible directly in the repository.

Open the resulting repository in a private/incognito browser window to confirm it is public. The link will resemble `https://github.com/YOUR_USERNAME/automated-posting-assessment`.

## 3. Email the recruiter

According to the supplied assessment:

- **To:** `hr@chivoxai.com`
- **Subject:** `Your Full Name - Python Practical test review`

Replace all square-bracket placeholders, including the name in the subject:

```text
Dear Hiring Team,

Please find my submission for the Python Practical Test below.

Full Name: [Your full name]
GitHub Repository: [Your public GitHub repository URL]
Contact Number: [Your number with country code]
Current Location: [City, State/Province]
Best Time to Discuss: [Date, time range, and timezone]

LinkedIn Profile: [Your LinkedIn profile URL]
Instagram Profile: [Your Instagram profile URL]

The repository includes the FastAPI application, five platform integrations,
setup instructions, automated tests, API examples, and verification evidence.
The README states which checks were performed with mocked responses and
which live posting checks were completed.

Thank you for reviewing my submission. I look forward to discussing the
implementation with your panel.

Kind regards,
[Your full name]
```

If live testing is still incomplete, keep that limitation clear in the README and email. Do not claim that five live posts succeeded using the offline fixture results.

## 4. Profile verification requested in the assessment

The document also asks applicants to follow [Dxora Technologies on LinkedIn](https://www.linkedin.com/company/dxora-technologies) and [CREST on Instagram](https://www.instagram.com/crestspot/), and include their own LinkedIn/Instagram profile links with the application. These are instructions from the supplied recruitment brief; no accounts were followed and no personal profile links were shared during this work.

No email has been sent on your behalf.
