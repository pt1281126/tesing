import streamlit as st
from bs4 import BeautifulSoup
import re
import requests
from urllib.parse import urljoin, urlparse

# ---------------- HELPER FUNCTIONS ----------------
def count_visible_occurrences(soup, text):
    """Count only visible text occurrences of `text`, ignoring hidden elements."""
    blacklist = ['style', 'script', 'head', 'title', 'meta', 'noscript', '[document]']
    elements = soup.find_all(string=lambda t: text in t)
    count = 0
    for elem in elements:
        if elem.parent.name not in blacklist:
            count += elem.count(text)
    return count

def check_phone_email(html_content, phone=None, email=None):
    results = {}
    summary_status = True  

    if not phone:
        results["phone"] = "❌ Phone EMPTY"
        summary_status = False
    if not email:
        results["email"] = "❌ Email EMPTY"
        summary_status = False

    soup = BeautifulSoup(html_content, "html.parser")

    # ---------------- PHONE CHECK ----------------
    if phone:
        phone_text_count = count_visible_occurrences(soup, phone)
        all_text_phones = re.findall(
            r'\b(?:\+44\s?\d{4,}|\(?0\d{2,4}\)?)\s?\d{3,4}\s?\d{3,4}\b',
            soup.get_text()
        )
        phone_link_tags = soup.find_all("a", href=lambda href: href and "tel:" in href)
        phone_link_count = sum(1 for a in phone_link_tags if phone in a['href'])

        if phone_text_count > 0:
            results["phone_text"] = f"✅ Phone '{phone}' found ({phone_text_count} times)"
        else:
            results["phone_text"] = f"❌ Phone '{phone}' NOT found"
            summary_status = False

        if phone_link_count > 0:
            results["phone_link"] = f"✅ Phone link 'tel:{phone}' found ({phone_link_count} times)"
        else:
            results["phone_link"] = f"❌ Phone link 'tel:{phone}' NOT found"
            summary_status = False

        visible_phones = [num for num in all_text_phones if count_visible_occurrences(soup, num) > 0]
        other_phones = set(visible_phones) - {phone}
        if other_phones:
            results["other_phone_text"] = f"❌ Found other phone numbers: {list(other_phones)}"
            summary_status = False

        other_phone_links = [a['href'] for a in phone_link_tags if phone not in a['href']]
        if other_phone_links:
            results["other_phone_links"] = f"❌ Found other phone links: {other_phone_links}"
            summary_status = False

    # ---------------- EMAIL CHECK ----------------
    if email:
        email_text_count = count_visible_occurrences(soup, email)
        all_text_emails = re.findall(r'[\w\.-]+@[\w\.-]+', soup.get_text())
        email_link_tags = soup.find_all("a", href=lambda href: href and "mailto:" in href)
        email_link_count = sum(1 for a in email_link_tags if email in a['href'])

        if email_text_count > 0:
            results["email_text"] = f"✅ Email '{email}' found ({email_text_count} times)"
        else:
            results["email_text"] = f"❌ Email '{email}' NOT found"
            summary_status = False

        if email_link_count > 0:
            results["email_link"] = f"✅ Email link 'mailto:{email}' found ({email_link_count} times)"
        else:
            results["email_link"] = f"❌ Email link 'mailto:{email}' NOT found"
            summary_status = False

        visible_emails = [e for e in all_text_emails if count_visible_occurrences(soup, e) > 0]
        other_emails = set(visible_emails) - {email}
        if other_emails:
            results["other_email_text"] = f"❌ Found other emails: {list(other_emails)}"
            summary_status = False

        other_email_links = [a['href'] for a in email_link_tags if email not in a['href']]
        if other_email_links:
            results["other_email_links"] = f"❌ Found other email links: {other_email_links}"
            summary_status = False

    return results, summary_status

def get_internal_links(base_url, html_content):
    """Extract all internal Wix links"""
    soup = BeautifulSoup(html_content, "html.parser")
    base_domain = urlparse(base_url).netloc
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        full_url = urljoin(base_url, href.split("?")[0])
        if urlparse(full_url).netloc == base_domain:
            if full_url not in links:
                links.append(full_url)
    return links

def get_body_links_info(soup, base_url=None):
    """Get all visible body text links, ignoring buttons, tel:, mailto:, and specific Wix button class."""
    main_content = soup.find('main') or soup.find('body')
    if not main_content:
        return []
    links = main_content.find_all('a', href=True)
    link_info = []
    for a in links:
        text = a.get_text(strip=True)
        if not text:
            continue
        href = a['href']
        classes = a.get("class") or []
        if href.startswith('tel:') or href.startswith('mailto:'):
            continue
        if "button" in classes or "StylableButton2545352419__root" in classes:
            continue
        # Only consider internal links for body link count if base_url is provided
        if base_url:
            full_url = urljoin(base_url, href.split("?")[0])
            if urlparse(full_url).netloc != urlparse(base_url).netloc:
                continue
            link_info.append({"text": text, "href": full_url})
        else:
            link_info.append({"text": text, "href": href})
    return link_info

def count_valid_body_links(soup, base_url=None):
    """Count only unique valid internal body links (must point to different pages)."""
    links = get_body_links_info(soup, base_url)
    unique_pages = set()
    for l in links:
        unique_pages.add(l['href'])
    return len(unique_pages)

