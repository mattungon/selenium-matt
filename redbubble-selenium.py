"""
Redbubble checkout automation (Selenium).
Single-file, self-contained.
"""

import os
import re
import time
import base64
from datetime import datetime
from urllib.parse import urlparse

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException, TimeoutException, WebDriverException,
    StaleElementReferenceException, ElementNotInteractableException,
    InvalidElementStateException,
)
from selenium.webdriver.chrome.options import Options as ChromeOptions

try:
    import img2pdf
    HAS_IMG2PDF = True
except ImportError:
    HAS_IMG2PDF = False


# ===========================================================================
# CONFIG
# ===========================================================================
EMAIL = "huntbrad007@proton.me"
FULL_NAME = "ZBD5N299OI4c"
PHONE = "4705551234"

ADDRESSES = [
    {"address": "2151 East St NE",     "city": "Covington",   "state": "Georgia",       "zip": "30014"},
    {"address": "55 West 46th Street", "city": "New York",    "state": "New York",      "zip": "10036-4126"},
    {"address": "10 Timberlane Dr",    "city": "Pittsburgh",  "state": "Pennsylvania",  "zip": "15238"},
]

OUTPUT_ROOT = "redbubble_output"
CHECKOUT_URL = "https://www.redbubble.com/check-out"


# ===========================================================================
# SELECTORS
# ===========================================================================
SEL_COLOR_OPTION = (
    "#product-configurator-form_product_type_bodyColor "
    "> div > div > div:nth-child(2) > span > label:nth-child(1) > button"
)
SEL_SIZE_OPTION = (
    "#product-configurator-form_product_type_size "
    "> div > div > div:nth-child(2) > div "
    "> label.styles_label__31aa092b.styles_active__31aa092b > input"
)
SEL_ADD_TO_CART = (
    "#__next > div > main > div > div > div."
    "styles_box__54ba70e3.PrimaryContentSection_primaryContent__HacGS "
    "> div.styles_box__54ba70e3.PrimaryContentSection_addToCart__GBLa3 "
    "> div.styles_box__54ba70e3.PrimaryContentSection_desktopOnly__48TDn."
    "PrimaryContentSection_ATCButton__7NfMp > button"
)
SEL_ADD_TO_CART_FALLBACK = (
    "//button[contains(., 'Add to cart') or contains(., 'Add to Cart')]"
)
SEL_SELLER = (
    "#__next > div > main > div > div > div."
    "styles_box__54ba70e3.PrimaryContentSection_primaryContent__HacGS "
    "> div.styles_box__54ba70e3.PrimaryContentSection_listingInfo__yDWTW "
    "> div > div:nth-child(2) > div > div:nth-child(2) > div > span > a"
)
SEL_VIEW_CART = (
    "#react-aria-modal-dialog > div:nth-child(1) > div > div > div > div."
    "styles_box__54ba70e3.CartItemsTray_actions__1bI2c > a"
)
SEL_VIEW_CART_FALLBACK = "//a[contains(., 'View cart') or contains(., 'View Cart')]"
SEL_CHECKOUT_BTN = "//button[contains(., 'Checkout')] | //a[contains(., 'Checkout')]"

SEL_EMAIL = "input[type='email'][placeholder='Email address']"
SEL_EMAIL_FALLBACK = "input[type='email']"

SEL_CONTINUE_PAYMENT = "//button[@type='submit' and contains(., 'Continue to Payment')]"

IFRAME_ADDRESS = "iframe[title='Secure address input frame']"
IFRAME_AUTOCOMPLETE = "iframe[title='Google autocomplete suggestions dropdown list']"

STRIPE_SEL_FULLNAME = "#shippingAddress-nameInput"
STRIPE_SEL_COUNTRY = "#shippingAddress-countryInput"
STRIPE_SEL_ADDRESS = "#shippingAddress-addressLine1Input"
STRIPE_SEL_CITY    = "#shippingAddress-localityInput"
STRIPE_SEL_STATE   = "#shippingAddress-administrativeAreaInput"
STRIPE_SEL_ZIP     = "#shippingAddress-postalCodeInput"
STRIPE_SEL_PHONE   = "#shippingAddress-phoneInput"

