# Email Tracking Tool

## Project Overview

This application provides a comprehensive solution for tracking email engagement, developed as part of the assessment for the Data Signal Optimization Specialist role at CISS International. Built with Python using the Flask framework by Khilav Jadav, it allows authorized staff members to compose and send emails with embedded tracking pixels, monitor open events, and view detailed reports.

The tool captures key metrics upon sending (time, sender IP/location) and upon each email open (time, opener IP/location, device information), storing this data securely in a MySQL database (configurable for local development or production RDS). It features a clean web interface for ease of use by non-technical staff.

**Core Features:**

*   **User Authentication:** Secure login system for staff members.
*   **Web-Based Email Composition:** Interface to write and send HTML emails.
*   **Automatic Pixel Injection:** Transparent 1x1 tracking pixel automatically added to outgoing emails.
*   **Send Event Logging:** Captures timestamp, sender's IP, and sender's location when an email is sent via the application.
*   **Open Event Tracking:** Logs timestamp, opener's IP, opener's location (via GeoIP), and User-Agent string for every email open.
*   **Detailed Reporting:** View individual email performance, including all open events and summary statistics.
*   **Dashboard View:** Overview of recently sent tracked emails.
*   **Database Persistence:** Uses MySQL via SQLAlchemy ORM.
*   **Database Migrations:** Managed by Flask-Migrate (Alembic) for reliable schema updates.
*   **Configuration Management:** Uses environment variables (`.env` file) for secure handling of credentials and settings.

---

## Technology Stack

*   **Backend Framework:** Flask 2.3+
*   **Database:** MySQL 5.7+ / 8.0+ (Tested with AWS RDS)
*   **ORM:** Flask-SQLAlchemy
*   **Database Migrations:** Flask-Migrate (Alembic)
*   **Web Forms:** Flask-WTF (WTForms)
*   **User Authentication:** Flask-Login, Werkzeug (Password Hashing)
*   **IP Geolocation:** GeoIP2 (using MaxMind GeoLite2 City database)
*   **Email Sending:** smtplib, email (Standard Python Libraries)
*   **Configuration:** python-dotenv
*   **Language:** Python 3.8+
*   **(Deployment Recommendation):** Gunicorn, Docker, Docker Compose

---
## Screenshots

**1. Login Page:**  
![Login Page](email-tracker-flask/UI-images/dashboard.jpg)

**2. Dashboard:**  
![Dashboard](email-tracker-flask/UI-images/login-image.jpg)

**3. Compose Email Page:**  
![Compose Email Page](email-tracker-flask/UI-images/compose.jpg)

**4. Email Report Page:**  
![Email Report Page](email-tracker-flask/UI-images/compose.jpg)


---

## Prerequisites

Before setting up the application, ensure you have the following installed:

1.  **Python:** Version 3.8 or higher.
2.  **pip:** Python package installer (usually included with Python).
3.  **Git:** For cloning the repository (if applicable).
4.  **MySQL Server:** Access to a running MySQL instance (local or remote, e.g., AWS RDS). Ensure you have credentials with permissions to create databases/tables or use an existing database.
5.  **MySQL Development Libraries (for `mysqlclient`):** *(Only needed if `pip install` fails for `mysqlclient`)*
    *   **Debian/Ubuntu:** `sudo apt-get update && sudo apt-get install python3-dev default-libmysqlclient-dev build-essential`
    *   **Fedora/CentOS/RHEL:** `sudo yum install python3-devel mysql-devel gcc` or `sudo dnf install python3-devel mysql-devel gcc redhat-rpm-config`
    *   **macOS (Homebrew):** `brew install mysql` (usually sufficient).
    *   **Windows:** May require installing MySQL Connector/C or ensuring `mysqlclient` wheels are available/compatible. Use `mysql-connector-python` (already in requirements) as an alternative if `mysqlclient` proves difficult.

---

## Setup Instructions

*(Assumes you have received the complete project file structure).*

1.  **Navigate to Project Directory:** Open your terminal and `cd` into the `email-tracker-flask` directory containing all the provided files.

2.  **Place GeoIP Database:**
    *   Ensure the `GeoLite2-City.mmdb` file (provided or downloaded from MaxMind) is placed inside the `geoip_data/` directory.

3.  **Place Tracking Pixel:**
    *   Ensure the 1x1 transparent `pixel.gif` file (provided) is placed inside the `app/static/` directory.

