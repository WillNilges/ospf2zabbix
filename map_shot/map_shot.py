from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# Set up Chrome options for headless mode
chrome_options = Options()
chrome_options.add_argument("--headless")  # Run Chrome in headless mode

# Create an instance of the Chrome WebDriver with the headless option
driver = webdriver.Chrome(executable_path='/path/to/chromedriver.exe', options=chrome_options)

# Navigate to the webpage
url = "https://www.nycmesh.net/map"
driver.get(url)

try:
    # Take a screenshot of the webpage
    driver.save_screenshot("nycmesh_map.png")
    print("Screenshot saved as 'nycmesh_map.png'")

finally:
    # Close the browser
    driver.quit()