IFRAME_PAYMENT = "iframe[title='Secure payment input frame']"
SEL_PAYPAL_IN_PAYMENT_IFRAME = (
    "div.p-AccordionButton "
    "div.p-PaymentAccordionButtonText"
)
SEL_PAYPAL_FALLBACK_XPATH = (
    "//div[contains(@class,'p-PaymentAccordionButtonText')]"
    "[.//*[normalize-space(text())='PayPal']]"
    "/ancestor::div[contains(@class,'p-AccordionButton')][1]"
)


# ===========================================================================
# HELPERS
# ===========================================================================
def is_redbubble_url(url: str) -> bool:
    try:
        host = (urlparse(url).netloc or "").lower()
        return host.endswith("redbubble.com")
    except Exception:
        return False


def slugify(text: str, max_len: int = 40) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")
    return text[:max_len] or "query"


def make_output_dir(url: str, keyword: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder = os.path.join(OUTPUT_ROOT, f"{slugify(keyword)}_{ts}")
    os.makedirs(folder, exist_ok=True)
    return folder


def save_png_and_pdf(driver, folder: str, prefix: str):
    png_path = os.path.join(folder, f"{prefix}.png")
    pdf_path = os.path.join(folder, f"{prefix}.pdf")

    try:
        metrics = driver.execute_cdp_cmd("Page.getLayoutMetrics", {})
        size = metrics.get("cssContentSize") or metrics.get("contentSize")
        width  = int(size["width"])
        height = int(size["height"])

        max_height = 20000
        if height > max_height:
            height = max_height

        result = driver.execute_cdp_cmd("Page.captureScreenshot", {
            "format": "png",
            "captureBeyondViewport": True,
            "clip": {
                "x": 0, "y": 0,
                "width": width, "height": height,
                "scale": 1,
            },
        })
        with open(png_path, "wb") as f:
            f.write(base64.b64decode(result["data"]))
        print(f"    [+] Full-page screenshot: {png_path} ({width}x{height})")
    except Exception as e:
        print(f"    [!] Full-page capture failed ({e}); using viewport.")
        driver.save_screenshot(png_path)
        print(f"    [+] Screenshot (viewport): {png_path}")

    if HAS_IMG2PDF:
        try:
            with open(pdf_path, "wb") as f:
                f.write(img2pdf.convert(png_path))
            print(f"    [+] PDF: {pdf_path}")
        except Exception as e:
            print(f"    [!] PDF failed: {e}")
    else:
        print("    [i] img2pdf not installed — skipping PDF.")
    return png_path, pdf_path


def save_page_as_pdf(driver, folder: str, filename: str):
    pdf_path = os.path.join(folder, filename)
    try:
        result = driver.execute_cdp_cmd("Page.printToPDF", {
            "printBackground": True,
            "preferCSSPageSize": False,
            "paperWidth":  8.27,
            "paperHeight": 11.69,
            "marginTop":    0.4,
            "marginBottom": 0.4,
            "marginLeft":   0.4,
            "marginRight":  0.4,
        })
        with open(pdf_path, "wb") as f:
            f.write(base64.b64decode(result["data"]))
        print(f"    [+] Full-page PDF: {pdf_path}")
        return pdf_path
    except Exception as e:
        print(f"    [!] save_page_as_pdf failed: {e}")
        return None


def js_click(driver, element):
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
    time.sleep(0.3)
    try:
        driver.execute_script("arguments[0].click();", element)
    except WebDriverException:
        element.click()


def find_first(driver, locators, timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        for by, sel in locators:
            try:
                for el in driver.find_elements(by, sel):
                    if el.is_displayed():
                        return el
            except Exception:
                continue
        time.sleep(0.4)
    return None


# ===========================================================================
# ANNOTATION
# ===========================================================================
ANNOTATION_CSS = """
.__rb_redact__ {
  background: #000 !important;
  color: #000 !important;
  text-shadow: none !important;
  border: none !important;
}
.__rb_redact__ * {
  color: #000 !important;
  background: #000 !important;
}
.__rb_highlight__ {
  outline: 4px solid #00ff00 !important;
  outline-offset: 3px !important;
  box-shadow: 0 0 0 6px rgba(0,255,0,0.35) !important;
}
"""

APPLY_ANNOTATIONS_JS = r"""
(function(email, fullName) {
  let redacted = 0;

  document.querySelectorAll("input[type='email']").forEach(el => {
    el.classList.add('__rb_redact__');
    redacted++;
  });

  const emailRe = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  const phoneRe = /^\+?[\d\s().\-]{7,}$/;
  document.querySelectorAll(
    'span, div, p, a, b, strong, em, label, li, h1, h2, h3, h4, h5, h6'
  ).forEach(el => {
    if (el.children.length > 0) return;
    const t = (el.innerText || '').trim();
    if (!t || t.length > 120) return;
    if (email && t === email)       { el.classList.add('__rb_redact__'); redacted++; return; }
    if (fullName && t === fullName) { el.classList.add('__rb_redact__'); redacted++; return; }
    if (emailRe.test(t))            { el.classList.add('__rb_redact__'); redacted++; return; }
    if (phoneRe.test(t) && /\d/.test(t) && t.length >= 7) {
      el.classList.add('__rb_redact__');
      redacted++;
      return;
    }
  });

  document.querySelectorAll('header *').forEach(el => {
    const t = (el.innerText || '').trim();
    if (/^(hi|hello|hey)[, ]/i.test(t) && t.length < 60) {
      el.classList.add('__rb_redact__');
      redacted++;
    }
  });

  let highlighted = 0;
  const targets = [
    "main [class*='CheckoutSteps_shippingStepGridArea']",
    "main [class*='CheckoutSteps_paymentStepGridArea']",
    "main [class*='CheckoutSteps_section__']",
    "main [class*='CheckoutSteps_deliveryAddressPreview']",
    "[data-testid='delivery-address-preview']",
  ];
  targets.forEach(sel => {
    document.querySelectorAll(sel).forEach(el => {
      const cls = el.className || '';
      if (cls.includes('cartSummaryGridArea')) return;
      el.classList.add('__rb_highlight__');
      highlighted++;
    });
  });

  return {redacted, highlighted};
})
"""

CLEAR_ANNOTATIONS_JS = """
(function() {
  document.querySelectorAll('.__rb_redact__, .__rb_highlight__')
    .forEach(el => el.classList.remove('__rb_redact__', '__rb_highlight__'));
  const s = document.getElementById('__rb_annotate__');
  if (s) s.remove();
})();
"""


def apply_annotations(driver, email="", full_name=""):
    driver.execute_script("""
        if (!document.getElementById('__rb_annotate__')) {
            const s = document.createElement('style');
            s.id = '__rb_annotate__';
            s.innerHTML = arguments[0];
            document.head.appendChild(s);
        }
    """, ANNOTATION_CSS)
    result = driver.execute_script(
        APPLY_ANNOTATIONS_JS + "(arguments[0], arguments[1]);",
        email, full_name
    ) or {}
    print(f"    [annotate] redacted={result.get('redacted')} "
          f"highlighted={result.get('highlighted')}")
    time.sleep(0.5)


def clear_annotations(driver):
    try:
        driver.execute_script(CLEAR_ANNOTATIONS_JS)
    except Exception:
        pass


# ===========================================================================
# BOT
# ===========================================================================
class RedbubbleBot:
    def __init__(self, headless=False):
        opts = ChromeOptions()
        if headless:
            opts.add_argument("--headless=new")
        opts.add_argument("--start-maximized")
        opts.add_argument("--disable-notifications")
        opts.add_argument("--disable-popup-blocking")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)
        self.driver = webdriver.Chrome(options=opts)
        self.wait = WebDriverWait(self.driver, 20)

    # ---------------- navigation ----------------
    def goto(self, url):
        self.driver.get(url)
        time.sleep(3)

    def refresh(self):
        self.driver.refresh()
        time.sleep(4)

    def close(self):
        try:
            self.driver.quit()
        except Exception:
            pass

    def scroll_page(self, step_px: int = 500, pause: float = 0.15,
                    passes: int = 2):
        """
        Scroll from top to bottom in increments, then back to top.
        Forces lazy-loaded images / reviews to render.
        `passes` = number of down+up cycles.
        """
        try:
            total_height = self.driver.execute_script(
                "return Math.max(document.body.scrollHeight, "
                "document.documentElement.scrollHeight);"
            )
            print(f"    [*] Scrolling page ({total_height}px tall, "
                  f"{passes} pass(es))...")

            for _ in range(passes):
                y = 0
                while y < total_height:
                    self.driver.execute_script(f"window.scrollTo(0, {y});")
                    time.sleep(pause)
                    y += step_px
                    new_height = self.driver.execute_script(
                        "return Math.max(document.body.scrollHeight, "
                        "document.documentElement.scrollHeight);"
                    )
                    if new_height > total_height:
                        total_height = new_height

                self.driver.execute_script(
                    "window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(0.4)

                self.driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(0.4)

            print("    [+] Page scrolled.")
        except Exception as e:
            print(f"    [!] scroll_page failed: {e}")

    # ---------------- product page ----------------
    def choose_color_if_available(self):
        try:
            btn = self.driver.find_element(By.CSS_SELECTOR, SEL_COLOR_OPTION)
            js_click(self.driver, btn)
            time.sleep(1)
            print("    [+] Color option clicked.")
            return True
        except NoSuchElementException:
            print("    [i] No color option.")
            return False

    def choose_size_if_available(self):
        try:
            el = self.driver.find_element(By.CSS_SELECTOR, SEL_SIZE_OPTION)
            js_click(self.driver, el)
            time.sleep(1)
            print("    [+] Size option clicked.")
            return True
        except NoSuchElementException:
            try:
                btns = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "#product-configurator-form_product_type_size button"
                )
                if btns:
                    js_click(self.driver, btns[0])
                    time.sleep(1)
                    print("    [+] Size option (fallback) clicked.")
                    return True
            except Exception:
                pass
            print("    [i] No size option.")
            return False

    def add_to_cart_button(self):
        try:
            return self.driver.find_element(By.CSS_SELECTOR, SEL_ADD_TO_CART)
        except NoSuchElementException:
            return find_first(
                self.driver, [(By.XPATH, SEL_ADD_TO_CART_FALLBACK)], timeout=3)

    def get_seller_link(self):
        try:
            a = self.driver.find_element(By.CSS_SELECTOR, SEL_SELLER)
            return a.get_attribute("href")
        except NoSuchElementException:
            for a in self.driver.find_elements(
                By.CSS_SELECTOR, "a[href*='/shop/'], a[href*='/people/']"
            ):
                href = a.get_attribute("href")
                if href:
                    return href
            return None

    def add_to_cart(self):
        btn = self.add_to_cart_button()
        if not btn:
            print("    [!] Add-to-cart button not found.")
            return False
        js_click(self.driver, btn)
        time.sleep(4)
        print("    [+] Clicked Add to Cart.")
        return True

    def view_cart(self):
        a = find_first(self.driver, [
            (By.CSS_SELECTOR, SEL_VIEW_CART),
            (By.XPATH, SEL_VIEW_CART_FALLBACK),
        ], timeout=10)
        if a:
            js_click(self.driver, a)
            time.sleep(4)
            print("    [+] Opened cart.")
            return True
        print("    [!] View cart not found; navigating to /cart directly.")
        self.goto("https://www.redbubble.com/cart")
        return True

    # ---------------- checkout ----------------
    def go_to_checkout(self):
        btn = find_first(self.driver, [(By.XPATH, SEL_CHECKOUT_BTN)], timeout=15)
        if btn:
            js_click(self.driver, btn)
            time.sleep(5)
            print("    [+] Clicked Checkout.")
            return True
        print("    [!] Checkout button not found.")
        return False

    def _wait_for_address_iframe(self, timeout=10):
        end = time.time() + timeout
        while time.time() < end:
            try:
                self.driver.switch_to.default_content()
                frames = self.driver.find_elements(By.CSS_SELECTOR, IFRAME_ADDRESS)
                if any(f.is_displayed() for f in frames):
                    return True
            except Exception:
                pass
            time.sleep(0.3)
        return False

    def _wait_for_payment_button(self, timeout=15):
        end = time.time() + timeout
        while time.time() < end:
            try:
                btn = self.driver.find_element(By.XPATH, SEL_CONTINUE_PAYMENT)
                if btn.is_displayed() and btn.is_enabled():
                    return True
            except Exception:
                pass
            time.sleep(0.3)
        return False

    def _expand_shipping_section(self, timeout=15):
        self.driver.switch_to.default_content()

        if self._wait_for_address_iframe(timeout=3):
            print("    [i] Shipping form already open.")
            return True

        print("    [*] Looking for Edit button on Delivery summary...")
        end = time.time() + timeout
        while time.time() < end:
            for xp in [
                "//div[@data-testid='delivery-address-preview']//button[contains(., 'Edit')]",
                "//div[contains(@class,'DeliveryAddressPreview')]//button[contains(., 'Edit')]",
                "//button[contains(., 'Edit')]",
                "//a[contains(., 'Edit')]",
                "//button[contains(., 'Change')]",
                "//a[contains(., 'Change')]",
            ]:
                try:
                    for btn in self.driver.find_elements(By.XPATH, xp):
                        if btn.is_displayed() and btn.is_enabled():
                            js_click(self.driver, btn)
                            print(f"    [+] Clicked Edit ({xp.split('//')[-1][:40]}).")
                            if self._wait_for_address_iframe(timeout=10):
                                return True
                except Exception:
                    continue
            time.sleep(0.5)

        print("    [!] Could not expand shipping section.")
        return False

    # ---------- typing ----------
    def _type_into(self, by, selector, text, clear=True, timeout=10, label=""):
        end = time.time() + timeout
        last_err = None
        while time.time() < end:
            try:
                el = self.driver.find_element(by, selector)
                if not el.is_displayed():
                    time.sleep(0.4)
                    continue
                if not el.is_enabled():
                    self.driver.execute_script(
                        "arguments[0].removeAttribute('disabled');"
                        "arguments[0].removeAttribute('readonly');", el)
                    time.sleep(0.3)
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", el)
                time.sleep(0.2)
                try:
                    el.click()
                except Exception:
                    self.driver.execute_script("arguments[0].focus();", el)
                if clear:
                    try:
                        el.clear()
                    except Exception:
                        pass
                    try:
                        self.driver.execute_script(
                            """
                            const el = arguments[0];
                            const setter = Object.getOwnPropertyDescriptor(
                              window.HTMLInputElement.prototype, 'value').set;
                            setter.call(el, '');
                            el.dispatchEvent(new Event('input', {bubbles:true}));
                            el.dispatchEvent(new Event('change',{bubbles:true}));
                            """, el)
                    except Exception:
                        pass
                try:
                    el.send_keys(text)
                except (ElementNotInteractableException,
                        InvalidElementStateException,
                        StaleElementReferenceException):
                    self.driver.execute_script(
                        """
                        const el = arguments[0];
                        const val = arguments[1];
                        const setter = Object.getOwnPropertyDescriptor(
                          window.HTMLInputElement.prototype, 'value').set;
                        setter.call(el, val);
                        el.dispatchEvent(new Event('input', {bubbles:true}));
                        el.dispatchEvent(new Event('change',{bubbles:true}));
                        el.dispatchEvent(new Event('blur',  {bubbles:true}));
                        """, el, text)
                print(f"    [+] {label or selector} = {text!r}")
                return el
            except (StaleElementReferenceException,
                    NoSuchElementException) as e:
                last_err = e
                time.sleep(0.5)
            except Exception as e:
                last_err = e
                time.sleep(0.5)
        print(f"    [!] {label or selector} failed after {timeout}s: {last_err}")
        return None

    # ---------- iframe navigation ----------
    def _enter_address_iframe(self, timeout=20):
        try:
            self.driver.switch_to.default_content()
            WebDriverWait(self.driver, timeout).until(
                EC.frame_to_be_available_and_switch_to_it(
                    (By.CSS_SELECTOR, IFRAME_ADDRESS))
            )
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, STRIPE_SEL_FULLNAME))
            )
            time.sleep(1.0)
            print("    [+] Entered Stripe address iframe.")
            return True
        except Exception as e:
            print(f"    [!] Could not enter address iframe: {e}")
            self.driver.switch_to.default_content()
            return False

    def _exit_iframe(self):
        try:
            self.driver.switch_to.default_content()
        except Exception:
            pass

    def _field_value(self, selector):
        try:
            el = self.driver.find_element(By.CSS_SELECTOR, selector)
            return (el.get_attribute("value") or "").strip()
        except NoSuchElementException:
            return ""

    def _pick_address_suggestion(self, timeout=10):
        self._exit_iframe()
        end = time.time() + timeout
        while time.time() < end:
            try:
                self.driver.switch_to.default_content()
                frames = self.driver.find_elements(
                    By.CSS_SELECTOR, IFRAME_AUTOCOMPLETE)
                for fr in frames:
                    try:
                        self.driver.switch_to.frame(fr)
                        for sel in [".pac-item",
                                    "li[role='option']",
                                    "[role='option']",
                                    "li"]:
                            for opt in self.driver.find_elements(
                                    By.CSS_SELECTOR, sel):
                                try:
                                    if opt.is_displayed():
                                        txt = (opt.text or "").strip()
                                        if txt:
                                            js_click(self.driver, opt)
                                            time.sleep(1.5)
                                            print(f"    [+] Picked suggestion: "
                                                  f"{txt[:60]!r}")
                                            self._exit_iframe()
                                            return True
                                except Exception:
                                    continue
                        self._exit_iframe()
                    except Exception:
                        self._exit_iframe()
                        continue
            except Exception:
                self._exit_iframe()
            time.sleep(0.5)
        self._exit_iframe()
        print("    [i] No address suggestion dropdown.")
        return False

    def _set_country_or_state(self, selector, value, label):
        el = self._type_into(By.CSS_SELECTOR, selector, value, label=label)
        if not el:
            return False
        try:
            el.send_keys(Keys.ENTER)
            time.sleep(1)
        except Exception:
            pass
        for sel in ["[role='option']", "li", "div[class*='option']"]:
            try:
                for opt in self.driver.find_elements(By.CSS_SELECTOR, sel):
                    if opt.is_displayed() and value.lower() in opt.text.lower():
                        js_click(self.driver, opt)
                        time.sleep(1)
                        return True
            except Exception:
                continue
        return True

    # ---------- fill shipping ----------
    def fill_shipping(self, addr, is_first: bool):
        self._exit_iframe()
        email_el = find_first(self.driver, [
            (By.CSS_SELECTOR, SEL_EMAIL),
            (By.CSS_SELECTOR, SEL_EMAIL_FALLBACK),
        ], timeout=15)
        if email_el:
            try:
                email_el.clear()
                email_el.send_keys(EMAIL)
                print(f"    [+] Email = {EMAIL!r}")
            except Exception as e:
                print(f"    [!] Email send failed: {e}")
        else:
            print("    [!] Email field not found at top level.")

        time.sleep(1)

        if not self._enter_address_iframe():
            raise RuntimeError("Could not enter Stripe address iframe.")

        try:
            if is_first:
                self._type_into(By.CSS_SELECTOR, STRIPE_SEL_FULLNAME,
                                FULL_NAME, label="Full name")
            else:
                print("    [i] Skipping full name (keeping existing).")

            if is_first:
                if not self._field_value(STRIPE_SEL_COUNTRY):
                    self._set_country_or_state(STRIPE_SEL_COUNTRY,
                                               "United States", "Country")
                else:
                    print(f"    [i] Country already set: "
                          f"{self._field_value(STRIPE_SEL_COUNTRY)!r}")
            else:
                print("    [i] Skipping country (keeping existing).")

            if not self._type_into(By.CSS_SELECTOR, STRIPE_SEL_ADDRESS,
                                   addr["address"], label="Address (initial)"):
                raise RuntimeError("Address field failed.")

            time.sleep(2.0)
            self._exit_iframe()
            self._pick_address_suggestion()
            time.sleep(1.5)

            if not self._enter_address_iframe():
                raise RuntimeError("Lost Stripe iframe after suggestion.")

            print("    [i] Re-typing address fields to enforce correctness.")
            self._type_into(By.CSS_SELECTOR, STRIPE_SEL_ADDRESS,
                            addr["address"], label="Address (final)")
            self._set_country_or_state(STRIPE_SEL_STATE, addr["state"], "State")
            self._type_into(By.CSS_SELECTOR, STRIPE_SEL_CITY,
                            addr["city"], label="City")
            self._type_into(By.CSS_SELECTOR, STRIPE_SEL_ZIP,
                            addr["zip"], label="ZIP")

            if is_first:
                self._type_into(By.CSS_SELECTOR, STRIPE_SEL_PHONE,
                                PHONE, label="Phone")
            else:
                print("    [i] Skipping phone (keeping existing).")
        finally:
            self._exit_iframe()

        time.sleep(1)
        return True

    def continue_to_payment(self):
        self._exit_iframe()
        try:
            btn = WebDriverWait(self.driver, 15).until(
                EC.element_to_be_clickable((By.XPATH, SEL_CONTINUE_PAYMENT))
            )
            js_click(self.driver, btn)
            time.sleep(6)
            print("    [+] Clicked Continue to Payment.")
            return True
        except Exception as e:
            print(f"    [!] Continue to Payment failed: {e}")
            return False

    # ---------- PayPal ----------
    def select_paypal(self, timeout=20):
        print("    [*] Selecting PayPal...")
        end = time.time() + timeout

        while time.time() < end:
            self._exit_iframe()
            try:
                frame = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, IFRAME_PAYMENT))
                )
                self.driver.switch_to.frame(frame)
                time.sleep(0.6)

                try:
                    for el in self.driver.find_elements(
                            By.CSS_SELECTOR, SEL_PAYPAL_IN_PAYMENT_IFRAME):
                        if el.is_displayed():
                            txt = (el.text or "").lower()
                            if "paypal" in txt:
                                target = el
                                for _ in range(3):
                                    try:
                                        if "p-AccordionButton" in (
                                                target.get_attribute("class") or ""):
                                            break
                                        target = target.find_element(By.XPATH, "..")
                                    except Exception:
                                        break
                                js_click(self.driver, target)
                                time.sleep(2)
                                print("    [+] Clicked PayPal (CSS).")
                                self._exit_iframe()
                                return True
                except Exception:
                    pass

                try:
                    for el in self.driver.find_elements(
                            By.XPATH, SEL_PAYPAL_FALLBACK_XPATH):
                        if el.is_displayed():
                            js_click(self.driver, el)
                            time.sleep(2)
                            print("    [+] Clicked PayPal (XPath).")
                            self._exit_iframe()
                            return True
                except Exception:
                    pass

                try:
                    els = self.driver.find_elements(
                        By.XPATH,
                        "//*[normalize-space(text())='PayPal']")
                    for el in els:
                        if el.is_displayed():
                            target = el
                            for _ in range(4):
                                try:
                                    cls = target.get_attribute("class") or ""
                                    if "p-AccordionButton" in cls:
                                        break
                                    target = target.find_element(By.XPATH, "..")
                                except Exception:
                                    break
                            js_click(self.driver, target)
                            time.sleep(2)
                            print("    [+] Clicked PayPal (text match).")
                            self._exit_iframe()
                            return True
                except Exception:
                    pass

                self._exit_iframe()
            except TimeoutException:
                self._exit_iframe()
                print("    [i] Payment iframe not present yet...")
            except Exception as e:
                self._exit_iframe()
                print(f"    [!] select_paypal attempt failed: {e}")
            time.sleep(1)

        print("    [!] Could not select PayPal.")
        return False

    # ---------------- store page ----------------
    def go_to_seller(self, seller_link):
        self.goto(seller_link)
        time.sleep(2)