4.  **Configure Environment File (`.env`):**
    *   Open the `.env` file located in the project root.
    *   **CRITICAL:** Set a unique, strong `SECRET_KEY`.
    *   **CRITICAL:** Fill in the correct database credentials (`DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`).
    *   **CRITICAL:** Fill in the correct SMTP credentials (`SMTP_SERVER`, `SMTP_PORT`, `SMTP_USE_TLS`, `SMTP_USE_SSL`, `SMTP_USERNAME`, `SMTP_PASSWORD`). **Use an App Password for Gmail/Outlook if 2FA is enabled.**
    *   Verify `GEOIP_DATABASE_PATH` points to the correct location relative to the project root.

5.  **Set Up Python Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    # Activate:
    # Windows CMD: venv\Scripts\activate.bat
    # Windows PowerShell: .\venv\Scripts\Activate.ps1
    # macOS/Linux: source venv/bin/activate
    ```

6.  **Install Dependencies:**
    ```bash
    # Ensure virtual environment is active if using one
    pip install -r requirements.txt
    ```

7.  **Database Setup & Migrations:**
    *   **Ensure Database Exists:** Make sure the database specified in `.env` (`DB_NAME`) exists on your MySQL server and the user (`DB_USER`) has full privileges on it. If not, create the database and grant permissions.
    *   **Initialize Migrations Folder (Run Once):**
        ```bash
        flask db init
        ```
    *   **Create Initial Migration Script:** *(This reflects the current models)*
        ```bash
        flask db migrate -m "Initial database schema"
        ```
    *   **Apply Migrations to Database:** *(This creates the tables)*
        ```bash
        flask db upgrade
        ```
    *   **Troubleshooting:** If `flask db upgrade` fails (e.g., due to permissions), see the "Manual Table Creation" section below.

8.  **Manual Table Creation (Optional/Fallback):**
    *   If `flask db upgrade` encounters issues creating the tables, you can manually create them using a MySQL client connected to your database (`DB_NAME`).
    *   **Run these SQL statements in order:**
        ```sql
        -- -----------------------------------------------------
        -- Table `users`
        -- -----------------------------------------------------
        CREATE TABLE IF NOT EXISTS `users` (
          `id` INT NOT NULL AUTO_INCREMENT,
          `username` VARCHAR(80) NOT NULL,
          `password_hash` VARCHAR(255) NULL DEFAULT NULL, -- Increased length
          PRIMARY KEY (`id`),
          UNIQUE INDEX `username_UNIQUE` (`username` ASC) VISIBLE,
          INDEX `ix_users_username` (`username` ASC) VISIBLE)
        ENGINE = InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

        -- -----------------------------------------------------
        -- Table `sent_emails`
        -- -----------------------------------------------------
        CREATE TABLE IF NOT EXISTS `sent_emails` (
          `id` INT NOT NULL AUTO_INCREMENT,
          `tracking_id` VARCHAR(36) NOT NULL,
          `send_time` DATETIME NOT NULL,
          `sender_ip` VARCHAR(45) NULL DEFAULT NULL,
          `sender_location` VARCHAR(100) NULL DEFAULT NULL,
          `sender_user_id` INT NULL DEFAULT NULL, -- Added user link
          `subject` VARCHAR(255) NULL DEFAULT NULL,
          `recipient_email` VARCHAR(255) NULL DEFAULT NULL,
          PRIMARY KEY (`id`),
          UNIQUE INDEX `tracking_id_UNIQUE` (`tracking_id` ASC) VISIBLE,
          INDEX `ix_sent_emails_tracking_id` (`tracking_id` ASC) VISIBLE,
          INDEX `fk_sent_emails_users_idx` (`sender_user_id` ASC) VISIBLE, -- Index for FK
          CONSTRAINT `fk_sent_emails_users` -- Foreign Key constraint
            FOREIGN KEY (`sender_user_id`)
            REFERENCES `users` (`id`)
            ON DELETE SET NULL
            ON UPDATE NO ACTION)
        ENGINE = InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

        -- -----------------------------------------------------
        -- Table `email_opens`
        -- -----------------------------------------------------
        CREATE TABLE IF NOT EXISTS `email_opens` (
          `id` INT NOT NULL AUTO_INCREMENT,
          `sent_email_id` INT NOT NULL,
          `open_time` DATETIME NOT NULL,
          `opener_ip` VARCHAR(45) NULL DEFAULT NULL,
          `opener_location` VARCHAR(100) NULL DEFAULT NULL,
          `user_agent` VARCHAR(255) NULL DEFAULT NULL,
          PRIMARY KEY (`id`),
          INDEX `ix_email_opens_sent_email_id` (`sent_email_id` ASC) VISIBLE,
          CONSTRAINT `fk_email_opens_sent_emails`
            FOREIGN KEY (`sent_email_id`)
            REFERENCES `sent_emails` (`id`)
            ON DELETE CASCADE
            ON UPDATE NO ACTION)
        ENGINE = InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

        -- -----------------------------------------------------
        -- Table `alembic_version` (Needed for Flask-Migrate tracking)
        -- -----------------------------------------------------
        CREATE TABLE IF NOT EXISTS `alembic_version` (
            `version_num` VARCHAR(32) NOT NULL,
            PRIMARY KEY (`version_num`)
        ) ENGINE = InnoDB DEFAULT CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

        -- After manual creation, stamp the migration history:
        -- flask db stamp head
        ```
    *   If you create tables manually, run `flask db stamp head` in the terminal afterwards to tell Flask-Migrate that the database schema is up-to-date with the latest migration script, preventing it from trying to create tables again.

9.  **Create Initial Admin User:**
    ```bash
    flask create-user
    ```
    *   Follow the prompts to set a username and password for the first web interface user.

---

## Running the Application

1.  Ensure your virtual environment is activated (if using).
2.  Make sure your MySQL server is running and accessible.
3.  From the project root directory (`email-tracker-flask/`), run:
    ```bash
    flask run
    ```
4.  The application will start, typically listening on `http://127.0.0.1:5000/`. Check console output for errors.
5.  Open your web browser and navigate to the address shown.