def check_self_links_body_only(soup, page_url):
    """Check if a page contains self-links only in body/main content."""
    main_content = soup.find('main') or soup.find('body')
    if not main_content:
        return []
    self_links = []
    links = main_content.find_all('a', href=True)
    for a in links:
        href = urljoin(page_url, a['href'].split("?")[0])
        if href == page_url:
            self_links.append(href)
    return self_links

# ---------------- STREAMLIT APP ----------------
st.title("🔍 Welcome Ranjit Kumar Mehta")

# st.write(
#     "Enter your **Wix preview home page link**, expected **Phone** and **Email**, "
#     "and the tool will scan **all internal pages**.\n\n"
#     "- Only visible phone/email text is counted.\n"
#     "- Checks that only the entered phone/email exist and are linked.\n"
#     "- Flags any other phone/email or links as errors.\n"
#     "- Each page must have at least 2 valid body links to **different internal pages**.\n"
#     "- All images must have ALT, '.' is allowed only at the end.\n"
#     "- Self-links in body/main content are flagged as errors."
# )

url = st.text_input("Enter Wix Preview Home URL")
phone = st.text_input("Enter Phone Number (with exact spacing)")
email = st.text_input("Enter Email Address")

if st.button("Check Now"):
    if url:
        try:
            response = requests.get(url)
            response.raise_for_status()
            home_html = response.text

            # Collect all internal links
            to_visit = get_internal_links(url, home_html)
            visited = set()
            pages = []
            all_body_links_set = set()

            while to_visit:
                page = to_visit.pop(0)
                if page not in visited:
                    visited.add(page)
                    try:
                        resp = requests.get(page)
                        resp.raise_for_status()
                        html = resp.text
                        pages.append(page)
                        new_links = get_internal_links(url, html)
                        for l in new_links:
                            if l not in visited and l not in to_visit:
                                to_visit.append(l)
                        # Add body links to set
                        soup = BeautifulSoup(html, "html.parser")
                        body_links = get_body_links_info(soup)
                        for link in body_links:
                            full_url = urljoin(page, link["href"])
                            all_body_links_set.add(full_url)
                    except:
                        pass

            st.write(f"📑 Found {len(pages)} internal pages to scan")
            overall_status = True
            error_pages = []

            for page in pages:
                st.subheader(f"🔎 Results for {page}")
                try:
                    resp = requests.get(page)
                    resp.raise_for_status()
                    soup = BeautifulSoup(resp.text, "html.parser")

                    # Phone/Email checks
                    results, summary_status = check_phone_email(resp.text, phone, email)
                    for key, value in results.items():
                        if "✅" in value:
                            st.success(value)
                        else:
                            st.error(value)

                    # Minimum 2 valid body links to DIFFERENT pages
                    body_link_count = count_valid_body_links(soup, page)
                    if body_link_count >= 2:
                        st.success(f"✅ Page has {body_link_count} valid internal body links to different pages (minimum 2 required)")
                    else:
                        st.error(f"❌ Page has only {body_link_count} valid internal body links to different pages (minimum 2 required)")
                        summary_status = False
                        overall_status = False
                        error_pages.append(page)

                    # List body links
                    body_links = get_body_links_info(soup, page)
                    if body_links:
                        st.subheader("🔗 Body Links on this page:")
                        for link in body_links:
                            st.write(f"- Text: '{link['text']}' → URL: {link['href']}")
                    else:
                        st.info("No valid internal body links found on this page.")

                    # Check self-links in body only
                    self_links = check_self_links_body_only(soup, page)
                    if self_links:
                        st.error(f"❌ Page contains self-links in body: {self_links}")
                        summary_status = False
                        overall_status = False
                        error_pages.append(page)
                    else:
                        st.success("✅ No self-links in body found on this page")

                    # Check if page is linked somewhere
                    if page not in all_body_links_set:
                        st.error(f"❌ This page is not linked anywhere on the website!")
                        summary_status = False
                        overall_status = False
                        error_pages.append(page)
                    else:
                        st.success("✅ This page is linked at least once on the website")

                    # ---------------- IMAGE ALT CHECK ----------------
                    images = soup.find_all("img")
                    missing_alt = False
                    for img in images:
                        alt = img.get("alt", "").strip()
                        if not alt or '.' in alt[:-1]:
                            missing_alt = True
                            break

                    if images:
                        if missing_alt:
                            st.error(f"❌ Page {page}: Some images are missing ALT or have invalid ALT")
                            summary_status = False
                            overall_status = False
                            if page not in error_pages:
                                error_pages.append(page)
                        else:
                            st.success(f"✅ Page {page}: All images have valid ALTs")
                    else:
                        st.info(f"Page {page}: No images found")

                    if summary_status:
                        st.info("✅ PASS for this page")
                    else:
                        st.error("❌ FAIL for this page")
                        overall_status = False
                        if page not in error_pages:
                            error_pages.append(page)

                except Exception as e:
                    st.error(f"Failed to fetch {page}: {e}")
                    overall_status = False
                    error_pages.append(page)

            st.subheader("📋 Final Summary")
            if overall_status:
                st.success("✅ PASS: All pages are consistent, linked, and have valid ALTs.")
            else:
                st.error("❌ FAIL: Errors found on these pages:")
                for ep in error_pages:
                    st.write(f"🔗 {ep}")

        except Exception as e:
            st.error(f"Failed to fetch Home URL: {e}")
    else:
        st.error("Please enter a Wix preview URL.")
