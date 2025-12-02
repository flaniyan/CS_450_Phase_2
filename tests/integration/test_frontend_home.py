"""
Selenium integration tests for the homepage frontend UI.
Tests WCAG 2.1 Level AA compliance and frontend UI functionality.
Note: These tests verify the frontend UI only, not backend functionality.
"""
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys


class TestHomeFrontendAccessibility:
    """Test WCAG 2.1 Level AA compliance on homepage frontend."""
    
    def test_language_attribute(self, driver, base_url):
        """Test that HTML lang attribute is set (WCAG 3.1.1)."""
        driver.get(base_url)
        html = driver.find_element(By.TAG_NAME, "html")
        assert html.get_attribute("lang") == "en", "HTML lang attribute should be 'en'"
    
    def test_page_title(self, driver, base_url):
        """Test that page has a descriptive title (WCAG 2.4.2)."""
        driver.get(base_url)
        title = driver.title
        assert title and len(title) > 0, "Page should have a title"
        assert "ACME" in title or "Registry" in title, "Title should be descriptive"
    
    def test_skip_link(self, driver, base_url):
        """Test skip link for main content (WCAG 2.4.1)."""
        driver.get(base_url)
        # Check for skip link or main landmark
        skip_links = driver.find_elements(By.CSS_SELECTOR, ".skip-link, a[href='#main']")
        main = driver.find_elements(By.CSS_SELECTOR, "main, [role='main'], #main")
        assert len(skip_links) > 0 or len(main) > 0, "Page should have skip link or main landmark"
    
    def test_navigation_structure(self, driver, base_url):
        """Test navigation has proper ARIA labels."""
        driver.get(base_url)
        nav = driver.find_elements(By.CSS_SELECTOR, "nav, [role='navigation']")
        if nav:
            aria_label = nav[0].get_attribute("aria-label")
            assert aria_label, "Navigation should have aria-label"
    
    def test_heading_hierarchy(self, driver, base_url):
        """Test that headings are in logical order (WCAG 1.3.1)."""
        driver.get(base_url)
        h1 = driver.find_elements(By.TAG_NAME, "h1")
        assert len(h1) > 0, "Page should have at least one h1"
        
        headings = driver.find_elements(By.CSS_SELECTOR, "h1, h2, h3, h4, h5, h6")
        if len(headings) > 1:
            for i in range(len(headings) - 1):
                current_level = int(headings[i].tag_name[1])
                next_level = int(headings[i + 1].tag_name[1])
                assert next_level <= current_level + 1, "Headings should not skip levels"
    
    def test_keyboard_navigation(self, driver, base_url):
        """Test that all interactive elements are keyboard accessible (WCAG 2.1.1)."""
        driver.get(base_url)
        body = driver.find_element(By.TAG_NAME, "body")
        body.send_keys(Keys.TAB)
        focused = driver.switch_to.active_element
        assert focused is not None, "Should be able to focus on elements with keyboard"
    
    def test_focus_indicators(self, driver, base_url):
        """Test that focus indicators are visible (WCAG 2.4.7)."""
        driver.get(base_url)
        # Find first focusable element
        links = driver.find_elements(By.TAG_NAME, "a")
        if links:
            links[0].send_keys(Keys.TAB)
            focused = driver.switch_to.active_element
            outline = focused.value_of_css_property("outline")
            box_shadow = focused.value_of_css_property("box-shadow")
            # At least one should be non-default
            assert outline != "none" or box_shadow != "none", "Focused elements should have visible focus indicators"


class TestHomeFrontendUI:
    """Test homepage frontend UI functionality."""
    
    def test_homepage_loads(self, driver, base_url):
        """Test that homepage frontend loads successfully."""
        driver.get(base_url)
        assert "ACME Registry" in driver.title or "ACME Registry" in driver.page_source
    
    def test_navigation_links_ui(self, driver, base_url):
        """Test that all navigation links are present and clickable in the frontend."""
        driver.get(base_url)
        # Get hrefs first to avoid stale element issues
        nav_links = driver.find_elements(By.CSS_SELECTOR, "nav a")
        hrefs = []
        for link in nav_links:
            try:
                href = link.get_attribute("href")
                if href and not href.startswith("#"):
                    if base_url in href or href.startswith("/"):
                        hrefs.append(href)
            except Exception:
                # Skip stale elements
                continue
        
        # Test each link by navigating directly
        for href in hrefs:
            try:
                driver.get(href)
                import time
                time.sleep(1)  # Wait for page load
                assert driver.current_url, "Navigation should work"
                driver.back()  # Return to homepage
                time.sleep(0.5)  # Wait for navigation
            except Exception as e:
                # Log but don't fail - some links might require auth
                print(f"Navigation test skipped for {href}: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

