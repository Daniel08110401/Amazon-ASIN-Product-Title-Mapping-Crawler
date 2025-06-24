# Amazon-ASIN-Product-Title-Mapping-Crawler

This project automates the process of mapping Amazon ASIN (Amazon Standard Identification Number) codes to product titles using a hybrid web scraping pipeline.

It leverages **Google Search**, **ScrapeOps Proxy**, and **Amazon product pages** to reliably extract product titles associated with each ASIN, with robust fallback handling for redirection, CAPTCHA, and request failures.

---

### 🔍 Key Features

* Automates batch ASIN-to-title mapping previously done manually
* Uses Google Search and ScrapeOps to locate valid Amazon product URLs
* Extracts product titles via `requests` and `BeautifulSoup`, with fallback to `Selenium` when CAPTCHA is detected
* Verifies ASIN consistency in redirected URLs
* Exports results to structured CSV, including error flags for manual follow-up
* Reduces manual effort by over 87% and improves data accuracy significantly

---

### 🛠 Tech Stack

* Python, Pandas, Requests, BeautifulSoup
* Selenium with headless Chrome
* ScrapeOps Proxy
* Regular expressions for ASIN validation

---

Let me know if you'd like this rewritten in a shorter version for the GitHub **description field**, or if you'd like help writing detailed usage instructions for the README.