# ===========================================================================
# WORKFLOW
# ===========================================================================
def run():
    url = input("Redbubble product URL: ").strip()
    if not is_redbubble_url(url):
        print("[!] Not a Redbubble URL. Exiting.")
        return
    keyword = input("Keyword (folder name only): ").strip()
    headless = input("Headless? (y/n): ").strip().lower() == "y"

    out_dir = make_output_dir(url, keyword)
    print(f"[+] Output folder: {out_dir}")

    bot = RedbubbleBot(headless=headless)
    try:
        # ------- product page -------
        bot.goto(url)
        bot.scroll_page(step_px=500, pause=0.15, passes=2)   # <-- NEW
        bot.choose_color_if_available()
        bot.choose_size_if_available()

        if not bot.add_to_cart_button():
            print("[!] No Add to Cart button. Exiting.")
            return

        seller_link = bot.get_seller_link()
        print(f"[+] Seller link: {seller_link}")

        # ------- add to cart → checkout -------
        bot.add_to_cart()
        bot.view_cart()
        bot.go_to_checkout()

        # ------- LOOP 1: all addresses -------
        for i, addr in enumerate(ADDRESSES):
            is_first = (i == 0)
            print(f"\n=== Checkout {i+1}/{len(ADDRESSES)}: "
                  f"{addr['city']}, {addr['state']} ===")

            try:
                if not is_first:
                    print("    [*] Navigating back to checkout...")
                    bot.goto(CHECKOUT_URL)
                    time.sleep(5)

                    if not bot._expand_shipping_section():
                        print(f"    [!] Skipping address {i+1} — "
                              f"could not open shipping form.")
                        continue

                    bot._wait_for_address_iframe(timeout=10)
                    bot._wait_for_payment_button(timeout=10)

                bot.fill_shipping(addr, is_first=is_first)

                if not bot.continue_to_payment():
                    print(f"    [!] Continue to Payment failed for "
                          f"address {i+1}. Skipping screenshot.")
                    continue

                # Select PayPal inside payment iframe
                bot.select_paypal()

                # ---- PAYMENT PAGE: annotate + FULL-PAGE screenshot + PDF ----
                bot._exit_iframe()
                bot.scroll_page(step_px=500, pause=0.15, passes=1)   # <-- NEW
                time.sleep(2.5)
                apply_annotations(bot.driver, EMAIL, FULL_NAME)
                save_png_and_pdf(
                    bot.driver, out_dir,
                    f"payment_addr{i+1}_{slugify(addr['city'])}"
                )
                clear_annotations(bot.driver)

            except Exception as e:
                print(f"    [!] Address {i+1} failed: {e}")
                try:
                    bot._exit_iframe()
                except Exception:
                    pass
                continue

        # ------- LOOP 2 (once): seller page → full-page PDF -------
        if seller_link:
            print("\n=== Seller page → full-page PDF ===")
            bot.go_to_seller(seller_link)
            bot.scroll_page(step_px=500, pause=0.15, passes=2)   # <-- NEW
            time.sleep(3)
            save_page_as_pdf(bot.driver, out_dir, "seller_page.pdf")

        print("\n[+] Done.")

    finally:
        bot.close()


if __name__ == "__main__":
    run()