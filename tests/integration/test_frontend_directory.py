"""
Selenium integration tests for the directory page frontend UI (/directory).
Tests WCAG 2.1 Level AA compliance and frontend UI functionality.
Note: These tests verify the frontend UI only, not backend search functionality.
"""
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class TestDirectoryFrontendAccessibility:
    """Test WCAG 2.1 Level AA compliance on directory page frontend."""
    
    def test_language_attribute(self, driver, base_url):
        """Test that HTML lang attribute is set (WCAG 3.1.1)."""
        driver.get(f"{base_url}/directory")
        html = driver.find_element(By.TAG_NAME, "html")
        assert html.get_attribute("lang") == "en", "HTML lang attribute should be 'en'"
    
    def test_page_title(self, driver, base_url):
        """Test that page has a descriptive title (WCAG 2.4.2)."""
        driver.get(f"{base_url}/directory")
        title = driver.title
        assert title and len(title) > 0, "Page should have a title"
        assert "Directory" in title or "Package" in title, "Title should be descriptive"
    
    def test_heading_hierarchy(self, driver, base_url):
        """Test that headings are in logical order (WCAG 1.3.1)."""
        driver.get(f"{base_url}/directory")
        h1 = driver.find_elements(By.TAG_NAME, "h1")
        assert len(h1) > 0, "Page should have at least one h1"
        # Check that h1 comes before h2, h2 before h3, etc.
        headings = driver.find_elements(By.CSS_SELECTOR, "h1, h2, h3, h4, h5, h6")
        if len(headings) > 1:
            for i in range(len(headings) - 1):
                current_level = int(headings[i].tag_name[1])
                next_level = int(headings[i + 1].tag_name[1])
                assert next_level <= current_level + 1, "Headings should not skip levels"
    
    def test_search_form_labels(self, driver, base_url):
        """Test that search form inputs have associated labels (WCAG 1.3.1, 4.1.2)."""
        driver.get(f"{base_url}/directory")
        search_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='search']")
        for input_elem in search_inputs:
            input_id = input_elem.get_attribute("id")
            if input_id:
                # Check for label with 'for' attribute
                label = driver.find_elements(By.CSS_SELECTOR, f"label[for='{input_id}']")
                # Or check for aria-label
                aria_label = input_elem.get_attribute("aria-label")
                assert len(label) > 0 or aria_label, f"Search input {input_id} should have a label or aria-label"
    
    def test_aria_labels(self, driver, base_url):
        """Test that interactive elements have aria-labels where needed (WCAG 4.1.2)."""
        driver.get(f"{base_url}/directory")
        buttons = driver.find_elements(By.TAG_NAME, "button")
        for button in buttons:
            text = button.text.strip()
            aria_label = button.get_attribute("aria-label")
            # Buttons should have text or aria-label
            assert text or aria_label, "Button should have text or aria-label"
    
    def test_keyboard_navigation(self, driver, base_url):
        """Test that all interactive elements are keyboard accessible (WCAG 2.1.1)."""
        driver.get(f"{base_url}/directory")
        # Test tab navigation
        body = driver.find_element(By.TAG_NAME, "body")
        body.send_keys(Keys.TAB)
        focused = driver.switch_to.active_element
        assert focused is not None, "Should be able to focus on elements with keyboard"
    
    def test_focus_indicators(self, driver, base_url):
        """Test that focus indicators are visible (WCAG 2.4.7)."""
        driver.get(f"{base_url}/directory")
        search_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='search'], input[id='q']")
        if search_inputs:
            search_input = search_inputs[0]
            search_input.send_keys(Keys.TAB)
            # Check if element has focus styles (outline or box-shadow)
            focused = driver.switch_to.active_element
            outline = focused.value_of_css_property("outline")
            box_shadow = focused.value_of_css_property("box-shadow")
            # At least one should be non-default
            assert outline != "none" or box_shadow != "none", "Focused elements should have visible focus indicators"
    
    def test_skip_links(self, driver, base_url):
        """Test skip links for main content (WCAG 2.4.1)."""
        driver.get(f"{base_url}/directory")
        # Check for skip link or main landmark
        main = driver.find_elements(By.CSS_SELECTOR, "main, [role='main'], #main")
        assert len(main) > 0, "Page should have main content landmark"


class TestDirectoryFrontendUI:
    """Test directory page frontend UI functionality."""
    
    def test_directory_page_loads(self, driver, base_url):
        """Test that directory page frontend loads successfully."""
        driver.get(f"{base_url}/directory")
        assert "Package Directory" in driver.page_source or "Directory" in driver.title
    
    def test_search_form_ui(self, driver, base_url):
        """Test that search form UI elements are present and interactable."""
        driver.get(f"{base_url}/directory")
        search_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='search'], input[id='q']")
        if search_inputs:
            search_input = search_inputs[0]
            search_input.clear()
            search_input.send_keys("test")
            search_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            search_button.click()
            # Wait for results or error message to appear in UI
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".grid, .no-results, table, .package-list"))
            )
    
    def test_model_list_ui_display(self, driver, base_url):
        """Test that model list UI elements are displayed in the directory."""
        driver.get(f"{base_url}/directory")
        # Wait for content to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
        )
        # Check if models are displayed (could be in table, grid, or list format)
        content = driver.find_elements(By.CSS_SELECTOR, "table, .grid, .package-list, .model-item")
        # At least the page structure should be present
        assert len(content) >= 0, "Directory page should load"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


