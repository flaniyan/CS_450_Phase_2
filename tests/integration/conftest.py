"""
Shared pytest fixtures for Selenium frontend tests.
"""
import pytest
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager


def pytest_collection_modifyitems(config, items):
    """Print test cases that will be run."""
    print("\n" + "=" * 80)
    print("TEST CASES TO BE RUN:")
    print("=" * 80)
    for i, item in enumerate(items, 1):
        test_name = item.nodeid
        # Extract just the test name for cleaner output
        if "::" in test_name:
            parts = test_name.split("::")
            if len(parts) >= 3:
                test_name = f"{parts[0]}::{parts[1]}::{parts[2]}"
        print(f"  {i:3d}. {test_name}")
    print("=" * 80 + "\n")


def pytest_runtest_setup(item):
    """Print test name when it starts running."""
    test_name = item.nodeid.split("::")[-1]
    class_name = item.cls.__name__ if item.cls else ""
    if class_name:
        print(f"\n[RUNNING] {class_name}::{test_name}")
    else:
        print(f"\n[RUNNING] {test_name}")


@pytest.fixture(scope="module")
def driver():
    """Create and configure Chrome WebDriver for testing."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode for CI
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # Enable accessibility features
    chrome_options.add_argument("--force-color-profile=srgb")
    
    try:
        # Try to use webdriver-manager for automatic driver management
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except Exception:
        # Fallback to system ChromeDriver
        driver = webdriver.Chrome(options=chrome_options)
    
    driver.implicitly_wait(10)
    yield driver
    driver.quit()


@pytest.fixture
def base_url():
    """Get base URL for the frontend."""
    # Default to production URL if available, otherwise localhost
    return os.getenv("FRONTEND_URL", "https://d1peqh56nf2wej.cloudfront.net")