---

## Usage Guide

1.  **Login:** Navigate to `http://127.0.0.1:5000/login` (or the root URL) and log in using the credentials created with `flask create-user`.
2.  **Dashboard:** After login, you'll land on the dashboard (`/dashboard`) which lists emails you have previously sent using the application.
3.  **Compose Email:** Click the "Compose" link (or navigate to `/compose`).
    *   Fill in the Recipient Email, Subject, and Email Body (HTML is allowed).
    *   Click "Send Tracked Email".
    *   The application will log the send event, inject the tracking pixel, and attempt to send the email using the configured SMTP settings.
4.  **View Reports:** From the dashboard, click "View Report" for any sent email.
    *   The report page shows details captured during the send (Time, Sender Info, Subject, Recipient).
    *   It also lists every recorded open event for that specific email (Time, Opener IP, Location, User Agent).
    *   The "Total Opens" count reflects every time the tracking pixel was loaded.
5.  **Tracking Pixel:** The 1x1 pixel GIF is served from `/track/open/<tracking_id>.gif`. This endpoint logs the open event whenever accessed by an email client loading images.
6.  **Logout:** Click the "Logout" link in the navigation bar.

---

## Understanding "Forward" Tracking (Limitation)

This tool utilizes the industry-standard method of tracking email opens: an invisible 1x1 pixel image embedded in the email.

*   **What is tracked:** Every time this pixel is loaded by an email client (when images are enabled), the tool records an "open event" with the timestamp, the IP address making the request, the approximate location derived from that IP, and the browser/client identifier (User-Agent string).
*   **What this means for "Forwards":**
    *   If an email is forwarded and the *new* recipient opens it (with images enabled), this **will trigger a new open event**. This event will likely have a different IP address, location, and timestamp than the original open(s).
    *   The tool **cannot definitively distinguish** an open event caused by a forward from an open event caused by:
        *   The original recipient opening the email multiple times.
        *   The original recipient opening the email on different devices (e.g., desktop then phone).
        *   The original recipient opening the email on different networks (e.g., work then home).
        *   Email clients (like Gmail or Apple Mail Privacy Protection) pre-fetching or proxying the image request, which can record an open with the *proxy's* IP/location, sometimes even before the user truly viewed it.
*   **Conclusion:** The report page shows the **total number of recorded open events**. A high number, especially with varying IPs and locations, *may suggest* the email was shared or forwarded, but it cannot be guaranteed. This is an inherent limitation of pixel-based tracking.

---

## Deployment (Example - Render)

This application is suitable for deployment on platforms like Render, Heroku, or traditional VPS setups using a production WSGI server like Gunicorn.

**Example using Render (Web Service):**

1.  Push the project code to a Git repository (GitHub, GitLab).
2.  Create a new "Web Service" on Render, connecting it to your repository.
3.  **Environment:** Select "Python 3".
4.  **Build Command:** `pip install -r requirements.txt && flask db upgrade` (Installs dependencies and applies migrations on build).
5.  **Start Command:** `gunicorn "app:create_app()"` (Adjust workers/settings as needed: `gunicorn -w 4 --bind 0.0.0.0:$PORT "app:create_app()"` - Render injects PORT).
6.  **Environment Variables:** Add **all** variables from your local `.env` file (especially `SECRET_KEY`, `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `SMTP_*`, `FLASK_DEBUG=False`) into Render's secure "Environment" settings section via their dashboard. **Do not commit your `.env` file to Git.**
7.  Ensure your Database (e.g., RDS) Security Group/Firewall allows connections from Render's outbound IP addresses.
8.  Deploy the service.

---