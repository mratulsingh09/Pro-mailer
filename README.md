# AutoReach — One-Click Resume & Cold Email Dispatcher

> **Apply to 50+ companies in minutes without getting blocked or marked as spam.**

AutoReach is a desktop web application built specifically for job seekers who want to send their resume and job inquiries to multiple recruiters, HR managers, and companies efficiently from their personal email.

---

## ⚠️ Why You Should NEVER Use Mass BCC for Job Applications

When job seekers send one email with 50 company emails pasted into `BCC`:
1. **Recruiter Spam Filters Flag It**: Modern email filters instantly flag mass BCC emails as generic spam or marketing blasts.
2. **Zero Personalization**: You cannot address the specific company or person (e.g. *"Dear Google Team"* vs *"Dear Hiring Manager"*).
3. **Account Risk**: Gmail and Outlook will quickly temporarily suspend accounts that blast dozens of recipients simultaneously in one envelope.

### How AutoReach Fixes This:
AutoReach sends **genuine 1-to-1 individual emails** via your own authenticated SMTP provider. Each recipient receives an isolated email addressed to them and their company, with your resume PDF attached, spaced out with a **safe human-like delay (5–10 seconds)** between sends.

---

## 🚀 Quick Start (One Click)

### Option 1: Double-Click Launcher
Simply double-click the **`START_AUTOREACH.bat`** file inside `d:\direct email\`.
It will automatically start the server and open the app in your browser at `http://localhost:8000`.

### Option 2: Terminal / Command Prompt
```bash
cd "d:\direct email"
python app.py
```
Then visit **http://localhost:8000** in your browser.

---

## 🔑 How to Setup Your Email Credentials

### For Gmail Users (Recommended):
Google requires an **App Password** for third-party automated tools (your normal login password will not work):

1. Go to your [Google Account Security Settings](https://myaccount.google.com/security) and ensure **2-Step Verification** is turned **ON**.
2. Go directly to **[Google App Passwords](https://myaccount.google.com/apppasswords)**.
3. In the "App name" box, type **`Job Mailer`** and click **Create**.
4. Google will display a 16-character passcode (e.g., `abcd efgh ijkl mnop`).
5. Copy that 16-character code and paste it into the **Password** field in AutoReach.
6. Click **Test Connection** to confirm it works!

### For Outlook / Hotmail / Office365:
- Host: `smtp.office365.com`
- Port: `587`
- Security: `STARTTLS`
- Use your normal Microsoft email & password (or App Password if 2FA is active).

---

## 📋 Preparing Your Companies List

AutoReach accepts `.csv`, `.xlsx`, or `.xls` files. You can also download our ready-to-use template directly from the app interface by clicking **"Sample Companies CSV"**.

Your spreadsheet can have the following columns:

| Company | Name | Email | Role | Notes |
| :--- | :--- | :--- | :--- | :--- |
| Google | Sundar Pichai | recruiter@google.com | Software Engineer | AI Team |
| Microsoft | Satya Nadella | hr@microsoft.com | Full Stack Developer | Azure Team |
| Amazon | Andy Jassy | jobs@amazon.com | Backend Engineer | AWS Cloud |

> *Tip: If contact `Name` is left blank, AutoReach automatically defaults to "Hiring Team".*

---

## ✍️ Dynamic Placeholders

You can use these placeholders in your Subject line or Email body. They will be replaced automatically for every company:
- `{Company}` &rarr; Company name (e.g. *Google*)
- `{Name}` &rarr; Recruiter or hiring manager name (e.g. *Sarah*)
- `{Role}` &rarr; Job title you are applying for (e.g. *Software Engineer*)
- `{SenderName}` &rarr; Your full name
- `{SenderEmail}` &rarr; Your email address

---

## 🛡️ Anti-Spam & Safety Safeguards

1. **Test Send to Yourself**: Send a live test email with attachment to your personal email first to inspect formatting and layout.
2. **Configurable Delays**: Mimics human behavior with random pauses (e.g. 5–10 seconds) between each email.
3. **Real-Time Live Console**: View live sent/failed status and live logs as emails go out.
4. **Instant Stop Button**: Halt the campaign at any moment.
5. **Export Report**: Download a CSV timestamp report of all sent emails for your records.
