from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

# Di __init__ atau method:
try:
    # Auto install dan setup driver
    service = Service(ChromeDriverManager().install())
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')  # Run tanpa UI
    options.add_argument('--no-sandbox')  # Penting di cloud
    options.add_argument('--disable-dev-shm-usage')  # Fix memory issue
    self.driver = webdriver.Chrome(service=service, options=options)
    logger.info("✅ Selenium Chrome initialized with auto-driver")
except Exception as e:
    logger.warning(f"⚠️ Selenium failed: {e} - Fallback to mock")
    self.driver = None  # Atau mock mode
